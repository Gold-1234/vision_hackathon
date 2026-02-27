# Vision Hackathon

Real-time video safety monitoring agent built with Vision Agents.

## What it does
- Runs YOLO object detection (analysis only)
- Runs Roboflow toddler/adult detection (analysis only)
- Runs Roboflow fall detection (analysis only, gated by toddler presence)
- Publishes a single merged annotated video stream with one combined publisher

## Project structure
- `backend/` : Python agent server and processors
- `frontend/` : frontend app (if used)

## Prerequisites
- Python 3.12
- `uv` installed
- Stream + Google + (optional Roboflow) API keys

## 1) Setup backend
```bash
cd backend
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## 2) Configure environment
Create `backend/.env` with:
```env
STREAM_API_KEY=...
STREAM_API_SECRET=...
GOOGLE_API_KEY=...
ROBOFLOW_API_KEY=...   # optional (enables toddler/adult detector)
EXAMPLE_BASE_URL=https://demo.visionagents.ai
```

## 3) Run agent with demo call
```bash
cd backend
source .venv/bin/activate
python server.py run --call-type default --call-id vision-test-1
```

This opens (or prints) a demo join URL for `https://demo.visionagents.ai`.

## 4) Run as HTTP service
```bash
cd backend
source .venv/bin/activate
python server.py serve --host 127.0.0.1 --port 8000
```
Video stream route:
- `http://127.0.0.1:8000/video/stream`

## 5) Local camera test (no Stream call)
```bash
cd backend
source .venv/bin/activate
python local_runner.py --device 0
```
Press `q` to quit.

## 6) Basic frontend stream viewer
In a separate terminal:
```bash
cd frontend
python3 -m http.server 5173
```
Open:
- `http://127.0.0.1:5173`

Default stream URL in the page:
- `http://127.0.0.1:8000/video/stream`

Frontend docs:
- `frontend/README.md`

## Notes
- Only one video publisher is used: `CombinedVideoPublisher`.
- `ObjectDetectionProcessor`, `ToddlerProcessor`, and `FallDetectionProcessor` are analysis-only processors.
- YOLO `person` label is filtered out from overlay/state.
- Roboflow `toddler` detections require confidence >= `0.8`.
- Fall detection only runs when `toddler_present == true`.
