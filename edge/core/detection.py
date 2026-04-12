"""YOLO detection and ROI utilities — supports YOLOv5 (torch.hub) and Ultralytics (YOLOv8+)"""
import json
import warnings
from typing import Optional, List, Union, Tuple
import numpy as np
import cv2

from .config import CONF_TH, IOU_TH, DEVICE, WEIGHTS, REPO, YOLO_BACKEND
from .logger import get_logger

log = get_logger("detection")

# Check Intel XPU availability
INTEL_XPU_AVAILABLE = False
try:
    import intel_extension_for_pytorch as ipex
    import torch
    if hasattr(torch, 'xpu') and torch.xpu.is_available():
        INTEL_XPU_AVAILABLE = True
        log.info("Intel XPU available: %s", torch.xpu.get_device_name(0))
except ImportError:
    pass


def get_optimal_device():
    """Determine the best available device for inference"""
    import torch
    
    # If user specified a device, try to use it
    if DEVICE and DEVICE != "auto":
        if DEVICE == "xpu" and INTEL_XPU_AVAILABLE:
            return "xpu"
        elif DEVICE == "cuda" and torch.cuda.is_available():
            return "cuda"
        elif DEVICE == "cpu":
            return "cpu"
        else:
            log.warning("Requested device '%s' not available, falling back...", DEVICE)
    
    # Auto-detect best device
    if INTEL_XPU_AVAILABLE:
        return "xpu"
    elif torch.cuda.is_available():
        return "cuda"
    else:
        return "cpu"


def load_yolov5_model():
    """Load YOLOv5 via torch.hub with Intel XPU support"""
    import torch
    
    # Suppress torch.cuda.amp.autocast deprecation warning
    warnings.filterwarnings("ignore", message=".*torch.cuda.amp.autocast.*", category=FutureWarning)
    
    # Determine device
    device = get_optimal_device()
    log.info("Loading YOLOv5 model '%s' on device: %s", WEIGHTS, device)
    
    if REPO and WEIGHTS:
        model = torch.hub.load(REPO, "custom", path=WEIGHTS, source="local", force_reload=True)
    elif WEIGHTS and not REPO:
        model = torch.hub.load("ultralytics/yolov5", "custom", path=WEIGHTS, force_reload=True)
    else:
        model = torch.hub.load("ultralytics/yolov5", "yolov5s", pretrained=True, force_reload=True)

    model.conf = CONF_TH
    model.iou = IOU_TH
    model.classes = [0]  # person only
    
    # Move model to device
    model.to(device)
    
    # Optimize with Intel Extension for PyTorch if using XPU
    if device == "xpu" and INTEL_XPU_AVAILABLE:
        try:
            import intel_extension_for_pytorch as ipex
            model = ipex.optimize(model)
            log.info("Model optimized with Intel Extension for PyTorch")
        except Exception as e:
            log.warning("IPEX optimization failed: %s", e)
    
    log.info("YOLOv5 model loaded successfully on %s", device)
    return model


# ---------------------------------------------------------------------------
# Ultralytics wrapper — makes YOLOv8/v9/v10/v11 look like YOLOv5 to loops.py
# ---------------------------------------------------------------------------

class _UltralyticsResults:
    """Mimics the `results.xyxy[0]` interface that loops.py expects."""

    def __init__(self, result):
        import torch
        boxes = result.boxes
        if boxes is not None and len(boxes) > 0:
            xyxy = boxes.xyxy.cpu()             # (N, 4)
            conf = boxes.conf.cpu().unsqueeze(1) # (N, 1)
            cls  = boxes.cls.cpu().unsqueeze(1)  # (N, 1)
            combined = torch.cat([xyxy, conf, cls], dim=1)  # (N, 6)
        else:
            combined = torch.zeros((0, 6))
        self.xyxy = [combined]


class _UltralyticsModelWrapper:
    """Wraps an Ultralytics YOLO model to match the YOLOv5 call signature."""

    def __init__(self, model, conf: float, iou: float):
        self._model = model
        self._conf = conf
        self._iou = iou

    def __call__(self, frame, size: int = 640):
        results = self._model(
            frame,
            imgsz=size,
            conf=self._conf,
            iou=self._iou,
            classes=[0],   # person only
            verbose=False,
        )
        return _UltralyticsResults(results[0])

    # Passthrough so callers can do model.to(device) without an error
    def to(self, device):
        return self


def load_ultralytics_model():
    """Load a YOLOv8/v9/v10/v11 model via the ultralytics package."""
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise ImportError(
            "Package 'ultralytics' is required for YOLO_BACKEND=ultralytics. "
            "Install it with:  pip install ultralytics"
        ) from exc

    device = get_optimal_device()
    log.info("Loading Ultralytics model '%s' on device: %s", WEIGHTS, device)

    model = YOLO(WEIGHTS)
    model.to(device)

    log.info("Ultralytics model loaded successfully on %s", device)
    return _UltralyticsModelWrapper(model, conf=CONF_TH, iou=IOU_TH)


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def load_model():
    """Load the YOLO model selected by YOLO_BACKEND env variable.

    YOLO_BACKEND=yolov5       → YOLOv5 via torch.hub  (default)
    YOLO_BACKEND=ultralytics  → YOLOv8/v9/v10/v11 via ultralytics package
    """
    backend = YOLO_BACKEND
    log.info("YOLO_BACKEND=%r", backend)
    if backend == "ultralytics":
        return load_ultralytics_model()
    if backend == "yolov5":
        return load_yolov5_model()
    raise ValueError(
        f"Unknown YOLO_BACKEND={backend!r}. "
        "Supported values: 'yolov5', 'ultralytics'"
    )


