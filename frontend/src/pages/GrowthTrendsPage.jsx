import { useEffect, useState } from "react";
import Navbar from "../components/global/Navbar";
import GrowthCard from "../components/growth-trends/GrowthCard";

function GrowthTrendsPage() {
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrends();
  }, []);

  const fetchTrends = async () => {
    try {
      const res = await fetch(
        "http://127.0.0.1:8000/api/reports/trends?days=7",
      );

      const data = await res.json();

      const formatted = data.trends.map((item) => ({
        name: item.title,
        status: item.trend,
        description: item.description,
        insights: item.insights.map((text, index) => ({
          id: index,
          text,
        })),
      }));

      setTrends(formatted);
    } catch (err) {
      console.error("Failed to fetch trends:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Navbar></Navbar>

      <div className="section">
        <h1 className="h1">Growth Trends</h1>

        {loading ? (
          <p className="p1">Loading trends...</p>
        ) : (
          <div className="grid grid-cols-2 gap-7">
            {trends.map((v, i) => (
              <GrowthCard key={i} value={v} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default GrowthTrendsPage;
