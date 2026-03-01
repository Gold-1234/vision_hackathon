import { createSlice, createAsyncThunk } from "@reduxjs/toolkit";

// dummy
export const fetchDailyReports = createAsyncThunk(
  "reports/fetchDailyReports",
  async () => {
    const res = await fetch("/api/reports");
    return await res.json();
  },
);

const reportsSlice = createSlice({
  name: "reports",
  initialState: {
    dailyReports: [],
    loading: false,
    error: null,
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchDailyReports.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchDailyReports.fulfilled, (state, action) => {
        state.loading = false;
        state.dailyReports = action.payload;
      })
      .addCase(fetchDailyReports.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message;
      });
  },
});

export default reportsSlice.reducer;
