from typing import Optional

from processors.crying_audio_detector import CryingAudioDetector


_crying_detector: Optional[CryingAudioDetector] = None


def set_crying_detector(detector: CryingAudioDetector | None) -> None:
    global _crying_detector
    _crying_detector = detector


def get_crying_detector() -> Optional[CryingAudioDetector]:
    return _crying_detector
