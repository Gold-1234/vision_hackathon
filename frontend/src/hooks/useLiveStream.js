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

  const statusUrl = streamUrl.replace(/\/stream(\?.*)?$/, "/status");

  const startStream = useCallback(() => {
    if (!imgRef.current) return;

    clearTimeout(retryRef.current);
    clearInterval(statusIntervalRef.current);

    setStatus("connecting");
    setIsLive(false);

    imgRef.current.src = withCacheBuster(streamUrl);

    statusIntervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(statusUrl, { cache: "no-store" });
        if (!res.ok) return;

        const data = await res.json();

        if (!data.publisher_initialized) {
          setStatus("publisher not initialized");
          setIsLive(false);
        } else if (!data.has_frame) {
          setStatus("waiting for first frame");
          setIsLive(false);
        } else {
          setStatus("live");
          setIsLive(true);
        }
      } catch {
        setIsLive(false);
      }
    }, 1000);
  }, [streamUrl, statusUrl]);

  const stopStream = useCallback(() => {
    if (!imgRef.current) return;

    clearTimeout(retryRef.current);
    clearInterval(statusIntervalRef.current);

    imgRef.current.removeAttribute("src");

    setStatus("stopped");
    setIsLive(false);
  }, []);

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;

    const handleError = () => {
      setStatus("stream error");

      retryRef.current = setTimeout(() => {
        startStream();
      }, 2000);
    };

    img.addEventListener("error", handleError);

    return () => {
      img.removeEventListener("error", handleError);
    };
  }, [startStream]);

  useEffect(() => {
    return () => {
      clearTimeout(retryRef.current);
      clearInterval(statusIntervalRef.current);
    };
  }, []);

  return {
    imgRef,
    startStream,
    stopStream,
    status,
    isLive,
  };
}
