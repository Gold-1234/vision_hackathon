import { useEffect, useRef, useState } from "react";
import PlayButton from "./PlayButton";

function ActivityCard({
  activity,
  zoneText,
  onStart,
  onStop,
  streamStatus,
  isLive,
  onRedetectActivity,
  isRedetecting,
  onReassessZone,
  isReassessingZone,
}) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (isPlaying && isLive) {
      intervalRef.current = setInterval(() => {
        setTime((prevTime) => prevTime + 1000);
      }, 1000);
    } else {
      clearInterval(intervalRef.current);
    }

    return () => {
      clearInterval(intervalRef.current);
    };
  }, [isPlaying, isLive]);

  const handlePlay = () => {
    if (!isPlaying) {
      setTime(0);
      onStart && onStart();
    } else {
      onStop && onStop();
    }

    setIsPlaying(!isPlaying);
  };

  const formatTime = (milliseconds) => {
    const totalSeconds = Math.floor(milliseconds / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    return [hours, minutes, seconds]
      .map((num) => num.toString().padStart(2, "0"))
      .join(":");
  };

  return (
    <div className="flex flex-col bg-white p-6 box-shadow rounded-3xl gap-7">
      <PlayButton isPlaying={isPlaying} onClick={handlePlay}></PlayButton>

      <div className="flex flex-col gap-2">
        <h4 className="h4">Current Activity</h4>
        <div className="flex items-center gap-4">
          <div className="bg-grey w-2 h-2 rounded"></div>
          <p className="p1">
            {activity ? activity : "Please start the session"}
          </p>
        </div>

        <button
          type="button"
          onClick={onRedetectActivity}
          disabled={!isLive || isRedetecting}
          className="mt-2 rounded-lg bg-black text-white px-3 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRedetecting ? "Detecting..." : "Redetect Activity"}
        </button>

        <button
          type="button"
          onClick={onReassessZone}
          disabled={!isLive || isReassessingZone}
          className="rounded-lg bg-red-600 text-white px-3 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isReassessingZone ? "Reassessing Zone..." : "Reassess Zone"}
        </button>

        <div className="bg-grey-trans px-4 py-1 rounded-lg">
          <p className="small grey">Current Zone: {zoneText || "Not set"}</p>
        </div>
      </div>

      <div className="">
        <div className="bg-grey-trans px-4 py-1 rounded-lg mb-2">
          <p className="small grey">Session duration: {formatTime(time)}</p>
        </div>

        <div className="bg-grey-trans px-4 py-1 rounded-lg">
          <p className="small grey">Stream: {streamStatus}</p>
        </div>
      </div>
    </div>
  );
}

export default ActivityCard;
