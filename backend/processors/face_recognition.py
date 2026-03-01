import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Optional

import aiortc
import av
import cv2
import numpy as np
from vision_agents.core.processors import VideoProcessor
from vision_agents.core.utils.video_forwarder import VideoForwarder


class FaceRecognitionProcessor(VideoProcessor):
    """
    InsightFace-based face detection + recognition (analysis-only).
    Loads known faces once at startup from a directory of images.
    """

    name = "face_recognition"

    def __init__(
        self,
        fps: float = 2.0,
        model_name: str = "buffalo_s",
        det_size: tuple[int, int] = (640, 640),
        det_thresh: float = 0.35,
        providers: Optional[list[str]] = None,
        gallery_dir: str = "data/known_faces",
        match_threshold: float = 0.35,
    ) -> None:
        self.fps = float(fps)
        self.model_name = model_name
        self.det_size = det_size
        self.det_thresh = float(det_thresh)
        self.match_threshold = float(match_threshold)
        self._logger = logging.getLogger(__name__)

        if providers is None:
            providers_env = os.getenv("INSIGHTFACE_PROVIDERS", "CPUExecutionProvider")
            providers = [p.strip() for p in providers_env.split(",") if p.strip()]

        from insightface.app import FaceAnalysis

        self.app = FaceAnalysis(name=self.model_name, providers=providers)
        ctx_id = int(os.getenv("INSIGHTFACE_CTX_ID", "-1").strip() or -1)
        self.app.prepare(ctx_id=ctx_id, det_size=self.det_size, det_thresh=self.det_thresh)

        self.gallery_dir = Path(gallery_dir)
        self.known_embeddings: dict[str, list[np.ndarray]] = {}
        self.known_embeddings_by_call: dict[str, dict[str, list[np.ndarray]]] = {}
        self.active_call_id: Optional[str] = None
        self._load_gallery()

        self.latest_detections: list[dict[str, Any]] = []
        self.unknown_detected: bool = False
        self.last_unknown_ts: Optional[float] = None
        self._last_log_ts: float = 0.0
        self._log_interval_seconds: float = 2.0

        self._forwarder: Optional[VideoForwarder] = None
        self._owns_forwarder = False
        self._handler_registered = False
        self._processing_lock = asyncio.Lock()

    def _load_gallery(self) -> None:
        if not self.gallery_dir.exists():
            self._logger.warning(
                "FaceRecognition: gallery base dir not found: %s",
                self.gallery_dir,
            )
            return
        
    

        exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        # Load call-specific galleries from subdirectories (one per call_id).
        for subdir in sorted([p for p in self.gallery_dir.iterdir() if p.is_dir()]):
            call_id = subdir.name.strip()
            if not call_id:
                continue
            call_gallery: dict[str, list[np.ndarray]] = {}
            self._load_gallery_from_dir(subdir, call_gallery)
            if call_gallery:
                self.known_embeddings_by_call[call_id] = call_gallery
                self._logger.info(
                    "FaceRecognition: loaded %d identities for call_id=%s",
                    sum(len(v) for v in call_gallery.values()),
                    call_id,
                )

        if not self.known_embeddings_by_call:
            self._logger.warning(
                "FaceRecognition: no call galleries loaded under %s",
                self.gallery_dir,
            )

    def _load_gallery_from_dir(
        self,
        directory: Path,
        target: dict[str, list[np.ndarray]],
    ) -> None:
        exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        loaded = 0
        for path in sorted(directory.glob("*")):
            if path.suffix.lower() not in exts:
                continue
            name = path.stem.strip()
            if not name:
                continue
            image = cv2.imread(str(path))
            if image is None:
                self._logger.warning("FaceRecognition: failed to read image: %s", path)
                continue

            faces = self.app.get(image)
            if not faces:
                self._logger.warning("FaceRecognition: no face found in image: %s", path)
                continue

            best = max(
                faces,
                key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
            )
            emb = np.asarray(best.embedding, dtype=np.float32)
            emb = self._normalize(emb)
            target.setdefault(name, []).append(emb)
            loaded += 1

        if loaded == 0:
            self._logger.info("FaceRecognition: no valid images in %s", directory)

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        denom = float(np.linalg.norm(vec) + 1e-8)
        return vec / denom

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))

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
        unknown_seen = False
        for face in faces:
            bbox = face.bbox.astype(int).tolist()
            if len(bbox) != 4:
                continue
            x1, y1, x2, y2 = bbox
            name, score = self._match_face(face)
            if name == "unknown":
                unknown_seen = True
            detections.append(
                {
                    "label": name,
                    "confidence": score,
                    "bbox": (int(x1), int(y1), int(x2), int(y2)),
                }
            )
        if unknown_seen:
            import time

            self.unknown_detected = True
            self.last_unknown_ts = time.time()
        import time

        now = time.time()
        if now - self._last_log_ts >= self._log_interval_seconds:
            self._logger.info(
                "face-recognition | faces=%d unknown_seen=%s active_call_id=%s",
                len(detections),
                unknown_seen,
                self.active_call_id,
            )
            self._last_log_ts = now
        return detections

    def _match_face(self, face: Any) -> tuple[str, float]:
        gallery = self._get_active_gallery()
        if not gallery:
            return "unknown", 0.0

        emb = np.asarray(face.embedding, dtype=np.float32)
        emb = self._normalize(emb)

        best_name = "unknown"
        best_score = -1.0

        for name, emb_list in gallery.items():
            for ref in emb_list:
                score = self._cosine_similarity(emb, ref)
                if score > best_score:
                    best_score = score
                    best_name = name

        if best_score < self.match_threshold:
            return "unknown", float(best_score)
        return best_name, float(best_score)

    def _get_active_gallery(self) -> dict[str, list[np.ndarray]]:
        if self.active_call_id and self.active_call_id in self.known_embeddings_by_call:
            return self.known_embeddings_by_call[self.active_call_id]
        # Only recognize faces for the active call folder.
        return {}

    def set_active_call_id(self, call_id: Optional[str]) -> None:
        self.active_call_id = call_id

    def enroll_from_bytes(self, call_id: str, name: str, image_bytes: bytes) -> dict[str, Any]:
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return {"ok": False, "reason": "invalid_image"}

        faces = self.app.get(image)
        if not faces:
            return {"ok": False, "reason": "no_face_detected"}

        best = max(
            faces,
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        )
        emb = np.asarray(best.embedding, dtype=np.float32)
        emb = self._normalize(emb)

        gallery = self.known_embeddings_by_call.setdefault(call_id, {})
        gallery.setdefault(name, []).append(emb)

        return {
            "ok": True,
            "name": name,
            "call_id": call_id,
            "det_score": float(best.det_score),
        }

    def state(self) -> dict[str, Any]:
        return {
            "detections": self.latest_detections,
            "unknown_detected": self.unknown_detected,
            "last_unknown_ts": self.last_unknown_ts,
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