def _bbox_area(box: Tuple[float, float, float, float]) -> float:
    return max(0.0, float(box[2]) - float(box[0])) * max(0.0, float(box[3]) - float(box[1]))


def _bbox_intersection(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float],
) -> float:
    inter_x1 = max(float(box_a[0]), float(box_b[0]))
    inter_y1 = max(float(box_a[1]), float(box_b[1]))
    inter_x2 = min(float(box_a[2]), float(box_b[2]))
    inter_y2 = min(float(box_a[3]), float(box_b[3]))
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    return inter_w * inter_h


def _coverage_ratio(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float],
) -> Tuple[float, float]:
    inter_area = _bbox_intersection(box_a, box_b)
    area_a = _bbox_area(box_a)
    area_b = _bbox_area(box_b)
    cov_a = inter_area / area_a if area_a > 0 else 0.0
    cov_b = inter_area / area_b if area_b > 0 else 0.0
    return cov_a, cov_b


def _is_nested_duplicate(
    candidate: Tuple[float, float, float, float, float],
    existing: Tuple[float, float, float, float, float],
    containment_threshold: float = 0.9,
    x_alignment_ratio: float = 0.25,
    height_ratio_threshold: float = 1.2,
) -> bool:
    cand_box = candidate[:4]
    exist_box = existing[:4]
    cand_area = _bbox_area(cand_box)
    exist_area = _bbox_area(exist_box)
    if cand_area <= 0 or exist_area <= 0:
        return False

    cov_candidate, cov_existing = _coverage_ratio(cand_box, exist_box)

    # Case 1: almost identical boxes.
    if cov_candidate >= containment_threshold and cov_existing >= containment_threshold:
        return True

    # Case 2: upper-body / partial-body box almost fully contained within a full-body box.
    if cov_candidate >= containment_threshold or cov_existing >= containment_threshold:
        smaller_box, larger_box = (cand_box, exist_box) if cand_area <= exist_area else (exist_box, cand_box)

        smaller_width = max(1.0, float(smaller_box[2]) - float(smaller_box[0]))
        smaller_height = max(1.0, float(smaller_box[3]) - float(smaller_box[1]))
        larger_height = max(1.0, float(larger_box[3]) - float(larger_box[1]))

        smaller_center_x = (float(smaller_box[0]) + float(smaller_box[2])) / 2.0
        larger_center_x = (float(larger_box[0]) + float(larger_box[2])) / 2.0
        x_center_gap = abs(smaller_center_x - larger_center_x)

        if (
            x_center_gap <= x_alignment_ratio * smaller_width
            and larger_height >= height_ratio_threshold * smaller_height
        ):
            return True

    return False


def suppress_duplicate_person_detections(
    detections: List[Tuple[float, float, float, float, float]],
) -> List[Tuple[float, float, float, float, float]]:
    """Drop nested duplicate person boxes before tracking.

    Some crowded scenes produce two boxes for one seated person:
    a full-body box plus a smaller torso/upper-body box. DeepSORT then starts
    two tracks for the same person. This filter removes the nested duplicate
    while keeping nearby real people who only partially overlap.
    """
    if len(detections) < 2:
        return detections

    ordered = sorted(
        detections,
        key=lambda det: (float(det[4]), _bbox_area(det[:4])),
        reverse=True,
    )

    filtered: List[Tuple[float, float, float, float, float]] = []
    suppressed = 0
    for detection in ordered:
        if any(_is_nested_duplicate(detection, kept) for kept in filtered):
            suppressed += 1
            continue
        filtered.append(detection)

    if suppressed:
        log.debug("Suppressed %d nested duplicate detection(s)", suppressed)
    return filtered


def parse_roi(roi_data: Optional[Union[str, List]]) -> Optional[List[List[float]]]:
    """
    Parse ROI data dari string JSON atau list
    Returns: List of points [[x1,y1], [x2,y2], ...] atau None
    """
    if not roi_data:
        return None
    
    # Jika sudah list, return langsung
    if isinstance(roi_data, list):
        return roi_data
    
    # Jika string, parse JSON
    if isinstance(roi_data, str):
        try:
            parsed = json.loads(roi_data)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError as e:
            log.warning("Failed to parse ROI JSON: %s", e)
            return None
    
    return None


def point_in_roi(roi: Optional[List[List[float]]], x: float, y: float) -> bool:
    """Check if point is inside ROI polygon"""
    if not roi or len(roi) < 3:
        return True  # ROI not set => whole frame
    poly = np.array(roi, dtype=np.int32)
    return cv2.pointPolygonTest(poly, (float(x), float(y)), False) >= 0
