import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faLightbulb, faStar } from "@fortawesome/free-solid-svg-icons";

function ReportCard({ isActivity, value }) {
  let textColor;
  let text;
  let bgColor;
  if (isActivity) {
    textColor = "primary";
    text = 'Activity Highlights';
    bgColor = 'bg-primary-trans'
  } else {
    textColor = "secondary";
    text = 'Suggestions'
    bgColor = 'bg-secondary-trans'
  }

  return (
    <div className={`flex flex-col gap-3 ${bgColor} p-6 rounded-2xl`}>
      <div className="flex items-center gap-4">
        <div className=''>
        {isActivity ? <FontAwesomeIcon icon={faStar} style={{ color: 'var(--primary)' }} /> : <FontAwesomeIcon icon={faLightbulb} style={{ color: 'var(--secondary)' }} />}
        </div>
        <p className={`${textColor} h5`}>{text}</p>
      </div>

      <ul className="list-disc list-inside ml-3">
        {value.map((v, i) => (
          <li key={v.id} className="list">{v.text}</li>
        ))}
      </ul>
    </div>
  );
}

export default ReportCard;
