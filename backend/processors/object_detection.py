# RANK: 4 - Core ML processor (YOLO11n) to find objects, draw bounding boxes, and emit detection events.

import cv2
import numpy as np
from ultralytics import YOLO

# Local imports
from .base import draw_bbox, format_yolo_detections
from events.detection_events import ObjectDetectedEvent

# In a real Vision Agents plugin, this would inherit from VideoProcessorPublisher
# For now, we will create a standalone class that handles frames.

class ObjectDetectionProcessor:
    """
    Runs YOLO11n object detection on frames.
    Optionally draws bounding boxes and emits ObjectDetectedEvent.
    """
    name = "object_detection"

    def __init__(self, fps: int = 3, model_path: str = "yolo11n.pt", confidence_threshold: float = 0.5):
        self.fps = fps
        self.confidence_threshold = confidence_threshold
        
        # Load the model directly. Ultralytics will auto-download yolo11n.pt if missing.
        print(f"Loading YOLO model from {model_path}...")
        self.model = YOLO(model_path)
        print("YOLO model loaded.")
        
        # Shared dict for other processors to reference (per the PLAN.md)
        self.latest_detections = []

    def process_frame(self, frame_number: int, frame: np.ndarray) -> np.ndarray:
        """
        Run inference on a single frame, draw boxes, and return the annotated frame.
        """
        # Run YOLO inference
        results = self.model(frame, verbose=False, conf=self.confidence_threshold)
        
        # Format results using our base.py helper
        detections = format_yolo_detections(results)
        self.latest_detections = detections
        
        # Draw bounding boxes on the frame
        annotated_frame = frame.copy()
        for det in detections:
            label = f"{det['label']} {det['confidence']:.2f}"
            annotated_frame = draw_bbox(annotated_frame, det['bbox'], label=label)

        # In a full system, we would emit the event to the Event System here:
        # event = ObjectDetectedEvent(frame_number=frame_number, objects=detections)
        # emit_event(event)

        return annotated_frame

