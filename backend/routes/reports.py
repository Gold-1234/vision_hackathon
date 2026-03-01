from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, desc
from datetime import datetime, timedelta, timezone

from database.connection import get_db
from database.models import SafetyEvent, Alert, Camera, Users

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/daily")
async def get_daily_reports(db: AsyncSession = Depends(get_db), limit: int = Query(7, ge=1, le=30)):
    """
    Returns an aggregated daily report of SafetyEvents and Alerts for the last 'limit' days.
    """
    try:
        # Get count of events grouped by date
        # Assuming postgresql, func.date(created_at) works. Otherwise we can use cast(created_at, Date)
        from sqlalchemy import cast, Date

        # Safety Events
        stmt_events = (
            select(
                cast(SafetyEvent.created_at, Date).label("day"),
                SafetyEvent.event_type,
                func.count(SafetyEvent.id).label("count")
            )
            .group_by(cast(SafetyEvent.created_at, Date), SafetyEvent.event_type)
            .order_by(desc(cast(SafetyEvent.created_at, Date)))
        )
        result_events = await db.execute(stmt_events)
        rows_events = result_events.all()

        # Alerts
        stmt_alerts = (
            select(
                cast(Alert.created_at, Date).label("day"),
                func.count(Alert.id).label("count")
            )
            .group_by(cast(Alert.created_at, Date))
            .order_by(desc(cast(Alert.created_at, Date)))
        )
        result_alerts = await db.execute(stmt_alerts)
        rows_alerts = result_alerts.all()

        # Group data into a single JSON structure
        report = {}
        for row in rows_events:
            date_str = str(row.day)
            if date_str not in report:
                report[date_str] = {"events": {}, "total_alerts": 0}
            report[date_str]["events"][row.event_type] = row.count

        for row in rows_alerts:
            date_str = str(row.day)
            if date_str not in report:
                report[date_str] = {"events": {}, "total_alerts": 0}
            report[date_str]["total_alerts"] = row.count

        # Take only the newest `limit` days
        sorted_dates = sorted(report.keys(), reverse=True)[:limit]
        final_report = []
        for d in sorted_dates:
            events_dict = report[d]["events"]
            total_alerts = report[d]["total_alerts"]
            
            # Format Date
            date_obj = datetime.strptime(d, "%Y-%m-%d")
            # Replace 0-padded day with non-padded if possible by using strftime correctly or replace
            formatted_date = date_obj.strftime("%A, %B %d, %Y").replace(" 0", " ")
            
            summary = "A balanced day with gentle exploration and calm rest periods."
            if total_alerts >= 3:
                summary = "An active day with several unexpected incidents requiring attention."
            elif total_alerts == 0:
                summary = "A peaceful day with steady rhythms and imaginative play."
                
            highlights = []
            suggestions = []
            
            falls_count = events_dict.get("FallDetected", 0)
            if falls_count > 0:
                highlights.append(f"{falls_count} falls were detected today." if falls_count > 1 else "1 fall was detected today.")
                suggestions.append("Check for injury and monitor responsiveness.")
                
            crying_count = events_dict.get("CryingDetected", 0)
            if crying_count > 0:
                highlights.append("Elevated emotional intensity or crying was observed.")
                suggestions.append("Offer safe emotional regulation alternatives.")
                
            toddler_count = events_dict.get("ToddlerDetected", 0)
            if toddler_count == 0 and sum(events_dict.values()) == 0:
                highlights.append("An extended inactivity period was detected.")
                suggestions.append("Encourage gentle movement and assess responsiveness.")
            elif toddler_count >= 3:
                highlights.append("High level of independent movement and exploration.")
                suggestions.append("Ensure safe boundaries during active play.")
                
            if len(highlights) == 0:
                highlights.append("Normal daily rhythms observed.")
                suggestions.append("Continue following standard observation routines.")

            final_report.append({
                "date": formatted_date,
                "summary": summary,
                "highlights": highlights,
                "suggestions": suggestions
            })
        
        return {"daily_reports": final_report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent")
async def get_recent_observations(db: AsyncSession = Depends(get_db), limit: int = Query(10, ge=1, le=50)):
    """
    Returns the most recent LLM Alerts and SafetyEvents.
    """
    try:
        # Get recent alerts
        stmt_alerts = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
        results_alerts = await db.execute(stmt_alerts)
        alerts = results_alerts.scalars().all()

        # Get recent events
        stmt_events = select(SafetyEvent).order_by(desc(SafetyEvent.created_at)).limit(limit)
        results_events = await db.execute(stmt_events)
        events = results_events.scalars().all()

        return {
            "recent_alerts": [
                {
                    "id": a.id,
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "timestamp": a.created_at,
                    "metadata": a.alert_metadata
                }
                for a in alerts
            ],
            "recent_events": [
                {
                    "id": e.id,
                    "type": e.event_type,
                    "confidence": e.confidence,
                    "timestamp": e.created_at,
                    "metadata": e.event_metadata
                }
                for e in events
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trends")
async def get_growth_trends(db: AsyncSession = Depends(get_db), days: int = Query(7, ge=1, le=30)):
    """
    Returns the growth trends based on recent observations calculated dynamically
    from the database.
    """
    try:
        now = datetime.now(timezone.utc)
        current_period_start = now - timedelta(days=days)
        previous_period_start = current_period_start - timedelta(days=days)

        # Helper query to get counts of a specific event type within a time range
        async def get_event_counts(event_type: str, start_time, end_time):
            stmt = select(func.count(SafetyEvent.id)).where(
                SafetyEvent.event_type == event_type,
                SafetyEvent.created_at >= start_time,
                SafetyEvent.created_at < end_time
            )
            result = await db.execute(stmt)
            return result.scalar_one()

        # Calculate growth for a specific event type
        async def calculate_trend(event_type: str):
            current = await get_event_counts(event_type, current_period_start, now)
            previous = await get_event_counts(event_type, previous_period_start, current_period_start)
            
            if previous == 0:
                return "Increasing" if current > 0 else "Stable"
            
            growth = ((current - previous) / previous) * 100
            if growth > 15:
                return "Increasing"
            elif growth < -15:
                return "Decreasing"
            else:
                return "Stable"

        # Calculate for our main categories
        falls_trend = await calculate_trend("FallDetected")
        crying_trend = await calculate_trend("CryingDetected")
        toddler_trend = await calculate_trend("ToddlerDetected")
        
        # Build the dynamic UI response
        trends_response = []
        
        # 1. Frequent Falls
        falls_desc = "Falls occurred more frequently than typical developmental variation." if falls_trend == "Increasing" else "Fall frequency matches or is lower than typical expected behavior."
        falls_insights = [
            "May indicate environmental obstacles, fatigue, or rapid motor experimentation.",
            "Review flooring, footwear, and obstacle placement to ensure safe exploration space."
        ] if falls_trend == "Increasing" else [
            "Environment appears well-suited for stable exploration.",
            "Continue standard monitoring routines."
        ]
        trends_response.append({
            "title": "Frequent Falls",
            "trend": falls_trend,
            "description": falls_desc,
            "insights": falls_insights
        })
        
        # 2. Aggression / Safety Alerts Trend (Approximated with general alerts for this mock)
        async def get_alerts_counts(start_time, end_time):
            stmt = select(func.count(Alert.id)).where(
                Alert.created_at >= start_time,
                Alert.created_at < end_time
            )
            return (await db.execute(stmt)).scalar_one()

        curr_alerts = await get_alerts_counts(current_period_start, now)
        prev_alerts = await get_alerts_counts(previous_period_start, current_period_start)
        alerts_trend = "Stable"
        if prev_alerts == 0:
            alerts_trend = "Increasing" if curr_alerts > 0 else "Stable"
        else:
            growth = ((curr_alerts - prev_alerts) / prev_alerts) * 100
            if growth > 15:
                alerts_trend = "Increasing"
            elif growth < -15:
                alerts_trend = "Decreasing"
                
        trends_response.append({
            "title": "Safety Incidents Trend",
            "trend": alerts_trend,
            "description": "General safety alerts requiring supervision." if alerts_trend == "Increasing" else "General safety alerts are steady or declining.",
            "insights": [
                "Review recent alert recordings to identify patterns or triggers.",
                "Ensure child-proofing measures are consistently applied."
            ]
        })

        # 3. Reduced Activity (ToddlerDetected)
        activity_trend = "Stable"
        if toddler_trend == "Decreasing":
             activity_trend = "Decreasing"
        elif toddler_trend == "Increasing":
             activity_trend = "Increasing"
             
        trends_response.append({
            "title": "Movement Activity",
            "trend": activity_trend,
            "description": "Movement levels are lower than expected." if activity_trend == "Decreasing" else "Activity levels match typical daily rhythm.",
            "insights": [
                "May be associated with fatigue, mild discomfort, or environmental under-stimulation." if activity_trend == "Decreasing" else "Balanced exploration observed.",
                "Encourage gentle physical engagement and monitor energy levels." if activity_trend == "Decreasing" else "Maintain current play environment and scheduling."
            ]
        })

        # 4. High Emotional Intensity (CryingDetected)
        trends_response.append({
            "title": "Emotional Intensity",
            "trend": crying_trend,
            "description": "Emotional responses were stronger or longer than typical baseline." if crying_trend == "Increasing" else "Emotional responses are matching standard expected variations.",
            "insights": [
                "May be linked to overstimulation, disrupted routines, or unmet comfort needs." if crying_trend == "Increasing" else "Comfort needs seem consistently met.",
                "Review routine consistency and reduce sensory load during peak emotional periods." if crying_trend == "Increasing" else "Continue regular comforting rhythms."
            ]
        })

        return {
            "trends": trends_response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

