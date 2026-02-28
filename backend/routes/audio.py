from typing import Any

from fastapi import APIRouter

from processor_registry import get_crying_detector

router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/crying/status")
async def crying_status() -> dict[str, Any]:
    detector = get_crying_detector()
    if detector is None:
        return {
            "initialized": False,
            "enabled": False,
            "cry_detected": False,
            "cry_score": 0.0,
            "top_label": "",
            "top_score": 0.0,
            "alarm_active": False,
            "recent_predictions": [],
            "last_audio_ts": None,
            "disable_reason": "detector not initialized",
        }
    state = detector.state()
    return {"initialized": True, **state}
