import Navbar from "../components/global/Navbar";
import ReportDropdown from "../components/daily-reports/ReportDropdown";

function DailyReportsPage() {
  const reports = [
    {
      date: "Monday, February 23, 2026",
      header: "A balanced day with gentle exploration and calm rest periods.",
      activities: [
        {
          id: 1,
          text: "3 falls were detected today.",
        },
        {
          id: 2,
          text: "Self-impact behavior was observed.",
        },
        {
          id: 3,
          text: "An extended inactivity period was detected.",
        },
      ],
      suggestions: [
        {
          id: 1,
          text: "Check for injury and monitor responsiveness.",
        },
        {
          id: 2,
          text: "Offer safe emotional regulation alternatives.",
        },
        {
          id: 3,
          text: "Encourage gentle movement and assess responsiveness.",
        },
      ],
    },
    {
      date: "Sunday, February 22, 2026",
      header: "A peaceful day with steady rhythms and imaginative play.",
      activities: [
        {
          id: 1,
          text: "3 falls were detected today.",
        },
        {
          id: 2,
          text: "Self-impact behavior was observed.",
        },
        {
          id: 3,
          text: "An extended inactivity period was detected.",
        },
      ],
      suggestions: [
        {
          id: 1,
          text: "Check for injury and monitor responsiveness.",
        },
        {
          id: 2,
          text: "Offer safe emotional regulation alternatives.",
        },
        {
          id: 3,
          text: "Encourage gentle movement and assess responsiveness.",
        },
      ],
    },
    {
      date: "Saturday, February 21, 2026",
      header: "A lively and exploratory day with high morning energy.",
      activities: [
        {
          id: 1,
          text: "3 falls were detected today.",
        },
        {
          id: 2,
          text: "Self-impact behavior was observed.",
        },
        {
          id: 3,
          text: "An extended inactivity period was detected.",
        },
      ],
      suggestions: [
        {
          id: 1,
          text: "Check for injury and monitor responsiveness.",
        },
        {
          id: 2,
          text: "Offer safe emotional regulation alternatives.",
        },
        {
          id: 3,
          text: "Encourage gentle movement and assess responsiveness.",
        },
      ],
    },
  ];

  return (
    <div>
      <Navbar></Navbar>

      <div className="section">
        <h1 className="h1">Daily Reports</h1>

        <div className="flex flex-col gap-7">
          {reports.map((v, i) => (
            <ReportDropdown value={v}></ReportDropdown>
          ))}
        </div>
      </div>
    </div>
  );
}

export default DailyReportsPage;
