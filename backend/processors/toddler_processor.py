import asyncio
import logging
import os
import time
from typing import Any, Optional

import aiortc
import av
from roboflow import Roboflow
from vision_agents.core.processors import VideoProcessor
from vision_agents.core.utils.video_forwarder import VideoForwarder


DEFAULT_MODEL_ID = "toddler-detection-yxicj-sdfde/2"
ERROR_LOG_THROTTLE_SECONDS = 10.0
ALLOWED_CLASSES = {"toddler", "adult"}
TODDLER_MIN_CONFIDENCE = 0.8

logger = logging.getLogger(__name__)


class ToddlerProcessor(VideoProcessor):
    name = "toddler_processor"

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        api_key: Optional[str] = None,
        conf_threshold: float = 0.3,
        fps: int = 1,
    ) -> None:
        key = api_key or os.getenv("ROBOFLOW_API_KEY")
        if not key:
            raise ValueError("ROBOFLOW_API_KEY is required for ToddlerProcessor")

        self.model_id = model_id
        self.conf_threshold = conf_threshold
        self.fps = max(1, int(fps))

        project_name, version = self._parse_model_id(model_id)
        self._rf_confidence = max(1, int(conf_threshold * 100))
        self._rf_overlap = 30

        rf = Roboflow(api_key=key)
        self.model = rf.workspace().project(project_name).version(version).model

        self._forwarder: Optional[VideoForwarder] = None
        self._owns_forwarder = False
        self._handler_registered = False
        self._processing_lock = asyncio.Lock()
        self._last_error_log_ts = 0.0

        self.toddler_present: bool = False
        self.last_predictions: list[dict[str, Any]] = []

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
            image_bgr = frame.to_ndarray(format="bgr24")
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
                    logger.exception("Toddler inference failed: %s", error)
                    self._last_error_log_ts = now
                return

            predictions = result_json.get("predictions", []) if isinstance(result_json, dict) else []
            if not isinstance(predictions, list):
                predictions = []

            detections: list[dict[str, Any]] = []
            for pred in predictions:
                if not isinstance(pred, dict):
                    continue
                class_name = str(pred.get("class", "Unknown")).strip() or "Unknown"
                class_lower = class_name.lower()
                confidence = self._safe_float(pred.get("confidence"))
                if class_lower not in ALLOWED_CLASSES:
                    continue
                min_conf = self.conf_threshold
                if class_lower == "toddler":
                    min_conf = max(min_conf, TODDLER_MIN_CONFIDENCE)
                if confidence is None or confidence < min_conf:
                    continue
                bbox = self._prediction_to_bbox(pred)
                if bbox is None:
                    continue
                detections.append(
                    {
                        "label": class_name,
                        "confidence": confidence,
                        "bbox": bbox,
                    }
                )

            self.last_predictions = detections
            self.toddler_present = any(det["label"].lower() == "toddler" for det in detections)

    def state(self) -> dict[str, Any]:
        return {
            "toddler_present": self.toddler_present,
            "detections": self.last_predictions,
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
