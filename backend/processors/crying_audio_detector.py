import csv
import io
import logging
import os
import queue
import threading
import time
from typing import Any, Optional
from urllib.request import urlopen

import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from getstream.video.rtc import PcmData
else:
    PcmData = Any
try:
    from vision_agents.core.processors import AudioProcessor
except Exception:  # pragma: no cover - allows local CLI without full stack
    class AudioProcessor:  # type: ignore[no-redef]
        async def process_audio(self, audio_data: Any) -> None:  # noqa: D401
            return None

logger = logging.getLogger(__name__)

YAMNET_MODEL_URL = "https://tfhub.dev/google/yamnet/1"
YAMNET_CLASS_MAP_URL = "https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv"
DEFAULT_CRY_KEYWORDS = (
    "baby cry",
    "infant cry",
    "crying",
    "sobbing",
    "wail",
)


class CryingAudioDetector(AudioProcessor):
    """
    Phase 1 (observe-only):
    - Runs YAMNet on live audio windows
    - Updates state + logs cry scores
    - Does not trigger user-facing alerts by itself
    """

    name = "crying_audio_detector"

    def __init__(
        self,
        window_seconds: float = 2.0,
        infer_hz: float = 2.0,
        enter_threshold: float = 0.35,
        exit_threshold: float = 0.20,
        log_interval_seconds: float = 2.0,
    ) -> None:
        self.window_seconds = max(0.5, float(window_seconds))
        self.infer_interval_seconds = 1.0 / max(0.1, float(infer_hz))
        self.enter_threshold = float(enter_threshold)
        self.exit_threshold = float(exit_threshold)
        self.log_interval_seconds = max(0.5, float(log_interval_seconds))

        self.sample_rate = 16000
        self.window_samples = int(self.window_seconds * self.sample_rate)
        self._buffer = np.array([], dtype=np.float32)

        self._lock = threading.Lock()
        self._last_infer_ts = 0.0
        self._last_log_ts = 0.0

        self.cry_detected = False
        self.cry_score = 0.0
        self.top_label = ""
        self.top_score = 0.0
        self.enabled = False
        self.alarm_active = False
        self.recent_predictions: list[bool] = []
        self.last_audio_ts: float | None = None
        self.disable_reason: str | None = None

        self._tf = None
        self._yamnet = None
        self._class_names: list[str] = []
        self._cry_class_indices: list[int] = []

        self._audio_queue: "queue.Queue[tuple[np.ndarray, int, int]]" = queue.Queue(maxsize=50)
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._chunk_size = int(self.sample_rate * 1.0)
        self._chunk_step = int(self.sample_rate * 1.0)
        self._alarm_window_size = 5

        try:
            import tensorflow as tf
            import tensorflow_hub as hub

            self._tf = tf
            logger.info("CryingAudioDetector: TensorFlow loaded successfully")
            self._yamnet = hub.load(YAMNET_MODEL_URL)
            logger.info("CryingAudioDetector: YAMNet model loaded")
            self._class_names = self._load_class_names()
            logger.info("CryingAudioDetector: YAMNet class map loaded (%d classes)", len(self._class_names))
            self._cry_class_indices = self._resolve_cry_class_indices(self._class_names)
            logger.info(
                "CryingAudioDetector: cry class indices resolved (%d matches)",
                len(self._cry_class_indices),
            )
            self.enabled = len(self._cry_class_indices) > 0
        except Exception as error:
            self.disable_reason = str(error)
            logger.warning("CryingAudioDetector disabled (YAMNet unavailable): %s", error)

        if self.enabled:
            logger.info(
                "CryingAudioDetector enabled: window=%.1fs infer_hz=%.1f classes=%d",
                self.window_seconds,
                1.0 / self.infer_interval_seconds,
                len(self._cry_class_indices),
            )
            logger.info("CryingAudioDetector worker starting (chunk=1.0s step=1.0s)")
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="CryingAudioDetectorWorker",
                daemon=True,
            )
            self._worker_thread.start()
        else:
            logger.info("CryingAudioDetector running in disabled mode")

    def _load_class_names(self) -> list[str]:
        with urlopen(YAMNET_CLASS_MAP_URL, timeout=10) as response:
            body = response.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(body))
        names: list[str] = []
        for row in reader:
            names.append(str(row.get("display_name", "")).strip())
        if not names:
            raise RuntimeError("Failed to load YAMNet class names")
        return names

    @staticmethod
    def _resolve_cry_class_indices(class_names: list[str]) -> list[int]:
        indices: list[int] = []
        for idx, name in enumerate(class_names):
            n = name.lower().strip()
            if any(keyword in n for keyword in DEFAULT_CRY_KEYWORDS):
                indices.append(idx)
        return indices

    @staticmethod
    def _to_mono(samples: np.ndarray, channels: int) -> np.ndarray:
        if samples.ndim == 1:
            return samples.astype(np.float32, copy=False)
        if samples.ndim == 2:
            if channels > 1 and samples.shape[0] == channels:
                return samples.mean(axis=0, dtype=np.float32)
            if channels > 1 and samples.shape[1] == channels:
                return samples.mean(axis=1, dtype=np.float32)
            return samples.reshape(-1).astype(np.float32, copy=False)
        return samples.reshape(-1).astype(np.float32, copy=False)

    def _resample_if_needed(self, mono: np.ndarray, src_rate: int) -> np.ndarray:
        if src_rate == self.sample_rate:
            return mono
        target_len = int(len(mono) * (self.sample_rate / max(1, src_rate)))
        target_len = max(1, target_len)
        # tf.signal.resample is not available in some TF builds (e.g., certain macOS wheels).
        if self._tf is not None and hasattr(self._tf.signal, "resample"):
            return self._tf.signal.resample(mono, target_len).numpy().astype(np.float32)
        from scipy.signal import resample
        return resample(mono, target_len).astype(np.float32)

    def _infer_window(self, wav: np.ndarray) -> tuple[float, str, float]:
        scores, _, _ = self._yamnet(wav)
        mean_scores = self._tf.reduce_mean(scores, axis=0).numpy()

        cry_score = float(np.max(mean_scores[self._cry_class_indices]))
        top_idx = int(np.argmax(mean_scores))
        top_label = self._class_names[top_idx] if 0 <= top_idx < len(self._class_names) else str(top_idx)
        top_score = float(mean_scores[top_idx])
        return cry_score, top_label, top_score

    async def process_audio(self, audio_data: PcmData) -> None:
        if not self.enabled:
            return
        if audio_data.samples is None or len(audio_data.samples) == 0:
            return

        pcm = audio_data.to_float32()
        samples = np.array(pcm.samples, copy=False)
        try:
            self._audio_queue.put_nowait((samples, int(pcm.sample_rate), int(pcm.channels or 1)))
        except queue.Full:
            # Drop audio if we can't keep up.
            pass

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                samples, sample_rate, channels = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            with self._lock:
                mono = self._to_mono(samples, channels)
                mono = self._resample_if_needed(mono, int(sample_rate))
                self.last_audio_ts = time.time()

                if mono.size == 0:
                    continue

                if self._buffer.size == 0:
                    self._buffer = mono
                else:
                    self._buffer = np.concatenate([self._buffer, mono]).astype(np.float32, copy=False)

                # Process fixed 1-second chunks at 16kHz.
                while self._buffer.size >= self._chunk_size:
                    chunk = self._buffer[: self._chunk_size]
                    self._buffer = self._buffer[self._chunk_step :]

                    now = time.time()
                    if now - self._last_infer_ts < self.infer_interval_seconds:
                        continue
                    self._last_infer_ts = now

                    cry_score, top_label, top_score = self._infer_window(chunk.copy())
                    self.cry_score = cry_score
                    self.top_label = top_label
                    self.top_score = top_score

                    logger.info(
                        "cry-frame | cry_score=%.3f top_label=%s top_score=%.3f",
                        self.cry_score,
                        self.top_label,
                        self.top_score,
                    )

                    if self.cry_detected:
                        if cry_score <= self.exit_threshold:
                            self.cry_detected = False
                    elif cry_score >= self.enter_threshold:
                        self.cry_detected = True

                    self.recent_predictions.append(self.cry_detected)
                    if len(self.recent_predictions) > self._alarm_window_size:
                        self.recent_predictions.pop(0)
                    self.alarm_active = sum(self.recent_predictions) >= 3

                    if now - self._last_log_ts >= self.log_interval_seconds:
                        logger.info(
                            "cry-monitor | cry_detected=%s cry_score=%.3f top_label=%s top_score=%.3f alarm=%s recent=%s",
                            self.cry_detected,
                            self.cry_score,
                            self.top_label,
                            self.top_score,
                            self.alarm_active,
                            self.recent_predictions,
                        )
                        self._last_log_ts = now

    async def close(self) -> None:
        self._stop_event.set()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=2.0)

    def state(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "cry_detected": self.cry_detected,
            "cry_score": self.cry_score,
            "top_label": self.top_label,
            "top_score": self.top_score,
            "alarm_active": self.alarm_active,
            "recent_predictions": list(self.recent_predictions),
            "last_audio_ts": self.last_audio_ts,
            "disable_reason": self.disable_reason,
        }

    async def close(self) -> None:
        self._buffer = np.array([], dtype=np.float32)
