const streamImg = document.getElementById("stream");
const streamUrlInput = document.getElementById("streamUrl");
const statusEl = document.getElementById("status");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
let retryTimer = null;
let live = false;

function setStatus(message) {
  statusEl.textContent = `Status: ${message}`;
}

function normalizedStreamUrl() {
  const raw = streamUrlInput.value.trim();
  return raw || "http://127.0.0.1:8000/video/stream";
}

function startStream() {
  clearTimeout(retryTimer);
  const url = normalizedStreamUrl();
  const withCacheBuster = `${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`;

  live = false;
  setStatus("connecting...");
  streamImg.src = withCacheBuster;
}

function stopStream() {
  clearTimeout(retryTimer);
  live = false;
  streamImg.removeAttribute("src");
  setStatus("stopped");
}

streamImg.addEventListener("load", () => {
  live = true;
  setStatus("live");
});

streamImg.addEventListener("error", () => {
  live = false;
  setStatus("no frame yet or bad URL");
  retryTimer = setTimeout(() => {
    if (!live) {
      startStream();
    }
  }, 2000);
});

startBtn.addEventListener("click", startStream);
stopBtn.addEventListener("click", stopStream);

async function refreshStatusFromApi() {
  const streamUrl = normalizedStreamUrl();
  const statusUrl = streamUrl.replace(/\/stream(\?.*)?$/, "/status");
  try {
    const response = await fetch(statusUrl, { cache: "no-store" });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    if (!payload.publisher_initialized) {
      setStatus("publisher not initialized");
      return;
    }
    if (!payload.has_frame) {
      setStatus("waiting for first video frame");
    }
  } catch {
    // Keep current status if API is unreachable.
  }
}

setInterval(refreshStatusFromApi, 2000);
refreshStatusFromApi();
startStream();
