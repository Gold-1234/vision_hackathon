function InputBox({ label, placeholder, value, onChange }) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor="input" className="h5 neutral">
        {label}
      </label>
      <input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        id="input"
        className="p1 bg-grey-trans w-full focus:outline focus:outline-[#898989] rounded-2xl py-3 px-4"
      />
    </div>
  );
}

export default InputBox;
