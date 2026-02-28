import asyncio
from typing import Any, Optional

import aiortc
import av
import numpy as np
from ultralytics import YOLO
from vision_agents.core.processors import VideoProcessor
from vision_agents.core.utils.video_forwarder import VideoForwarder

from events.detection_events import FallDetectedEvent
from .base import draw_bbox


class FallDetectionProcessor(VideoProcessor):
    """
    YOLO pose-based fall detection processor.
    """

    name = "fall_detection"

    def __init__(
        self,
        fps: float = 2.0,
        model_path: str = "yolo11n-pose.pt",
        confidence_threshold: float = 0.5,
        fall_ratio_threshold: float = 1.2, # width / height ratio to trigger fall
    ) -> None:
        self.fps = float(fps)
        self.confidence_threshold = confidence_threshold
        self.fall_ratio_threshold = fall_ratio_threshold
        self.model_path = model_path

        print(f"Loading YOLO Pose model from {model_path}...")
        self.model = YOLO(model_path)
        print("YOLO Pose model loaded.")

        self.latest_detections: list[dict[str, Any]] = []
        self.latest_event: Optional[FallDetectedEvent] = None
        self.fall_present: bool = False

        self._forwarder: Optional[VideoForwarder] = None
        self._owns_forwarder = False
        self._handler_registered = False
        self._processing_lock = asyncio.Lock()
        self._frame_number = 0

    async def process_video(
        self,
        track: aiortc.VideoStreamTrack,
        participant_id: Optional[str],
        shared_forwarder: Optional[VideoForwarder] = None,
    ) -> None:
        _ = participant_id
        if self._forwarder is not None and self._handler_registered:
            await self._forwarder.remove_frame_handler(self._on_frame)
            if self._owns_forwarder:
                await self._forwarder.stop()
            self._handler_registered = False
            self._owns_forwarder = False

        self._forwarder = shared_forwarder
        if self._forwarder is None:
            self._forwarder = VideoForwarder(
                input_track=track,
                max_buffer=5,
                fps=max(1.0, self.fps),
                name=f"{self.name}_forwarder",
            )
            await self._forwarder.start()
            self._owns_forwarder = True

        self._forwarder.add_frame_handler(
            self._on_frame,
            fps=self.fps,
            name=f"{self.name}_handler",
        )
        self._handler_registered = True

    async def _on_frame(self, frame: av.VideoFrame) -> None:
        if self._processing_lock.locked():
            return

        async with self._processing_lock:
            frame_bgr = frame.to_ndarray(format="bgr24")
            frame_number = self._frame_number
            self._frame_number += 1
            detections = await asyncio.to_thread(
                self._detect,
                frame_number,
                frame_bgr,
            )

            self.latest_detections = detections
            
            # Check if any detected person is falling
            fall_detected = False
            highest_conf_fall = 0.0
            fall_bbox = (0, 0, 0, 0)

            for det in detections:
                if det.get("is_falling", False):
                    fall_detected = True
                    if det["confidence"] > highest_conf_fall:
                        highest_conf_fall = det["confidence"]
                        fall_bbox = det["bbox"]

            self.fall_present = fall_detected
            if fall_detected:
                self.latest_event = FallDetectedEvent(
                    frame_number=frame_number,
                    confidence=highest_conf_fall,
                    bbox=fall_bbox,
                )
            else:
                self.latest_event = None

    def _detect(
        self,
        frame_number: int,
        frame_bgr: np.ndarray,
    ) -> list[dict[str, Any]]:
        _ = frame_number
        results = self.model(frame_bgr, verbose=False, conf=self.confidence_threshold)
        detections = []

        if results and len(results) > 0:
            result = results[0]
            if result.boxes and result.keypoints:
                for box, keypoints in zip(result.boxes, result.keypoints):
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    
                    # Pose keypoints: [17, 2] or [17, 3] usually
                    kpts = keypoints.data[0].tolist() if keypoints.data is not None else []
                    
                    is_falling = False
                    
                    # Bounding box aspect ratio check
                    width = max(1, x2 - x1)
                    height = max(1, y2 - y1)
                    ratio = width / height
                    
                    if ratio > self.fall_ratio_threshold:
                        is_falling = True
                    
                    # Further keypoint analysis can be added here
                    # e.g. check if head keypoints are lower than hip keypoints
                    if len(kpts) >= 13:
                        # 0: nose, 11: left_hip, 12: right_hip
                        nose_y = kpts[0][1] if len(kpts[0]) > 1 else 0
                        l_hip_y = kpts[11][1] if len(kpts[11]) > 1 else 0
                        r_hip_y = kpts[12][1] if len(kpts[12]) > 1 else 0
                        
                        # Only check if points are valid (y > 0)
                        if nose_y > 0 and l_hip_y > 0 and r_hip_y > 0:
                            avg_hip_y = (l_hip_y + r_hip_y) / 2
                            # in image coords, higher y means lower visually
                            if nose_y > avg_hip_y: 
                                is_falling = True
                    
                    detections.append({
                        "label": "person", 
                        "confidence": conf,
                        "bbox": (x1, y1, x2, y2),
                        "is_falling": is_falling,
                        "keypoints": kpts
                    })

        return detections

    def state(self) -> dict[str, Any]:
        return {
            "detections": self.latest_detections,
            "fall_present": self.fall_present
        }

    async def stop_processing(self) -> None:
        if self._forwarder is not None and self._handler_registered:
            await self._forwarder.remove_frame_handler(self._on_frame)
        if self._forwarder is not None and self._owns_forwarder:
            await self._forwarder.stop()
        self._handler_registered = False
        self._forwarder = None
        self._owns_forwarder = False

    async def close(self) -> None:
        await self.stop_processing()
