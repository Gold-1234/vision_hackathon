import { useRef } from "react";
import { StreamVideoClient } from "@stream-io/video-react-sdk";
import { StreamChat } from "stream-chat";

const apiKey = "kq5wzhabzjzv";

export default function useVisionCall () {
  const clientRef = useRef(null);
  const callRef = useRef(null);

  const joinCall = async (callId) => {
    const userId = "hackathon-user";
    
    // const token = StreamChat.getInstance(apiKey).devToken(userId);

    const client = new StreamVideoClient({
      apiKey,
      user: { id: userId },
      token,
    });

    await client.connectUser({ id: userId }, token);

    const call = client.call("default", callId);
    await call.join({ create: true });
    await call.camera.enable({ audio: false });

    clientRef.current = client;
    callRef.current = call;
  };

  const leaveCall = async () => {
    if (callRef.current) {
      await callRef.current.leave();
      callRef.current = null;
    }

    if (clientRef.current) {
      await clientRef.current.disconnectUser();
      clientRef.current = null;
    }
  };

  return { joinCall, leaveCall };
};
