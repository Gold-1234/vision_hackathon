import argparse
import importlib.util
import json
import wave
from pathlib import Path
from typing import Tuple

import numpy as np

_MODULE_PATH = Path(__file__).resolve().parents[1] / "processors" / "crying_audio_detector.py"
_SPEC = importlib.util.spec_from_file_location("crying_audio_detector", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("Failed to load crying_audio_detector module")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
CryingAudioDetector = _MODULE.CryingAudioDetector


def _load_wav(path: str) -> Tuple[np.ndarray, int, int]:
    with wave.open(path, "rb") as wf:
        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        nframes = wf.getnframes()
        frames = wf.readframes(nframes)

    if sampwidth == 1:
        dtype = np.uint8
    elif sampwidth == 2:
        dtype = np.int16
    elif sampwidth == 4:
        dtype = np.int32
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth} bytes")

    data = np.frombuffer(frames, dtype=dtype)
    if sampwidth == 1:
        data = data.astype(np.float32) - 128.0
        data /= 128.0
    else:
        scale = float(2 ** (8 * sampwidth - 1))
        data = data.astype(np.float32) / scale

    if channels > 1:
        data = data.reshape(-1, channels)

    return data, sample_rate, channels


def main() -> int:
    parser = argparse.ArgumentParser(description="Run YAMNet crying detector on a WAV file.")
    parser.add_argument("--wav", required=True, help="Path to a WAV file (PCM).")
    parser.add_argument("--window", type=float, default=2.0, help="Window size in seconds.")
    parser.add_argument("--stride", type=float, default=0.5, help="Stride in seconds.")
    parser.add_argument("--json", action="store_true", help="Emit per-window JSON lines.")
    args = parser.parse_args()

    detector = CryingAudioDetector(window_seconds=args.window, infer_hz=max(0.1, 1.0 / args.stride))
    if not detector.enabled:
        print("CryingAudioDetector is disabled. Install tensorflow + tensorflow_hub and allow model download.")
        return 1

    samples, sample_rate, channels = _load_wav(args.wav)
    mono = detector._to_mono(samples, channels)
    mono = detector._resample_if_needed(mono, sample_rate)

    window_samples = detector.window_samples
    stride_samples = max(1, int(args.stride * detector.sample_rate))
    total_samples = mono.shape[0]

    if total_samples < window_samples:
        print("Audio too short for the configured window size.")
        return 2

    cry_detected = False
    max_score = 0.0
    max_at = 0.0

    for start in range(0, total_samples - window_samples + 1, stride_samples):
        window = mono[start : start + window_samples]
        cry_score, top_label, top_score = detector._infer_window(window)

        if cry_detected:
            if cry_score <= detector.exit_threshold:
                cry_detected = False
        elif cry_score >= detector.enter_threshold:
            cry_detected = True

        t = start / float(detector.sample_rate)
        if cry_score > max_score:
            max_score = cry_score
            max_at = t

        if args.json:
            print(
                json.dumps(
                    {
                        "t": round(t, 3),
                        "cry_score": round(cry_score, 4),
                        "cry_detected": cry_detected,
                        "top_label": top_label,
                        "top_score": round(top_score, 4),
                    }
                )
            )
        else:
            print(
                f"t={t:6.2f}s cry_score={cry_score:.3f} "
                f"cry_detected={cry_detected} top_label={top_label} top_score={top_score:.3f}"
            )

    print(f"max_cry_score={max_score:.3f} at {max_at:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
