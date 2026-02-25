# RANK: 6 - LLM-callable functions (Gemini tools) to process alerts emitted by detection events.

import logging
from typing import Annotated

# We use livekit.agents.llm to define functions the LLM can call
try:
    from livekit.agents import llm
except ImportError:
    # Fallback/mock if livekit is not installed yet
    class llm:
        @staticmethod
        def ai_callable(description=""):
            def decorator(func):
                return func
            return decorator

logger = logging.getLogger(__name__)

class NotificationTools:
    """
    A collection of functions that the Gemini AI can call 
    to dispatch alerts to the parents/users.
    """
    
    @llm.ai_callable(description="Send an immediate alert to the user about a safety concern.")
    async def send_alert(
        self, 
        alert_type: Annotated[str, llm.TypeInfo(description="The type of alert (e.g. 'Fall', 'Intruder', 'Edge Danger')")],
        message: Annotated[str, llm.TypeInfo(description="A descriptive message explaining what was detected.")],
        severity: Annotated[str, llm.TypeInfo(description="Severity level: 'low', 'medium', or 'high'")]
    ):
        """
        Records and dispatches a safety alert. 
        In the future, this could trigger an SMS, push notification, or GetStream event.
        """
        prefix = f"⚠️ [{severity.upper()}] {alert_type} Alert: "
        print(f"\n{'='*50}\n{prefix}{message}\n{'='*50}\n")
        
        # Here we would integrate with twilio / websockets / push notifications
        return f"Successfully dispatched {severity} severity alert for {alert_type}."