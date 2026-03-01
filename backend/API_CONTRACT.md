# API Contract

This document outlines the available REST API endpoints provided by the Vision Hackathon backend for the frontend to consume.

All endpoints are hosted under `http://localhost:8000`.

---

## 1. Reports API (Prefix: `/api/reports`)

### 1.1 Daily Reports
Returns aggregated safety events and alerts grouped by day.

- **Endpoint:** `GET /api/reports/daily`
- **Query Parameters:**
  - `limit` (int, optional): The number of days to return. Default is `7`. Minimum `1`, Maximum `30`.

**Response (200 OK):**
```json
{
  "daily_reports": [
    {
      "date": "Monday, March 01, 2026",
      "summary": "An active day with several unexpected incidents requiring attention.",
      "highlights": [
        "2 falls were detected today.",
        "Elevated emotional intensity or crying was observed."
      ],
      "suggestions": [
        "Check for injury and monitor responsiveness.",
        "Offer safe emotional regulation alternatives."
      ]
    },
    {
      "date": "Sunday, February 28, 2026",
      "summary": "An active day with several unexpected incidents requiring attention.",
      "highlights": [
        "1 fall was detected today.",
        "Elevated emotional intensity or crying was observed.",
        "High level of independent movement and exploration."
      ],
      "suggestions": [
        "Check for injury and monitor responsiveness.",
        "Offer safe emotional regulation alternatives.",
        "Ensure safe boundaries during active play."
      ]
    }
  ]
}
```

### 1.2 Growth Trends
Returns categorized insights based on recent safety observations. This data provides qualitative insights and trends (e.g., "Increasing" / "Decreasing") rather than raw counts.

- **Endpoint:** `GET /api/reports/trends`
- **Query Parameters:**
  - `days` (int, optional): The number of days used to calculate the trend. Default is `7`. Minimum `1`, Maximum `30`.

**Response (200 OK):**
```json
{
  "trends": [
    {
      "title": "Frequent Falls",
      "trend": "Increasing",
      "description": "Falls occurred more frequently than typical developmental variation.",
      "insights": [
        "May indicate environmental obstacles, fatigue, or rapid motor experimentation.",
        "Review flooring, footwear, and obstacle placement to ensure safe exploration space."
      ]
    },
    {
      "title": "Aggression Trend",
      "trend": "Decreasing",
      "description": "Repeated physical contact incidents requiring behavioral reinforcement.",
      "insights": [
        "May indicate difficulty regulating frustration or expressing boundaries.",
        "Model safe emotional expression and reinforce consistent behavioral boundaries."
      ]
    },
    {
      "title": "Reduced Activity",
      "trend": "Stable",
      "description": "Movement levels were lower than expected for typical daily rhythm.",
      "insights": [
        "May be associated with fatigue, mild discomfort, or environmental under-stimulation.",
        "Encourage gentle physical engagement and monitor energy levels."
      ]
    },
    {
      "title": "High Emotional Intensity",
      "trend": "Increasing",
      "description": "Emotional responses were stronger or longer than typical baseline.",
      "insights": [
        "May be linked to overstimulation, disrupted routines, or unmet comfort needs.",
        "Review routine consistency and reduce sensory load during peak emotional periods."
      ]
    }
  ]
}
```

### 1.3 Recent Observations
Returns the most recent alert and safety event logs individually.

- **Endpoint:** `GET /api/reports/recent`
- **Query Parameters:**
  - `limit` (int, optional): The maximum number of alerts/events to return. Default is `10`. Minimum `1`, Maximum `50`.

**Response (200 OK):**
```json
{
  "recent_alerts": [
    {
      "id": 1,
      "type": "SafetyAlert",
      "severity": "High",
      "message": "Something happened",
      "timestamp": "2026-03-01T21:22:43Z",
      "metadata": {
        "test": true
      }
    }
  ],
  "recent_events": [
    {
      "id": 15,
      "type": "FallDetected",
      "confidence": 0.9177,
      "timestamp": "2026-03-01T14:22:43Z",
      "metadata": {
        "test": true
      }
    }
  ]
}
```

---

## 2. Video Stream API (Prefix: `/video`)

### 2.1 Video Stream Status
Returns the status of the video publisher and stream availability.

- **Endpoint:** `GET /video/status`
- **Response (200 OK):**
```json
{
  "publisher_initialized": true,
  "has_frame": true
}
```

### 2.2 Live Video Stream
Returns a live Multipart MJPEG stream of the active camera feed with AI bounding boxes.

- **Endpoint:** `GET /video/stream`
- **Response (200 OK):** `multipart/x-mixed-replace; boundary=frame`
- **Response (503 Service Unavailable):** Returned if the video publisher is not initialized or no frames are available yet.

---

## 3. Audio & Crying Detection API (Prefix: `/audio`)

### 3.1 Crying Detection Status
Returns the real-time status and confidence metrics from the crying audio detector.

- **Endpoint:** `GET /audio/crying/status`
- **Response (200 OK):**
```json
{
  "initialized": true,
  "enabled": true,
  "cry_detected": false,
  "cry_score": 0.05,
  "top_label": "Speech",
  "top_score": 0.85,
  "alarm_active": false,
  "recent_predictions": [],
  "last_audio_ts": 1709325942.123,
  "disable_reason": ""
}
```
