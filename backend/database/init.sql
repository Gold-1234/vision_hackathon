-- Initial schema for Vision Monitor

CREATE TABLE IF NOT EXISTS safety_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    confidence FLOAT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_safety_events_type ON safety_events(event_type);
CREATE INDEX idx_safety_events_created_at ON safety_events(created_at);
CREATE INDEX idx_alerts_severity ON alerts(severity);
