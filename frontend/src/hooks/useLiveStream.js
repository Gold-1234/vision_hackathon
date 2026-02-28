import { useEffect, useRef, useState, useCallback } from "react";

export default function useLiveStream(streamUrl) {
  const imgRef = useRef(null);
  const retryRef = useRef(null);
  const statusIntervalRef = useRef(null);
  const [status, setStatus] = useState("idle");
  const [isLive, setIsLive] = useState(false);

  const withCacheBuster = (url) => {
    return `${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`;
  };

  const startStream = useCallback(() => {
    if (!imgRef.current) return;

    clearTimeout(retryRef.current);

    setStatus("connecting...");
    setIsLive(false);

    imgRef.current.src = withCacheBuster(streamUrl);
  }, [streamUrl]);

  const stopStream = useCallback(() => {
    if (!imgRef.current) return;

    clearTimeout(retryRef.current);

    imgRef.current.removeAttribute("src");

    setStatus("stopped");
    setIsLive(false);
  }, []);

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;

    const handleLoad = () => {
      setStatus("live");
      setIsLive(true);
    };

    const handleError = () => {
      setStatus("no frame yet or bad URL");
      setIsLive(false);

      retryRef.current = setTimeout(() => {
        startStream();
      }, 2000);
    };

    img.addEventListener("load", handleLoad);
    img.addEventListener("error", handleError);

    return () => {
      img.removeEventListener("load", handleLoad);
      img.removeEventListener("error", handleError);
    };
  }, [startStream]);

  useEffect(() => {
    async function checkStatus() {
      try {
        const statusUrl = streamUrl.replace(/\/stream(\?.*)?$/, "/status");
        const res = await fetch(statusUrl, { cache: "no-store" });

        if (!res.ok) return;

        const data = await res.json();

        if (!data.publisher_initialized) {
          setStatus("publisher not initialized");
        } else if (!data.has_frame) {
          setStatus("waiting for first video frame");
        }
      } catch {
        // Ignore network errors
      }
    }

    statusIntervalRef.current = setInterval(checkStatus, 2000);

    return () => {
      clearInterval(statusIntervalRef.current);
    };
  }, [streamUrl]);

  return {
    imgRef,
    startStream,
    stopStream,
    status,
    isLive,
  };
}
