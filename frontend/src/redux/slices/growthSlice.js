import { createSlice, createAsyncThunk } from "@reduxjs/toolkit";

// dummy
export const fetchGrowthPatterns = createAsyncThunk(
  "growth/fetchGrowthPatterns",
  async () => {
    const res = await fetch("/api/growth");
    return await res.json();
  },
);

const growthSlice = createSlice({
  name: "growth",
  initialState: {
    patterns: [],
    loading: false,
    error: null,
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchGrowthPatterns.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchGrowthPatterns.fulfilled, (state, action) => {
        state.loading = false;
        state.patterns = action.payload;
      })
      .addCase(fetchGrowthPatterns.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message;
      });
  },
});

export default growthSlice.reducer;
