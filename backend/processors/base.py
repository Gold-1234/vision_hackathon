"""
Shared utilities for all video processors.

Every processor can import these helpers instead of reimplementing
common drawing, distance, and geometry logic.
"""

import cv2
import numpy as np
from typing import Sequence


# ── Drawing helpers ──────────────────────────────────────────────

def draw_bbox(
    frame: np.ndarray,
    bbox: tuple[int, int, int, int],
    label: str = "",
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
    font_scale: float = 0.6,
) -> np.ndarray:
    """
    Draw a bounding box with an optional label on the frame.

    Args:
        frame: RGB numpy array (H, W, 3)
        bbox: (x1, y1, x2, y2) top-left and bottom-right corners
        label: Text label to show above the box
        color: BGR color tuple
        thickness: Line thickness
        font_scale: Label font size

    Returns:
        The frame with the box drawn (modified in-place)
    """
    x1, y1, x2, y2 = map(int, bbox)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

    if label:
        # Background for text readability
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 4, y1), color, -1)
        cv2.putText(
            frame, label, (x1 + 2, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 1, cv2.LINE_AA,
        )

    return frame


def draw_zone(
    frame: np.ndarray,
    polygon: Sequence[tuple[int, int]],
    color: tuple[int, int, int] = (0, 0, 255),
    alpha: float = 0.3,
    label: str = "",
) -> np.ndarray:
    """
    Draw a semi-transparent polygon zone overlay on the frame.

    Args:
        frame: RGB numpy array
        polygon: List of (x, y) vertex points
        color: BGR color
        alpha: Transparency (0=invisible, 1=opaque)
        label: Optional zone label

    Returns:
        Frame with zone overlay
    """
    overlay = frame.copy()
    pts = np.array(polygon, dtype=np.int32)
    cv2.fillPoly(overlay, [pts], color)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)

    if label and len(polygon) > 0:
        cx = int(np.mean([p[0] for p in polygon]))
        cy = int(np.mean([p[1] for p in polygon]))
        cv2.putText(
            frame, label, (cx - 20, cy),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA,
        )

    return frame


# ── Geometry helpers ─────────────────────────────────────────────

def bbox_center(bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    """Return the center point (cx, cy) of a bounding box (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def calculate_distance(
    bbox1: tuple[int, int, int, int],
    bbox2: tuple[int, int, int, int],
) -> float:
    """
    Calculate pixel distance between the centers of two bounding boxes.
    """
    c1 = bbox_center(bbox1)
    c2 = bbox_center(bbox2)
    return float(np.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2))


def is_inside_zone(
    point: tuple[int, int],
    polygon: Sequence[tuple[int, int]],
) -> bool:
    """
    Check if a point is inside a polygon using OpenCV's pointPolygonTest.

    Returns:
        True if the point is inside or on the edge of the polygon
    """
    pts = np.array(polygon, dtype=np.float32)
    result = cv2.pointPolygonTest(pts, (float(point[0]), float(point[1])), False)
    return result >= 0


def bbox_overlap_ratio(
    bbox1: tuple[int, int, int, int],
    bbox2: tuple[int, int, int, int],
) -> float:
    """
    Calculate the IoU (Intersection over Union) of two bounding boxes.
    """
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2])
    y2 = min(bbox1[3], bbox2[3])

    if x2 <= x1 or y2 <= y1:
        return 0.0

    intersection = (x2 - x1) * (y2 - y1)
    area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0


# ── Detection result helpers ────────────────────────────────────

def format_yolo_detections(results) -> list[dict]:
    """
    Convert YOLO results to a standardized list of detection dicts.

    Returns:
        List of dicts with keys: label, confidence, bbox (x1,y1,x2,y2), class_id
    """
    detections = []

    if results and len(results) > 0:
        result = results[0]  # First image result
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append({
                "label": result.names[int(box.cls[0])],
                "confidence": float(box.conf[0]),
                "bbox": (int(x1), int(y1), int(x2), int(y2)),
                "class_id": int(box.cls[0]),
            })

    return detections
