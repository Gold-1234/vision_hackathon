import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from processor_registry import get_face_recognizer

router = APIRouter(prefix="/faces", tags=["faces"])


def _sanitize_name(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip())
    return clean.strip("_")


@router.post("/enroll")
async def enroll_face(
    call_id: str = Form(...),
    name: str = Form(...),
    image: UploadFile = File(...),
) -> dict[str, Any]:
    recognizer = get_face_recognizer()
    if recognizer is None:
        raise HTTPException(status_code=503, detail="Face recognizer not initialized")

    safe_name = _sanitize_name(name)
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid name")

    ext = Path(image.filename or "").suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image upload")

    # Save to disk under data/know_faces/<call_id>/<name>.<ext>
    base_dir = Path("data/know_faces") / call_id
    base_dir.mkdir(parents=True, exist_ok=True)
    dest = base_dir / f"{safe_name}{ext}"
    dest.write_bytes(contents)

    result = recognizer.enroll_from_bytes(call_id=call_id, name=safe_name, image_bytes=contents)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("reason", "enroll_failed"))

    return {
        "ok": True,
        "call_id": call_id,
        "name": safe_name,
        "path": str(dest),
        "det_score": result.get("det_score", 0.0),
    }
