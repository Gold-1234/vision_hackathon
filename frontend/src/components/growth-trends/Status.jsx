import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faArrowTrendUp,
  faArrowTrendDown,
  faArrowRightLong,
} from "@fortawesome/free-solid-svg-icons";

function Status({ text }) {
  let bgColor;
  let icon;

  if (text === "Increasing") {
    bgColor = "bg-secondary";
    icon = (
      <FontAwesomeIcon
        icon={faArrowTrendUp}
        style={{ color: "var(--secondary-trans)" }}
        size="xs"
      />
    );
  } else if (text === "Decreasing") {
    bgColor = "bg-primary";
    icon = (
      <FontAwesomeIcon
        icon={faArrowTrendDown}
        style={{ color: "var(--primary-trans)" }}
        size="xs"
      />
    );
  } else {
    bgColor = "bg-grey";
    icon = (
      <FontAwesomeIcon
        icon={faArrowRightLong}
        style={{ color: "var(--grey-trans)" }}
        size="xs"
      />
    );
  }

  return (
    <div className={`${bgColor} flex items-center gap-2 px-2.5 rounded-full`}>
      {icon}
      <p className="small white">{text}</p>
    </div>
  );
}

export default Status;
