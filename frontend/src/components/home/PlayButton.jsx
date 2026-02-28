import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faPlay, faPause } from "@fortawesome/free-solid-svg-icons";

function PlayButton({ onClick, isPlaying }) {
  let btnStyle;
  let text;

  if (isPlaying) {
    btnStyle = "bg-secondary-trans secondary";
    text = "Stop Session";
  } else {
    btnStyle = "bg-primary-trans primary";
    text = "Start Session";
  }

  return (
    <button
      className={`${btnStyle} h5 flex gap-4 items-center cursor-pointer py-3 px-5 rounded-xl hover:scale-105 transition-all duration-300`}
      onClick={onClick}
    >
      {isPlaying ? (
        <FontAwesomeIcon icon={faPause} style={{ color: "var(--secondary)" }} />
      ) : (
        <FontAwesomeIcon icon={faPlay} style={{ color: "var(--primary)" }} />
      )}

      {text}
    </button>
  );
}

export default PlayButton;
