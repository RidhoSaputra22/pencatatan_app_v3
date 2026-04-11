"""YOLO detection and ROI utilities — supports YOLOv5 (torch.hub) and Ultralytics (YOLOv8+)"""
import json
import warnings
from typing import Optional, List, Union
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
