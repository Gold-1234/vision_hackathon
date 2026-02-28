import { BrowserRouter, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import DailyReportsPage from "./pages/DailyReportsPage";
import GrowthTrendsPage from "./pages/GrowthTrendsPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage></HomePage>}></Route>
        <Route
          path="/reports"
          element={<DailyReportsPage></DailyReportsPage>}
        ></Route>
        <Route
          path="/trends"
          element={<GrowthTrendsPage></GrowthTrendsPage>}
        ></Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
