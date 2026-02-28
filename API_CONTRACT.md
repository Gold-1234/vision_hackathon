# API Contract

Base URL (local):
- `http://127.0.0.1:8000`

All endpoints are served by the FastAPI app started with:
```bash
python server.py serve --host 127.0.0.1 --port 8000
```

## Video

### `GET /video/stream`
MJPEG video stream from the combined publisher.

Response:
- `200` streaming `multipart/x-mixed-replace` with JPEG frames.
- `503` if no publisher is initialized or no frames are available yet.

### `GET /video/status`
Returns whether a publisher is initialized and whether a frame is available.

Response:
```json
{
  "publisher_initialized": true,
  "has_frame": true
}
```

## Audio

### `GET /audio/crying/status`
Returns the current state of the crying detector.

Response:
```json
{
  "initialized": true,
  "enabled": true,
  "cry_detected": false,
  "cry_score": 0.0,
  "top_label": "",
  "top_score": 0.0,
  "alarm_active": false,
  "recent_predictions": [],
  "last_audio_ts": null,
  "disable_reason": null
}
```

## Faces

### `POST /faces/enroll`
Enroll a face image for recognition. Saves the image to disk and updates the in‑memory
gallery for the provided `call_id`.

Request (multipart/form-data):
- `call_id`: string (required)
- `name`: string (required) — used as the label
- `image`: file (required) — jpg/png/bmp/webp

Example:
```bash
curl -X POST \
  -F "call_id=vision-test-1" \
  -F "name=alice" \
  -F "image=@/absolute/path/to/alice.jpg" \
  http://127.0.0.1:8000/faces/enroll
```

Response:
```json
{
  "ok": true,
  "call_id": "vision-test-1",
  "name": "alice",
  "path": "data/know_faces/vision-test-1/alice.jpg",
  "det_score": 0.98
}
```
