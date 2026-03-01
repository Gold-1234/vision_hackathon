# Vision Hackathon: Real-Time Child Safety Copilot

AI safety monitoring for toddlers using live video + audio.  
The system watches only when a toddler is present, detects high-risk situations, verifies context, and speaks alerts in real time.

## Why This Can Win
- Clear real-world problem: home child safety.
- Multi-signal intelligence: toddler presence, dangerous objects, fall events, and risky-zone crossing.
- Strong demo UX: live overlays + spoken warnings + structured alert logs.
- Practical design: false-positive controls, cooldowns, and stateful event transitions.
- Hackathon-ready evidence: saved videos, debug ticks, and JSON alert history.

## Features
### 1) Presence-Aware Pipeline
- Toddler-first gating: safety processors run only when toddler presence is true.
- Reduced false alarms and lower compute when toddler is not visible.

### 2) Dangerous Object Detection
- Local YOLO detection for dangerous classes near toddler.
- Proximity logic between toddler bbox and object bbox.
- Optional second-pass behavior supported in object detector for harder objects.
- Alert transitions are event-based (not frame-spam).

### 3) Fall Detection
- Toddler-gated fall model inference.
- Buffered/thresholded logic in fall processor to avoid flicker alerts.
- Emits alert event + spoken warning when fall state transitions to true.

### 4) Zone Risk Guard (Stairs / Drop-Off)
- Startup Moondream two-step flow:
- Step 1: `/v1/query` to return unsafe place names.
- Step 2: `/v1/detect` for returned place(s), prioritizing stairs-like labels.
- Risk zone locks after successful detection.
- If not found, detection retries on later frames until success (configurable).
- Boundary crossing and near-zone state are tracked in real time.

### 5) Context Verification Layer
- Moondream verification for dangerous-object candidates before final danger alert.
- Helps suppress false positives from local detector alone.

### 6) Real-Time Alerts + Speech
- Cartesia TTS warnings for:
- fall detected
- dangerous object near toddler
- toddler near/crossed/inside risky stairs zone
- Alert cooldown and dedupe logic prevents repetitive speech spam.

### 7) Evidence + Audit Trail
- Live overlay stream with all active safety annotations.
- JSONL alert sink for downstream actions (notifications/email integration).
- Saved zone snapshots and raw Moondream request/response logs for debugging.
- Offline video runners to reproduce and demonstrate results quickly.

## Visual + Audio Output
- Live annotated stream:
  - toddler boxes, danger boxes, fall box, red risky-zone box.
  - status text including boundary crossing.
- Spoken messages (Cartesia):
  - “Toddler fall detected.”
  - “<object> is dangerously close to the toddler.”
  - “Baby crossed into the stairs danger zone.”

## Project Structure
- `backend/`: agent runtime, processors, routes, tools
- `frontend/`: viewer/demo UI

## Prerequisites
- Python `3.12`
- `uv`
- API keys:
  - `STREAM_API_KEY`, `STREAM_API_SECRET`
  - `GOOGLE_API_KEY`
  - `ROBOFLOW_API_KEY`
  - `MOONDREAM_API_KEY`
  - `CARTESIA_API_KEY` (for TTS)

## Setup
```bash
cd backend
uv venv --python 3.12 .venv
source .venv/bin/activate
uv sync
```

If needed:
```bash
uv add "vision-agents[moondream]"
```

## Environment
Create `backend/.env`:
```env
STREAM_API_KEY=...
STREAM_API_SECRET=...
GOOGLE_API_KEY=...
ROBOFLOW_API_KEY=...
MOONDREAM_API_KEY=...
CARTESIA_API_KEY=...

GEMINI_MODEL=gemini-2.5-flash-lite
STARTUP_SPEECH_ENABLED=false

ZONE_RISK_DEBUG_DIR=data/test_results/zone_risk
ZONE_RISK_INIT_AFTER_FRAMES=0
ZONE_RISK_INIT_RETRY_INTERVAL_FRAMES=30
ZONE_RISK_MAX_INIT_ATTEMPTS=0
ZONE_RISK_CROSSED_DISPLAY_SECONDS=3
```

## Live Demo Run
1. Run agent:
```bash
cd backend
source .venv/bin/activate
python server.py run --call-type default --call-id vision-test-1
```

2. Optional stream endpoint server:
```bash
python server.py serve --host 127.0.0.1 --port 8000
```

3. Stream URL:
- `http://127.0.0.1:8000/video/stream`

## Offline Test Runners
Full danger/fall pipeline on video:
```bash
backend/.venv/bin/python backend/tools/run_toddler_danger_video.py \
  --input backend/data/test_video/test_7.mp4 \
  --output backend/data/test_results/test_7_full_pipeline.mp4 \
  --process-fps 1 \
  --debug-log backend/data/test_results/test_7_full_pipeline_ticks.csv
```

Zone-risk only runner:
```bash
backend/.venv/bin/python backend/tools/run_zone_risk_video.py \
  --input backend/data/test_video/test_8.mp4 \
  --output backend/data/test_results/test_8_zone_risk.mp4 \
  --process-fps 2 \
  --debug-log backend/data/test_results/test_8_zone_risk_ticks.csv
```

## Stored Artifacts (for judging)
- Alert events:
  - `backend/data/alerts/alerts.jsonl`
- Zone init artifacts:
  - `backend/data/test_results/zone_risk/zone_init_*_raw.jpg`
  - `backend/data/test_results/zone_risk/zone_init_*_marked.jpg`
  - `backend/data/test_results/zone_risk/zone_init_*_response.json`
  - `backend/data/test_results/zone_risk/moondream_api_debug.jsonl`
- Tick-level debug CSVs in `backend/data/test_results/`

## Example Outputs
Playable sample outputs:

### test_7_full_pipeline_rerun.mp4
<video src="backend/data/test_results/test_7_full_pipeline_rerun.mp4" controls width="720"></video>

### test_1_out.mp4
<video src="backend/data/test_results/test_1_out.mp4" controls width="720"></video>

### test_result_1.mp4
<video src="backend/data/test_results/test_result_1.mp4" controls width="720"></video>

### test_result_2.mp4
<video src="backend/data/test_results/test_result_2.mp4" controls width="720"></video>

### test_result_3.mp4
<video src="backend/data/test_results/test_result_3.mp4" controls width="720"></video>

### test_results_6.mp4
<video src="backend/data/test_results/test_results_6.mp4" controls width="720"></video>

## Frontend app call flow (recommended)
- Frontend joins Stream call via backend token endpoint:
  - `POST /auth/stream-token`
- Backend agent joins same `call_id`, processes incoming user camera.
- Frontend displays processed output from:
  - `GET /video/stream`

For Vite frontend, set:
```env
VITE_BACKEND_URL=http://127.0.0.1:8000
```

## Notes
- `person` class is filtered from object overlay/state.
- Zone is locked after detection; not continuously re-detected.
- Retry is enabled only until initial zone lock succeeds.
- TTS is event-based with cooldown to avoid repetitive spam.
