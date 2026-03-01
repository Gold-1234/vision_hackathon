import asyncio
from collections import deque
import logging
import os
import time
from typing import Any, Optional

import aiortc
import av
from roboflow import Roboflow
from vision_agents.core.processors import VideoProcessor
from vision_agents.core.utils.video_forwarder import VideoForwarder

from events.detection_events import FallDetectedEvent


DEFAULT_MODEL_ID = "fall-detection-ca3o8/4"
ERROR_LOG_THROTTLE_SECONDS = 10.0

logger = logging.getLogger(__name__)


class FallDetectionProcessor(VideoProcessor):
    """
    Roboflow-based fall detection processor.
    """

    name = "fall_detection"

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        api_key: Optional[str] = None,
        conf_threshold: float = 0.7,
        overlap: int = 30,
        fps: int = 2,
        fall_window_size: int = 5,
        required_fall_frames: int = 5,
        require_toddler_for_processing: bool = True,
    ) -> None:
        key = api_key or os.getenv("ROBOFLOW_API_KEY") or os.getenv("RF_FALL_API_KEY")
        if not key:
            raise ValueError("ROBOFLOW_API_KEY (or RF_FALL_API_KEY) is required for FallDetectionProcessor2")

        self.model_id = model_id
        self.conf_threshold = float(conf_threshold)
        self.overlap = int(overlap)
        self.fps = max(1, int(fps))
        self.fall_window_size = max(1, int(fall_window_size))
        self.required_fall_frames = max(1, int(required_fall_frames))
        self.required_fall_frames = min(self.required_fall_frames, self.fall_window_size)
        self.require_toddler_for_processing = bool(require_toddler_for_processing)

        project_name, version = self._parse_model_id(model_id)
        self._rf_confidence = max(1, int(self.conf_threshold * 100))
        self._rf_overlap = max(0, int(self.overlap))

        rf = Roboflow(api_key=key)
        self.model = rf.workspace().project(project_name).version(version).model

        self._forwarder: Optional[VideoForwarder] = None
        self._owns_forwarder = False
        self._handler_registered = False
        self._processing_lock = asyncio.Lock()
        self._last_error_log_ts = 0.0
        self._last_log_ts = 0.0
        self._log_interval_seconds = 2.0
        self._frame_number = 0
        self._fall_window: deque[bool] = deque(maxlen=self.fall_window_size)

        self.latest_detections: list[dict[str, Any]] = []
        self.latest_event: Optional[FallDetectedEvent] = None
        self.fall_present: bool = False
        self.toddler_processor: Optional[Any] = None

    def bind_toddler_processor(self, toddler_processor: Optional[Any]) -> None:
        self.toddler_processor = toddler_processor

    def _toddler_present(self) -> bool:
        if self.toddler_processor is None or not hasattr(self.toddler_processor, "state"):
            return False
        try:
            state = self.toddler_processor.state() or {}
        except Exception:
            return False
        if bool(state.get("toddler_present", False)):
            return True
        detections = state.get("detections", []) or []
        for det in detections:
            if str(det.get("label", "")).strip().lower() == "toddler":
                return True
        return False

    @staticmethod
    def _parse_model_id(model_id: str) -> tuple[str, int]:
        if "/" not in model_id:
            raise ValueError("model_id must be in '<project>/<version>' format.")
        project, version_str = model_id.rsplit("/", 1)
        try:
            return project, int(version_str)
        except ValueError as error:
            raise ValueError("model_id version must be an integer.") from error

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _prediction_to_bbox(cls, pred: dict[str, Any]) -> Optional[tuple[int, int, int, int]]:
        x = cls._safe_float(pred.get("x"))
        y = cls._safe_float(pred.get("y"))
        width = cls._safe_float(pred.get("width"))
        height = cls._safe_float(pred.get("height"))
        if None in (x, y, width, height):
            return None
        if width <= 0 or height <= 0:
            return None
        x1 = int(round(x - width / 2.0))
        y1 = int(round(y - height / 2.0))
        x2 = int(round(x + width / 2.0))
        y2 = int(round(y + height / 2.0))
        return (x1, y1, x2, y2)

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
                fps=max(1.0, float(self.fps)),
                name=f"{self.name}_forwarder",
            )
            await self._forwarder.start()
            self._owns_forwarder = True

        self._forwarder.add_frame_handler(
            self._on_frame,
            fps=float(self.fps),
            name=f"{self.name}_handler",
        )
        self._handler_registered = True

    async def _on_frame(self, frame: av.VideoFrame) -> None:
        if self._processing_lock.locked():
            return

        async with self._processing_lock:
            if self.require_toddler_for_processing and not self._toddler_present():
                self.latest_detections = []
                self.fall_present = False
                self.latest_event = None
                self._fall_window.clear()
                return

            image_bgr = frame.to_ndarray(format="bgr24")
            frame_number = self._frame_number
            self._frame_number += 1

            try:
                result = await asyncio.to_thread(
                    self.model.predict,
                    image_bgr,
                    confidence=self._rf_confidence,
                    overlap=self._rf_overlap,
                )
                result_json = result.json()
            except Exception as error:
                now = time.time()
                if now - self._last_error_log_ts >= ERROR_LOG_THROTTLE_SECONDS:
                    logger.exception("Fall detection inference failed: %s", error)
                    self._last_error_log_ts = now
                return

            predictions = result_json.get("predictions", []) if isinstance(result_json, dict) else []
            if not isinstance(predictions, list):
                predictions = []

            detections: list[dict[str, Any]] = []
            fall_detected = False
            highest_conf_fall = 0.0
            fall_bbox = (0, 0, 0, 0)

            for pred in predictions:
                if not isinstance(pred, dict):
                    continue
                class_name = str(pred.get("class", "Unknown")).strip() or "Unknown"
                confidence = self._safe_float(pred.get("confidence"))
                if confidence is None:
                    continue
                if confidence < self.conf_threshold:
                    continue
                bbox = self._prediction_to_bbox(pred)
                if bbox is None:
                    continue

                normalized_class = class_name.strip().lower().replace("_", "-").replace(" ", "-")
                is_falling = normalized_class in {"fall-detected", "fall"}
                if is_falling:
                    fall_detected = True
                    if confidence > highest_conf_fall:
                        highest_conf_fall = confidence
                        fall_bbox = bbox

                detections.append(
                    {
                        "label": class_name,
                        "confidence": confidence,
                        "bbox": bbox,
                        "is_falling": is_falling,
                    }
                )

            self.latest_detections = detections
            self._fall_window.append(fall_detected)
            fall_votes = sum(1 for item in self._fall_window if item)
            self.fall_present = (
                len(self._fall_window) == self.fall_window_size
                and fall_votes >= self.required_fall_frames
            )
            now = time.time()
            if now - self._last_log_ts >= self._log_interval_seconds:
                logger.info(
                    "fall2 | fall_present=%s raw=%s votes=%d/%d detections=%d best_conf=%.3f",
                    self.fall_present,
                    fall_detected,
                    fall_votes,
                    self.fall_window_size,
                    len(detections),
                    highest_conf_fall,
                )
                self._last_log_ts = now
            if self.fall_present:
                self.latest_event = FallDetectedEvent(
                    frame_number=frame_number,
                    confidence=highest_conf_fall,
                    bbox=fall_bbox,
                )
            else:
                self.latest_event = None

    def state(self) -> dict[str, Any]:
        return {
            "detections": self.latest_detections,
            "fall_present": self.fall_present,
            "fall_window_votes": sum(1 for item in self._fall_window if item),
            "fall_window_size": self.fall_window_size,
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
