import Navbar from "../components/global/Navbar";
import GrowthCard from "../components/growth-trends/GrowthCard";

function GrowthTrendsPage() {
  const trends = [{
    name: 'Frequent Falls',
    status: 'Increasing',
    description: 'Falls occurred more frequently than typical developmental variation.',
    insights: [{
      id: 1,
      text: 'May indicate environmental obstacles, fatigue, or rapid motor experimentation.'
    },{
      id: 2,
      text: 'Review flooring, footwear, and obstacle placement to ensure safe exploration space.'
    }]
  }, {
    name: 'Aggression Trend',
    status: 'Decreasing',
    description: 'Repeated physical contact incidents requiring behavioral reinforcement.',
    insights: [{
      id: 1,
      text: 'May indicate environmental obstacles, fatigue, or rapid motor experimentation.'
    },{
      id: 2,
      text: 'Review flooring, footwear, and obstacle placement to ensure safe exploration space.'
    }]
  }, {
    name: 'Reduced Activity',
    status: 'Stable',
    description: 'Falls occurred more frequently than typical developmental variation.',
    insights: [{
      id: 1,
      text: 'May indicate environmental obstacles, fatigue, or rapid motor experimentation.'
    },{
      id: 2,
      text: 'Review flooring, footwear, and obstacle placement to ensure safe exploration space.'
    }]
  },{
    name: 'High Emotional Intensity',
    status: 'Increasing',
    description: 'Falls occurred more frequently than typical developmental variation.',
    insights: [{
      id: 1,
      text: 'May indicate environmental obstacles, fatigue, or rapid motor experimentation.'
    },{
      id: 2,
      text: 'Review flooring, footwear, and obstacle placement to ensure safe exploration space.'
    }]
  }, {
    name: 'Impulsive Behavior',
    status: 'Stable',
    description: 'Falls occurred more frequently than typical developmental variation.',
    insights: [{
      id: 1,
      text: 'May indicate environmental obstacles, fatigue, or rapid motor experimentation.'
    },{
      id: 2,
      text: 'Review flooring, footwear, and obstacle placement to ensure safe exploration space.'
    }]
  }]

  return (
    <div>
      <Navbar></Navbar>

      <div className="section">
        <h1 className="h1">Growth Trends</h1>

        <div className="grid grid-cols-2 gap-7">
          {trends.map((v, i) => (
            <GrowthCard value={v}></GrowthCard>
          ))}
        </div>
      </div>
    </div>
  );
}

export default GrowthTrendsPage;
