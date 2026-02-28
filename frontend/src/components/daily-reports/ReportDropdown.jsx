import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faAngleUp } from "@fortawesome/free-solid-svg-icons";
import { useState } from "react";
import ReportCard from "./ReportCard";

function ReportDropdown({ value }) {
  const [isOpen, setIsOpen] = useState(false);

  let rotate;
  if (isOpen) {
    rotate = "180deg";
  } else {
    rotate = "0deg";
  }

  return (
    <div className="flex flex-col gap-7 bg-white box-shadow rounded-3xl px-8 py-7">
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <h4 className="h4">{value.date}</h4>
          <button className="cursor-pointer" onClick={() => setIsOpen(!isOpen)}>
            <FontAwesomeIcon icon={faAngleUp} style={{ rotate: rotate }} />
          </button>
        </div>

        <p className="p1">{value.header}</p>
      </div>

      {isOpen && (
        <div className="flex flex-col gap-6">
          <ReportCard isActivity={true} value={value.activities}></ReportCard>
          <ReportCard isActivity={false} value={value.suggestions}></ReportCard>
        </div>
      )}
    </div>
  );
}

export default ReportDropdown;
