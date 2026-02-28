import asyncio
import os
from typing import Any, Optional

import aiortc
import av
import numpy as np
from vision_agents.core.processors import VideoProcessor
from vision_agents.core.utils.video_forwarder import VideoForwarder


class FaceDetectionProcessor(VideoProcessor):
    """
    InsightFace-based face detection processor (analysis-only).
    """

    name = "face_detection"

    def __init__(
        self,
        fps: float = 2.0,
        model_name: str = "buffalo_s",
        det_size: tuple[int, int] = (640, 640),
        det_thresh: float = 0.5,
        providers: Optional[list[str]] = None,
    ) -> None:
        self.fps = float(fps)
        self.model_name = model_name
        self.det_size = det_size
        self.det_thresh = float(det_thresh)

        if providers is None:
            providers_env = os.getenv("INSIGHTFACE_PROVIDERS", "CPUExecutionProvider")
            providers = [p.strip() for p in providers_env.split(",") if p.strip()]

        # Import locally so the module is optional at runtime.
        from insightface.app import FaceAnalysis

        self.app = FaceAnalysis(name=self.model_name, providers=providers)
        # ctx_id: -1 for CPU, 0 for first GPU (CUDA).
        ctx_id = int(os.getenv("INSIGHTFACE_CTX_ID", "-1").strip() or -1)
        self.app.prepare(ctx_id=ctx_id, det_size=self.det_size, det_thresh=self.det_thresh)

        self.latest_detections: list[dict[str, Any]] = []

        self._forwarder: Optional[VideoForwarder] = None
        self._owns_forwarder = False
        self._handler_registered = False
        self._processing_lock = asyncio.Lock()

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
            detections = await asyncio.to_thread(self._detect, frame_bgr)
            self.latest_detections = detections

    def _detect(self, frame_bgr: np.ndarray) -> list[dict[str, Any]]:
        faces = self.app.get(frame_bgr)
        detections: list[dict[str, Any]] = []
        for face in faces:
            bbox = face.bbox.astype(int).tolist()
            if len(bbox) != 4:
                continue
            x1, y1, x2, y2 = bbox
            detections.append(
                {
                    "label": "face",
                    "confidence": float(face.det_score),
                    "bbox": (int(x1), int(y1), int(x2), int(y2)),
                }
            )
        return detections

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
