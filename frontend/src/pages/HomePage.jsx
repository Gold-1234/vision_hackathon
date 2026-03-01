import { useState } from "react";
import Navbar from "../components/global/Navbar";
import ActivityCard from "../components/home/ActivityCard";
import NotificationCard from "../components/home/NotificationCard";
import useLiveStream from "../hooks/useLiveStream";
import useVisionCall from "../hooks/useVisionCall";
import RegistrationCard from "../components/home/RegistrationCard";

function HomePage() {
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

  const [url, setUrl] = useState("");
  const [isPlaying, setIsPlaying] = useState(false);
  const { imgRef, startStream, stopStream, status, isLive } =
    useLiveStream(url);

  const { joinCall, leaveCall } = useVisionCall();

  const handleStart = async () => {
    if (!url) {
      alert("Please enter stream URL first");
      return;
    }

    const callId = "vision-test-1";
    await joinCall(callId);
    startStream();

    setIsPlaying(true);
  };

  const handleStop = async () => {
    stopStream();
    await leaveCall();

    setIsPlaying(false);
  };

  return (
    <div>
      <Navbar></Navbar>

      <div className="section">
        <h1 className="h1">Today's Events</h1>

        <div className="flex gap-8 w-full">
          <div className="flex flex-col items-start gap-8 w-full">
            <div className="w-full h-[40rem] bg-grey rounded-3xl overflow-hidden">
              <img
                ref={imgRef}
                alt="Live stream"
                className="w-full h-full object-contain"
              />
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
              onStart={handleStart}
              onStop={handleStop}
              streamStatus={status}
              isLive={isLive}
              setUrl={setUrl}
              url={url}
              isPlaying={isPlaying}
            ></ActivityCard>

            <RegistrationCard></RegistrationCard>
          </div>
        </div>
      </div>
    </div>
  );
}

export default HomePage;
