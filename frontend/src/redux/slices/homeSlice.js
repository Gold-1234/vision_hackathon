import { createSlice, createAsyncThunk } from "@reduxjs/toolkit";

// dummy
export const fetchNotifications = createAsyncThunk(
  "home/fetchNotifications",
  async () => {
    const res = await fetch("/api/notifications");
    return await res.json();
  },
);

const homeSlice = createSlice({
  name: "home",
  initialState: {
    notifications: [],
    currentActivity: null,
    loading: false,
    error: null,
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchNotifications.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchNotifications.fulfilled, (state, action) => {
        state.loading = false;
        state.notifications = action.payload;
      })
      .addCase(fetchNotifications.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message;
      });
  },
});

export default homeSlice.reducer;
