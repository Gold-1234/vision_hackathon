import { useRef, useState } from "react";
import { StreamVideoClient } from "@stream-io/video-react-sdk";

export default function useVisionCall () {
  const clientRef = useRef(null);
  const callRef = useRef(null);
  const joiningRef = useRef(false);
  const [client, setClient] = useState(null);
  const [call, setCall] = useState(null);
  const [status, setStatus] = useState("idle");

  const joinCall = async (callId) => {
    if (joiningRef.current || callRef.current) return;
    joiningRef.current = true;
    setStatus("joining");
    const backendBaseUrl = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
    const existingUserId = window.localStorage.getItem("vision_hack_user_id");
    const userId = existingUserId || `hackathon-user-${Math.floor(Date.now() / 1000)}`;
    if (!existingUserId) {
      window.localStorage.setItem("vision_hack_user_id", userId);
    }
    const userName = "Hackathon User";
    try {
      const tokenResp = await fetch(`${backendBaseUrl}/auth/stream-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          call_id: callId,
          call_type: "default",
          user_id: userId,
          user_name: userName,
          create_call: true,
        }),
      });
      if (!tokenResp.ok) {
        const text = await tokenResp.text();
        throw new Error(`Failed to get Stream token: ${tokenResp.status} ${text}`);
      }

      const tokenPayload = await tokenResp.json();
      const apiKey = tokenPayload.api_key;
      const token = tokenPayload.token;
      const callType = tokenPayload.call_type || "default";

      const client = new StreamVideoClient({
        apiKey,
        user: { id: userId, name: userName },
        token,
      });

      const call = client.call(callType, callId);
      // Force a single codec path to avoid decode incompatibilities on backend aiortc.
      call.updatePublishOptions({
        preferredCodec: "h264",
        subscriberCodec: "h264",
        dangerouslyForceCodec: "h264",
      });
      await call.join({ create: true });
      await call.microphone.disable();
      await call.camera.enable();

      clientRef.current = client;
      callRef.current = call;
      setClient(client);
      setCall(call);
      setStatus("live");
    } catch (err) {
      setStatus("error");
      throw err;
    } finally {
      joiningRef.current = false;
    }
  };

  const leaveCall = async () => {
    setStatus("stopping");
    if (callRef.current) {
      await callRef.current.leave();
      callRef.current = null;
    }

    if (clientRef.current) {
      await clientRef.current.disconnectUser();
      clientRef.current = null;
    }
    setCall(null);
    setClient(null);
    setStatus("stopped");
  };

  return { joinCall, leaveCall, client, call, status, isLive: Boolean(call) };
};
