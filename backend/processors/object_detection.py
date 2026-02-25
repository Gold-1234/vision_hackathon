import asyncio
from typing import Any, Optional

import aiortc
import av
import numpy as np
from ultralytics import YOLO
from vision_agents.core.processors import VideoProcessor
from vision_agents.core.utils.video_forwarder import VideoForwarder

from events.detection_events import ObjectDetectedEvent
from .base import draw_bbox, format_yolo_detections

EXCLUDED_YOLO_LABELS = {"person"}


class ObjectDetectionProcessor(VideoProcessor):
    """
    YOLO object detection processor (analysis-only).
    """

    name = "object_detection"

    def __init__(
        self,
        fps: float = 3.0,
        model_path: str = "yolo11n.pt",
        confidence_threshold: float = 0.5,
    ) -> None:
        self.fps = float(fps)
        self.confidence_threshold = confidence_threshold
        self.model_path = model_path

        print(f"Loading YOLO model from {model_path}...")
        self.model = YOLO(model_path)
        print("YOLO model loaded.")

        self.latest_detections: list[dict[str, Any]] = []
        self.latest_event: Optional[ObjectDetectedEvent] = None

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
        # Rebind handler if process_video is called again (e.g., track switch).
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
        # Skip frame if previous inference is still running.
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
            self.latest_event = ObjectDetectedEvent(
                frame_number=frame_number,
                objects=detections,
            )

    def _detect(
        self,
        frame_number: int,
        frame_bgr: np.ndarray,
    ) -> list[dict[str, Any]]:
        _ = frame_number
        results = self.model(frame_bgr, verbose=False, conf=self.confidence_threshold)
        detections = format_yolo_detections(results)
        filtered = [
            det for det in detections
            if str(det.get("label", "")).strip().lower() not in EXCLUDED_YOLO_LABELS
        ]
        return filtered

    def process_frame(self, frame_number: int, frame: np.ndarray) -> np.ndarray:
        """
        Backwards-compatible synchronous API used by local_runner.py.
        """
        detections = self._detect(frame_number, frame)
        annotated_frame = frame.copy()
        for det in detections:
            label = f"{det['label']} {det['confidence']:.2f}"
            annotated_frame = draw_bbox(annotated_frame, det["bbox"], label=label)
        self.latest_detections = detections
        self.latest_event = ObjectDetectedEvent(
            frame_number=frame_number,
            objects=detections,
        )
        return annotated_frame

    def state(self) -> dict[str, Any]:
        return {"detections": self.latest_detections}

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
