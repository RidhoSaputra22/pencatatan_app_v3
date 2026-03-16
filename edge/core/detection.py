"""YOLOv5 detection and ROI utilities"""
import json
import warnings
from typing import Optional, List, Union
import numpy as np
import cv2

from .config import CONF_TH, IOU_TH, DEVICE, WEIGHTS, REPO

# Check Intel XPU availability
INTEL_XPU_AVAILABLE = False
try:
    import intel_extension_for_pytorch as ipex
    import torch
    if hasattr(torch, 'xpu') and torch.xpu.is_available():
        INTEL_XPU_AVAILABLE = True
        print(f"[detection] Intel XPU available: {torch.xpu.get_device_name(0)}")
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
            print(f"[detection] Warning: Requested device '{DEVICE}' not available, falling back...")
    
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
    print(f"[detection] Loading YOLOv5 model on device: {device}")
    
    if REPO and WEIGHTS:
        model = torch.hub.load(REPO, "custom", path=WEIGHTS, source="local")
    elif WEIGHTS and not REPO:
        model = torch.hub.load("ultralytics/yolov5", "custom", path=WEIGHTS)
    else:
        model = torch.hub.load("ultralytics/yolov5", "yolov5s", pretrained=True)

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
            print("[detection] Model optimized with Intel Extension for PyTorch")
        except Exception as e:
            print(f"[detection] Warning: IPEX optimization failed: {e}")
    
    print(f"[detection] YOLOv5 model loaded successfully on {device}")
    return model


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
            print(f"[edge] Failed to parse ROI JSON: {e}")
            return None
    
    return None


def point_in_roi(roi: Optional[List[List[float]]], x: float, y: float) -> bool:
    """Check if point is inside ROI polygon"""
    if not roi or len(roi) < 3:
        return True  # ROI not set => whole frame
    poly = np.array(roi, dtype=np.int32)
    return cv2.pointPolygonTest(poly, (float(x), float(y)), False) >= 0
