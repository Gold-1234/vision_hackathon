from .audio import router as audio_router
from .video import router as video_router
from .faces import router as faces_router
from .auth import router as auth_router

__all__ = ["video_router", "audio_router", "faces_router", "auth_router"]
