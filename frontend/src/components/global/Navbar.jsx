import { useNavigate } from "react-router-dom";

function Navbar() {
  const navigate = useNavigate();

  return (
    <div className="bg-white py-5 px-20 flex justify-between items-center">
      <img src="./logo.svg" alt="logo" className="w-20" />

      <nav className="flex items-center gap-10">
        <button
          className="p1 hover:primary hover:h5 cursor-pointer"
          onClick={() => navigate("/")}
        >
          Home
        </button>
        <button
          className="p1 hover:primary hover:h5 cursor-pointer"
          onClick={() => navigate("/reports")}
        >
          Daily Reports
        </button>
        <button
          className="p1 hover:primary hover:h5 cursor-pointer"
          onClick={() => navigate("/trends")}
        >
          Growth Trends
        </button>
      </nav>
    </div>
  );
}

export default Navbar;
