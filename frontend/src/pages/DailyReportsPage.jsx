import { useEffect, useState } from "react";
import Navbar from "../components/global/Navbar";
import ReportDropdown from "../components/daily-reports/ReportDropdown";

function DailyReportsPage() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDailyReports();
  }, []);

  const fetchDailyReports = async () => {
    try {
      const res = await fetch(
        "http://127.0.0.1:8000/api/reports/daily?limit=7",
      );

      const data = await res.json();

      const formatted = data.daily_reports.map((report) => ({
        date: report.date,
        header: report.summary,
        activities: report.highlights.map((text, index) => ({
          id: `a-${index}`,
          text,
        })),
        suggestions: report.suggestions.map((text, index) => ({
          id: `s-${index}`,
          text,
        })),
      }));

      setReports(formatted);
    } catch (err) {
      console.error("Failed to fetch daily reports:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Navbar />

      <div className="section">
        <h1 className="h1">Daily Reports</h1>

        {loading ? (
          <p className="p1">Loading reports...</p>
        ) : (
          <div className="flex flex-col gap-7">
            {reports.map((v, i) => (
              <ReportDropdown key={i} value={v} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default DailyReportsPage;
