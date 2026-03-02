import { useState } from "react";
import Navbar from "../components/global/Navbar";
import ActivityCard from "../components/home/ActivityCard";
import NotificationCard from "../components/home/NotificationCard";
import useVisionCall from "../hooks/useVisionCall";
import RegistrationCard from "../components/home/RegistrationCard";
import {
  CallControls,
  SpeakerLayout,
  StreamCall,
  StreamVideo,
} from "@stream-io/video-react-sdk";

function HomePage() {
  const backendBaseUrl =
    import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

  const notif = [
    {
      text: "Risky climbing detected!",
      timestamp: "2:46 PM",
    },
    {
      text: "Intense emotional outburst detected!",
      timestamp: "2:42 PM",
    },
  ];
  const [activity, setActivity] = useState("");
  const [isRedetecting, setIsRedetecting] = useState(false);
  const [zoneText, setZoneText] = useState("");
  const [isReassessingZone, setIsReassessingZone] = useState(false);

  const { joinCall, leaveCall, client, call, status, isLive } = useVisionCall();

  const handleStart = async () => {
    try {
      const callId = "vision-test-1";
      await joinCall(callId);
    } catch (err) {
      console.error("Failed to start call/stream:", err);
      alert(`Failed to start stream: ${err?.message || err}`);
    }
  };

  const handleStop = async () => {
    await leaveCall();
    setActivity("");
    setZoneText("");
  };

  const handleRedetectActivity = async () => {
    if (!isLive) return;
    setIsRedetecting(true);
    try {
      const resp = await fetch(`${backendBaseUrl}/video/current-activity`, {
        method: "POST",
      });
      const payload = await resp.json();
      if (!resp.ok) {
        throw new Error(payload?.detail || `Request failed (${resp.status})`);
      }
      setActivity(payload.activity || "No activity description returned.");
    } catch (err) {
      console.error("Redetect activity failed:", err);
      setActivity(`Activity detection failed: ${err?.message || err}`);
    } finally {
      setIsRedetecting(false);
    }
  };

  const handleReassessZone = async () => {
    if (!isLive) return;
    setIsReassessingZone(true);
    try {
      const resp = await fetch(`${backendBaseUrl}/video/reassess-zone`, {
        method: "POST",
      });
      const payload = await resp.json();
      if (!resp.ok) {
        throw new Error(payload?.detail || `Request failed (${resp.status})`);
      }
      const bbox = payload.zone_bbox;
      const reason = payload.zone_reason || "unknown";
      if (Array.isArray(bbox) || (bbox && typeof bbox === "object")) {
        setZoneText(`${JSON.stringify(bbox)} (${reason})`);
      } else {
        setZoneText(`Not detected (${reason})`);
      }
    } catch (err) {
      console.error("Reassess zone failed:", err);
      setZoneText(`Zone reassess failed: ${err?.message || err}`);
    } finally {
      setIsReassessingZone(false);
    }
  };

  return (
    <div>
      <Navbar></Navbar>

      <div className="section">
        <h1 className="h1">Today's Events</h1>

        <div className="flex gap-8 w-full">
          <div className="flex flex-col items-start gap-8 w-full">
            <div className="w-full h-[40rem] bg-grey rounded-3xl overflow-hidden">
              {client && call ? (
                <div className="w-full h-full">
                  <StreamVideo client={client}>
                    <StreamCall call={call}>
                      <div className="w-full h-full flex flex-col">
                        <div className="flex-1 min-h-0">
                          <SpeakerLayout />
                        </div>
                        <div className="p-3 bg-black/60">
                          <CallControls />
                        </div>
                      </div>
                    </StreamCall>
                  </StreamVideo>
                </div>
              ) : (
                <div className="w-full h-full flex items-center justify-center text-slate-600">
                  Click Start to join call and begin monitoring
                </div>
              )}
            </div>

            <div className="flex flex-col gap-5 w-full">
              <h4 className="h4">Recent Observations</h4>

              <div className="flex flex-col gap-4 w-full">
                {notif.map((v, i) => (
                  <NotificationCard value={v}></NotificationCard>
                ))}
              </div>
            </div>
          </div>

          <div className="flex flex-col w-96 gap-7">
            <ActivityCard
              activity={activity}
              zoneText={zoneText}
              onStart={handleStart}
              onStop={handleStop}
              onRedetectActivity={handleRedetectActivity}
              isRedetecting={isRedetecting}
              onReassessZone={handleReassessZone}
              isReassessingZone={isReassessingZone}
              streamStatus={status}
              isLive={isLive}
            ></ActivityCard>

            <RegistrationCard></RegistrationCard>
          </div>
        </div>
      </div>
    </div>
  );
}

export default HomePage;
