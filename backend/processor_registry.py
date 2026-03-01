from typing import Optional

from processors.crying_audio_detector import CryingAudioDetector
from processors.face_recognition import FaceRecognitionProcessor
from processors.zone_risk_guard import ZoneRiskGuard


_crying_detector: Optional[CryingAudioDetector] = None
_face_recognizer: Optional[FaceRecognitionProcessor] = None
_zone_guard: Optional[ZoneRiskGuard] = None


def set_crying_detector(detector: CryingAudioDetector | None) -> None:
    global _crying_detector
    _crying_detector = detector


def get_crying_detector() -> Optional[CryingAudioDetector]:
    return _crying_detector


def set_face_recognizer(detector: FaceRecognitionProcessor | None) -> None:
    global _face_recognizer
    _face_recognizer = detector


def get_face_recognizer() -> Optional[FaceRecognitionProcessor]:
    return _face_recognizer


def set_zone_guard(processor: ZoneRiskGuard | None) -> None:
    global _zone_guard
    _zone_guard = processor


def get_zone_guard() -> Optional[ZoneRiskGuard]:
    return _zone_guard
