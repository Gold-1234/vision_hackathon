import Status from "./Status";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faPersonFallingBurst,
  faPersonCircleExclamation,
} from "@fortawesome/free-solid-svg-icons";
import {
  faFaceAngry,
  faFaceSadTear,
  faFaceMehBlank,
} from "@fortawesome/free-regular-svg-icons";
import InsightCard from "./InsightCard";

function GrowthCard({ value }) {
  let icon;

  if (value.name === "Frequent Falls") {
    icon = (
      <FontAwesomeIcon
        icon={faPersonFallingBurst}
        style={{ color: "var(--neutral)" }}
        size="lg"
      />
    );
  } else if (value.name === "High Emotional Intensity") {
    icon = (
      <FontAwesomeIcon
        icon={faFaceSadTear}
        style={{ color: "var(--neutral)" }}
        size="lg"
      />
    );
  } else if (value.name === "Impulsive Behavior") {
    icon = (
      <FontAwesomeIcon
        icon={faPersonCircleExclamation}
        style={{ color: "var(--neutral)" }}
        size="lg"
      />
    );
  } else if (value.name === "Aggression Trend") {
    icon = (
      <FontAwesomeIcon
        icon={faFaceAngry}
        style={{ color: "var(--neutral)" }}
        size="lg"
      />
    );
  } else {
    icon = (
      <FontAwesomeIcon
        icon={faFaceMehBlank}
        style={{ color: "var(--neutral)" }}
        size="lg"
      />
    );
  }

  return (
    <div className="flex flex-col gap-6 bg-white box-shadow p-7 rounded-3xl">
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {icon}
            <h4 className="h4">{value.name}</h4>
          </div>

          <Status text={value.status}></Status>
        </div>

        <p className="p1">{value.description}</p>
      </div>

      <InsightCard value={value}></InsightCard>
    </div>
  );
}

export default GrowthCard;
