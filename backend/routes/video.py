import asyncio
import io
import os
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import cv2
import numpy as np

from processor_registry import get_zone_guard
from video_stream_registry import get_publisher

router = APIRouter(prefix="/video", tags=["video"])

BOUNDARY = "frame"
_moondream_model: Any = None


async def _mjpeg_generator() -> AsyncGenerator[bytes, None]:
    while True:
        publisher = get_publisher()
        if publisher is None or not hasattr(publisher, "get_latest_jpeg"):
            await asyncio.sleep(0.1)
            continue

        frame = await publisher.get_latest_jpeg()
        if frame is None:
            await asyncio.sleep(0.03)
            continue

        yield (
            f"--{BOUNDARY}\r\n"
            "Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(frame)}\r\n\r\n"
        ).encode("ascii") + frame + b"\r\n"
        await asyncio.sleep(0.03)


async def _get_frame_with_timeout(
    publisher: Any,
    timeout_seconds: float = 5.0,
) -> bytes | None:
    deadline = asyncio.get_running_loop().time() + max(0.1, timeout_seconds)
    while asyncio.get_running_loop().time() < deadline:
        frame = await publisher.get_latest_jpeg()
        if frame is not None:
            return frame
        await asyncio.sleep(0.05)
    return None


def _get_moondream_model() -> Any:
    global _moondream_model
    if _moondream_model is not None:
        return _moondream_model

    api_key = os.getenv("MOONDREAM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MOONDREAM_API_KEY is not configured.")

    import moondream as md

    _moondream_model = md.vl(api_key=api_key)
    return _moondream_model


def _describe_activity_with_moondream(frame_jpeg: bytes, question: str) -> dict[str, Any]:
    from PIL import Image

    model = _get_moondream_model()
    image = Image.open(io.BytesIO(frame_jpeg)).convert("RGB")
    result = model.query(image, question)
    if isinstance(result, dict):
        answer = str(result.get("answer", "")).strip()
    else:
        answer = str(result).strip()
    return {
        "answer": answer or "No activity description returned.",
        "raw": result,
    }


@router.get("/status")
async def stream_status() -> dict[str, bool]:
    publisher = get_publisher()
    if publisher is None or not hasattr(publisher, "get_latest_jpeg"):
        return {
            "publisher_initialized": False,
            "has_frame": False,
        }

    frame = await publisher.get_latest_jpeg()
    return {
        "publisher_initialized": True,
        "has_frame": frame is not None,
    }


@router.get("/stream")
async def stream_video() -> StreamingResponse:
    publisher = get_publisher()
    if publisher is None or not hasattr(publisher, "get_latest_jpeg"):
        raise HTTPException(status_code=503, detail="Video publisher not initialized")

    first_frame = await _get_frame_with_timeout(publisher, timeout_seconds=5.0)
    if first_frame is None:
        raise HTTPException(
            status_code=503,
            detail="No video frames available yet. Join a call and publish camera video first.",
        )

    return StreamingResponse(
        _mjpeg_generator(),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
    )


@router.post("/current-activity")
async def current_activity() -> dict[str, Any]:
    publisher = get_publisher()
    if publisher is None or not hasattr(publisher, "get_latest_jpeg"):
        raise HTTPException(status_code=503, detail="Video publisher not initialized")

    frame = await _get_frame_with_timeout(publisher, timeout_seconds=5.0)
    if frame is None:
        raise HTTPException(status_code=503, detail="No video frame available yet")

    question = (
        "Describe the current activity in this image in one short sentence. "
        "Focus on toddler safety context and mention any immediate risk if visible."
    )
    try:
        result = await asyncio.to_thread(_describe_activity_with_moondream, frame, question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Moondream query failed: {exc}") from exc

    return {
        "ok": True,
        "activity": result.get("answer", ""),
        "question": question,
    }


@router.post("/reassess-zone")
async def reassess_zone() -> dict[str, Any]:
    publisher = get_publisher()
    if publisher is None or not hasattr(publisher, "get_latest_jpeg"):
        raise HTTPException(status_code=503, detail="Video publisher not initialized")

    frame = await _get_frame_with_timeout(publisher, timeout_seconds=5.0)
    if frame is None:
        raise HTTPException(status_code=503, detail="No video frame available yet")

    zone_guard = get_zone_guard()
    if zone_guard is None:
        raise HTTPException(status_code=503, detail="Zone guard is not initialized")

    image = cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=500, detail="Failed to decode latest frame")

    try:
        result = await zone_guard.reassess_zone(image)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Zone reassess failed: {exc}") from exc

    state = zone_guard.state()
    return {
        "ok": bool(result.get("ok", False)),
        "zone_bbox": state.get("zone_bbox"),
        "zone_reason": state.get("zone_reason"),
        "status": state.get("status"),
        "init_attempts": state.get("init_attempts"),
    }
