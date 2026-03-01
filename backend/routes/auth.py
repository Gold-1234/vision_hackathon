import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from getstream import AsyncStream
from getstream.models import CallRequest


router = APIRouter(prefix="/auth", tags=["auth"])


class StreamTokenRequest(BaseModel):
    call_id: str
    call_type: str = "default"
    user_id: str = "hackathon-user"
    user_name: str = "Hackathon User"
    create_call: bool = True


@router.post("/stream-token")
async def stream_token(payload: StreamTokenRequest) -> dict[str, Any]:
    api_key = os.getenv("STREAM_API_KEY", "").strip()
    api_secret = os.getenv("STREAM_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise HTTPException(status_code=500, detail="Stream API credentials are not configured.")

    client = AsyncStream(api_key=api_key, api_secret=api_secret)
    try:
        if payload.create_call:
            call = client.video.call(payload.call_type, payload.call_id)
            creator_id = os.getenv("STREAM_CREATOR_ID", "agent")
            await call.get_or_create(data=CallRequest(created_by_id=creator_id))

        token = client.create_token(payload.user_id, expiration=3600)
        return {
            "api_key": api_key,
            "token": token,
            "call_id": payload.call_id,
            "call_type": payload.call_type,
            "user_id": payload.user_id,
            "user_name": payload.user_name,
        }
    finally:
        await client.aclose()
