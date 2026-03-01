import { use, useState } from "react";
import InputBox from "./InputBox";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faPlus } from "@fortawesome/free-solid-svg-icons";

function RegistrationCard() {
  const [name, setName] = useState("");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    if (!name || !file) {
      alert("Please enter name and select an image.");
      return;
    }

    try {
      setLoading(true);

      const formData = new FormData();
      formData.append("call_id", "vision-test-1");
      formData.append("name", name);
      formData.append("image", file);

      const res = await fetch("http://127.0.0.1:8000/faces/enroll", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (data.ok) {
        alert(`Successfully registered ${data.name}`);
        setName("");
        setFile(null);
      } else {
        alert("Registration failed.");
      }
    } catch (err) {
      console.error(err);
      alert("Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col bg-white p-6 box-shadow rounded-3xl gap-7 w-full">
      <h4 className="h4 text-center">Face Registration</h4>

      <div className="flex flex-col gap-4">
        <InputBox
          label={"Name"}
          type={"text"}
          placeholder={"Enter the person's name"}
          value={name}
          onChange={(e) => setName(e.target.value)}
        ></InputBox>

        <div className="flex flex-col gap-2">
          <label htmlFor="input" className="h5 neutral">
            Face Image
          </label>

          <input
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files[0])}
            className="p1 bg-grey-trans w-full focus:outline focus:outline-[#898989] rounded-2xl py-3 px-4"
          />
        </div>
      </div>

      <button
        className={`bg-primary-trans primary h5 flex gap-4 items-center cursor-pointer py-3 px-5 rounded-xl hover:scale-105 transition-all duration-300 ${
          loading ? "opacity-50 cursor-not-allowed" : ""
        }`}
        onClick={handleRegister}
        disabled={loading}
      >
        <FontAwesomeIcon icon={faPlus} style={{ color: "var(--primary) " }} />
        {loading ? "Registering..." : "Register Person"}
      </button>
    </div>
  );
}

export default RegistrationCard;
