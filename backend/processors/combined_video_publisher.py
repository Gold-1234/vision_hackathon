import asyncio
from typing import Any, Optional

import aiortc
import av
from vision_agents.core.processors import VideoProcessorPublisher
from vision_agents.core.utils.video_forwarder import VideoForwarder
from vision_agents.core.utils.video_track import QueuedVideoTrack

from .base import draw_bbox


class CombinedVideoPublisher(VideoProcessorPublisher):
    """
    Single publisher that merges overlays from multiple analysis processors
    and publishes one annotated video stream.
    """

    name = "combined_video_publisher"

    def __init__(
        self,
        object_processor: Any,
        toddler_processor: Optional[Any] = None,
        fps: float = 10.0,
    ) -> None:
        self.object_processor = object_processor
        self.toddler_processor = toddler_processor
        self.fps = float(fps)

        self._forwarder: Optional[VideoForwarder] = None
        self._owns_forwarder = False
        self._handler_registered = False
        self._processing_lock = asyncio.Lock()
        self._video_track = QueuedVideoTrack(width=1280, height=720, fps=max(1, int(self.fps)))

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

    @staticmethod
    def _draw_detection_list(frame, detections: list[dict[str, Any]], color=(0, 255, 0)):
        for det in detections:
            bbox = det.get("bbox")
            label = str(det.get("label", "object"))
            confidence = det.get("confidence")
            if bbox is None:
                continue
            if isinstance(confidence, (int, float)):
                text = f"{label} {float(confidence):.2f}"
            else:
                text = label
            frame = draw_bbox(frame, bbox, label=text, color=color)
        return frame

    async def _on_frame(self, frame: av.VideoFrame) -> None:
        if self._processing_lock.locked():
            return

        async with self._processing_lock:
            image_bgr = frame.to_ndarray(format="bgr24")
            annotated = image_bgr.copy()

            object_detections = []
            if hasattr(self.object_processor, "state"):
                object_detections = self.object_processor.state().get("detections", []) or []
            annotated = self._draw_detection_list(annotated, object_detections, color=(0, 255, 0))

            toddler_detections = []
            if self.toddler_processor is not None and hasattr(self.toddler_processor, "state"):
                toddler_detections = self.toddler_processor.state().get("detections", []) or []
            annotated = self._draw_detection_list(annotated, toddler_detections, color=(0, 165, 255))

            out_frame = av.VideoFrame.from_ndarray(annotated, format="bgr24")
            out_frame.pts = frame.pts
            out_frame.time_base = frame.time_base
            await self._video_track.add_frame(out_frame)

    def publish_video_track(self) -> aiortc.VideoStreamTrack:
        return self._video_track

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
        self._video_track.stop()
