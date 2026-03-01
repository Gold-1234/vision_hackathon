import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faMagnifyingGlass } from "@fortawesome/free-solid-svg-icons";

function InsightCard({ value }) {
  let bgColor;
  let iconColor;
  let textColor;

  if (value.status === "Increasing") {
    bgColor = "bg-secondary-trans";
    textColor = "secondary";
    iconColor = "var(--secondary)";
  } else if (value.status === "Decreasing") {
    bgColor = "bg-primary-trans";
    textColor = "primary";
    iconColor = "var(--primary)";
  } else {
    bgColor = "bg-grey-trans";
    textColor = "grey";
    iconColor = "var(--grey)";
  }

  return (
    <div className={`${bgColor} flex flex-col gap-2 p-6 rounded-2xl `}>
      <div className="flex items-center gap-4">
        <FontAwesomeIcon
          icon={faMagnifyingGlass}
          style={{ color: iconColor }}
          size="lg"
        />
        <h5 className={`${textColor} h5`}>Insights</h5>
      </div>

      <ul className="list-disc list-inside ml-3">
        {value.insights.map((v, i) => (
          <li key={v.id} className="list">
            {v.text}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default InsightCard;
