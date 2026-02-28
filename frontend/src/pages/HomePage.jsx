import Navbar from "../components/global/Navbar";
import ActivityCard from "../components/home/ActivityCard";
import NotificationCard from "../components/home/NotificationCard";

function HomePage() {
  const notif = [
    {
      text: "Risky climbing detected!",
      timestamp: "2:46 PM",
    },
    {
      text: "Intense emotional outburst detected!",
      timestamp: "2:42 PM",
    },
  ];

  return (
    <div>
      <Navbar></Navbar>

      <div className="section">
        <h1 className="h1">Today's Events</h1>

        <div className="flex flex-col gap-8">
          <div className="flex items-start gap-8">
            <div className="w-full h-[40rem] bg-grey rounded-3xl"></div>
            <ActivityCard></ActivityCard>
          </div>

          <div className="flex flex-col gap-5">
            <h4 className="h4">Recent Observations</h4>
            <div className="flex flex-col gap-4 mr-[21rem]">
              {notif.map((v, i) => (
                <NotificationCard value={v}></NotificationCard>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default HomePage;
