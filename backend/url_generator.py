import os
import asyncio
from urllib.parse import urlencode

from dotenv import load_dotenv
from getstream import AsyncStream
from getstream.models import CallRequest

load_dotenv()


async def main() -> None:
    call_type = os.getenv("STREAM_CALL_TYPE", "default")
    call_id = os.getenv("STREAM_CALL_ID", "vision-test")
    human_id = os.getenv("STREAM_HUMAN_USER_ID", "user-demo-agent")
    creator_id = os.getenv("STREAM_CREATOR_ID", "agent")

    client = AsyncStream(
        api_key=os.environ["STREAM_API_KEY"],
        api_secret=os.environ["STREAM_API_SECRET"],
    )

    # Required by Stream server-side auth: a creator must be set on call creation.
    call = client.video.call(call_type, call_id)
    await call.get_or_create(
        data=CallRequest(
            created_by_id=creator_id,
        )
    )

    token = client.create_token(human_id, expiration=3600)
    base = f'{os.getenv("EXAMPLE_BASE_URL", "https://getstream.io/video/demos")}/join/'
    params = {
        "api_key": os.environ["STREAM_API_KEY"],
        "token": token,
        "skip_lobby": "true",
        "user_name": "Human Camera",
        "video_encoder": "h264",
        "bitrate": "2500000",
        "w": "1280",
        "h": "720",
        "channel_type": call_type,
    }
    print(base + call_id + "?" + urlencode(params))


if __name__ == "__main__":
    asyncio.run(main())
