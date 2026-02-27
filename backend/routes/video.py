import asyncio
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from video_stream_registry import get_publisher

router = APIRouter(prefix="/video", tags=["video"])

BOUNDARY = "frame"


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
