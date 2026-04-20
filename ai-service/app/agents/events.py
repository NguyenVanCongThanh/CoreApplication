"""
ai-service/app/agents/events.py

SSE Event Schema for the Agent chat system.

Defined once and used by the ReAct loop, FastAPI endpoint, and frontend.
Each event type maps to a specific frontend rendering behaviour:

  text_delta     -> append to streaming text bubble
  thinking       -> show reasoning indicator (collapsible)
  tool_start     -> show tool loading spinner
  tool_result    -> show tool result summary
  ui_component   -> render dynamic widget (QuizPreview, Chart, etc.)
  clarification  -> show clarification question with options
  hitl_request   -> show human-in-the-loop approval widget
  done           -> mark message as complete
  error          -> show error state
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class AgentEventType(str, Enum):
    TEXT_DELTA     = "text_delta"
    THINKING       = "thinking"
    TOOL_START     = "tool_start"
    TOOL_RESULT    = "tool_result"
    UI_COMPONENT   = "ui_component"
    CLARIFICATION  = "clarification"
    HITL_REQUEST   = "hitl_request"
    SESSION        = "session"
    DONE           = "done"
    ERROR          = "error"


class AgentEvent(BaseModel):
    type: AgentEventType
    data: Any
    session_id: str
    turn_id: Optional[str] = None

    def to_sse(self) -> str:
        """Format as SSE data line."""
        import json
        payload = self.model_dump(mode="json")
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
