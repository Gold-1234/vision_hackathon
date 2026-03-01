import asyncio
from typing import Any, Optional

import aiortc
import av
import cv2
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
        fall_processor: Optional[Any] = None,
        danger_guard: Optional[Any] = None,
        zone_guard: Optional[Any] = None,
        face_processor: Optional[Any] = None,
        fps: float = 10.0,
    ) -> None:
        self.object_processor = object_processor
        self.toddler_processor = toddler_processor
        self.fall_processor = fall_processor
        self.danger_guard = danger_guard
        self.zone_guard = zone_guard
        self.face_processor = face_processor
        self.fps = float(fps)

        self._forwarder: Optional[VideoForwarder] = None
        self._owns_forwarder = False
        self._handler_registered = False
        self._processing_lock = asyncio.Lock()
        self._video_track = QueuedVideoTrack(width=1280, height=720, fps=max(1, int(self.fps)))
        self._latest_jpeg: Optional[bytes] = None
        self._jpeg_lock = asyncio.Lock()

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

            if self.fall_processor is not None and hasattr(self.fall_processor, "state"):
                fall_state = self.fall_processor.state()
                if fall_state.get("fall_present"):
                    # Find the bounding box for the falling person
                    for det in fall_state.get("detections", []):
                        if det.get("is_falling", False):
                            annotated = draw_bbox(
                                annotated,
                                det.get("bbox", (0, 0, 0, 0)),
                                label="FALL DETECTED!",
                                color=(0, 0, 255),
                                thickness=3,
                            )

            if self.danger_guard is not None and hasattr(self.danger_guard, "state"):
                danger_state = self.danger_guard.state()
                if danger_state.get("danger_present"):
                    alert = danger_state.get("alert") or {}
                    toddler_bbox = alert.get("toddler_bbox")
                    object_bbox = alert.get("object_bbox")
                    object_label = str(alert.get("object_label", "danger"))
                    reason = str(alert.get("reason", "")).strip()

                    if toddler_bbox is not None:
                        annotated = draw_bbox(
                            annotated,
                            toddler_bbox,
                            label="TODDLER AT RISK",
                            color=(0, 0, 255),
                            thickness=3,
                        )
                    if object_bbox is not None:
                        label = f"DANGER: {object_label}"
                        if reason:
                            label = f"{label} | {reason}"
                        annotated = draw_bbox(
                            annotated,
                            object_bbox,
                            label=label,
                            color=(0, 0, 255),
                            thickness=3,
                        )

            if self.zone_guard is not None and hasattr(self.zone_guard, "state"):
                zone_state = self.zone_guard.state()
                zone_bbox = zone_state.get("zone_bbox")
                baby_point = zone_state.get("baby_point")
                status = str(zone_state.get("status", "ZONE"))
                near_count = int(zone_state.get("near_count", 0) or 0)
                near_trigger_count = int(zone_state.get("near_trigger_count", 0) or 0)
                crossed_recent = bool(zone_state.get("crossed_recent", False))
                alert_active = bool(zone_state.get("alert_active", False))

                if zone_bbox is not None:
                    zone_color = (0, 0, 255)
                    annotated = draw_bbox(
                        annotated,
                        zone_bbox,
                        label="STAIRS ZONE",
                        color=zone_color,
                        thickness=2 if not alert_active else 3,
                    )
                if isinstance(baby_point, tuple) and len(baby_point) == 2:
                    cv2.circle(annotated, (int(baby_point[0]), int(baby_point[1])), 6, (255, 255, 0), -1)
                    cv2.circle(annotated, (int(baby_point[0]), int(baby_point[1])), 9, (0, 0, 0), 2)
                if crossed_recent:
                    status = "CROSSED STAIRS BOUNDARY"
                if near_trigger_count > 0:
                    status = f"{status} ({near_count}/{near_trigger_count})"
                cv2.putText(
                    annotated,
                    status,
                    (20, 36),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 0, 255) if (alert_active or crossed_recent) else (0, 200, 255),
                    2,
                    cv2.LINE_AA,
                )

            face_detections = []
            if self.face_processor is not None and hasattr(self.face_processor, "state"):
                face_detections = self.face_processor.state().get("detections", []) or []
            annotated = self._draw_detection_list(annotated, face_detections, color=(255, 255, 0))

            out_frame = av.VideoFrame.from_ndarray(annotated, format="bgr24")
            out_frame.pts = frame.pts
            out_frame.time_base = frame.time_base
            await self._video_track.add_frame(out_frame)

            ok, encoded = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ok:
                async with self._jpeg_lock:
                    self._latest_jpeg = encoded.tobytes()

    def publish_video_track(self) -> aiortc.VideoStreamTrack:
        return self._video_track

    async def get_latest_jpeg(self) -> Optional[bytes]:
        async with self._jpeg_lock:
            return self._latest_jpeg

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
