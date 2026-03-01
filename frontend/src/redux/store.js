import { configureStore } from "@reduxjs/toolkit";
import home from "./slices/homeSlice";
import reports from "./slices/reportsSlice";
import growth from "./slices/growthSlice";

const store = configureStore({
  reducer: { home, reports, growth },
});

export default store;
