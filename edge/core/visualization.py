"""Visualization utilities for drawing on frames"""
from typing import Optional, List, Dict, Any
import numpy as np
import cv2

from .tracker import Track


def draw_roi_polygon(frame: np.ndarray, roi: Optional[List[List[float]]]):
    """Draw ROI polygon on frame"""
    if not roi or len(roi) < 3:
        return
    poly = np.array(roi, dtype=np.int32)
    cv2.polylines(frame, [poly], True, (255, 255, 0), 2)


def draw_bounding_boxes(frame: np.ndarray, tracks: Dict[int, Track], visitor_states: Dict[int, Dict[str, Any]]):
    """
    Draw bounding boxes dengan status visitor pada frame
    States: NEW/EXISTING (unique visitor today), IN/OUT/IN_ROI (direction)
    Hanya menggambar box untuk track yang berada di dalam ROI
    """
    for tid, tr in tracks.items():
        if tr.disappeared > 0:
            continue  # Skip tracks yang sedang disappeared
        
        # Hanya gambar box untuk track yang berada di dalam ROI
        if not tr.in_roi:
            continue
        
        x1, y1, x2, y2 = tr.bbox
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        
        # Determine color dan status
        state = visitor_states.get(tid, {})
        is_new = state.get('is_new', True)
        direction = state.get('direction', 'IN_ROI')
        person_type = state.get('person_type', 'CUSTOMER')
        employee_name = state.get('employee_name') or state.get('employee_code')
        
        if person_type == "EMPLOYEE":
            color = (255, 0, 0)
            status_text = "EMPLOYEE"
        elif person_type == "UNKNOWN":
            color = (0, 255, 255)
            status_text = "VERIFY"
        elif is_new:
            color = (0, 255, 0)  # Green for NEW
            status_text = "NEW"
        else:
            color = (255, 165, 0)  # Orange for EXISTING
            status_text = "EXISTING"
        
        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Prepare label
        label = f"ID:{tid} {status_text}"
        if employee_name and person_type == "EMPLOYEE":
            label += f" {employee_name}"
        if direction:
            label += f" [{direction}]"
        
        # Draw label background
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1 - 20), (x1 + w + 10, y1), color, -1)
        
        # Draw label text
        cv2.putText(frame, label, (x1 + 5, y1 - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def draw_info_overlay(frame: np.ndarray, info_lines: List[str], show_live_indicator: bool = True):
    """Draw info text overlay on frame"""
    y_offset = 30
    for line in info_lines:
        cv2.putText(frame, line, (10, y_offset), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
        y_offset += 30
    
    # Draw LIVE indicator
    if show_live_indicator:
        status_color = (0, 255, 0)
        cv2.circle(frame, (frame.shape[1] - 30, 30), 10, status_color, -1)
        cv2.putText(frame, "LIVE", (frame.shape[1] - 80, 35), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 1, cv2.LINE_AA)
