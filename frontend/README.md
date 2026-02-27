# Frontend Stream Route Guide

This frontend displays the backend MJPEG stream published by the route:

- `GET /video/stream`
- Default local URL: `http://127.0.0.1:8000/video/stream`

It also uses:

- `GET /video/status`
- Default local URL: `http://127.0.0.1:8000/video/status`

## 1) Start backend and frontend

Backend (`serve` mode, required for stream routes):

```bash
cd ../backend
source .venv/bin/activate
python server.py serve --host 127.0.0.1 --port 8000
```

Frontend static server:

```bash
cd ../frontend
python3 -m http.server 5173
```

Open:

- `http://127.0.0.1:5173`

## 2) Start a call session (serve mode)

The stream route only gets frames after an agent session is started and a participant publishes video.

```bash
curl -X POST http://127.0.0.1:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"call_type":"default","call_id":"vision-test-1"}'
```

Then join the same call (`vision-test-1`) from browser and enable camera.

## 3) Frontend behavior

- `Start` button loads `<img src=".../video/stream">`
- `Stop` clears the stream `<img>`
- The frontend retries automatically every 2 seconds if the stream is not ready
- It polls `/video/status` to show:
  - `publisher not initialized`
  - `waiting for first video frame`
  - `live`

## 4) Example integration (plain HTML)

```html
<img id="stream" alt="Live stream" />
<script>
  const img = document.getElementById("stream");
  img.src = "http://127.0.0.1:8000/video/stream?t=" + Date.now();
</script>
```

## 5) Example integration (with retry)

```html
<img id="stream" alt="Live stream" />
<script>
  const streamUrl = "http://127.0.0.1:8000/video/stream";
  const img = document.getElementById("stream");

  function connect() {
    img.src = streamUrl + "?t=" + Date.now();
  }

  img.addEventListener("error", () => {
    setTimeout(connect, 2000);
  });

  connect();
</script>
```

## 6) Troubleshooting

1. `{"publisher_initialized": true, "has_frame": false}`
- No video frame has been published yet.
- Start `/sessions`, then join the same call ID with camera enabled.

2. Browser shows `ERR_BLOCKED_BY_CLIENT`
- Usually ad-block/shields extension.
- Disable blocker for `127.0.0.1` or test in private/incognito mode.

3. Stream works in direct URL but not frontend
- Hard refresh frontend (`Cmd+Shift+R`).
- Confirm frontend stream URL exactly matches backend host/port/path.

4. Using `python server.py run ...`
- `run` mode does not expose persistent serve endpoints the same way as `serve`.
- For frontend streaming routes, use `python server.py serve ...`.
