"""The single error envelope.

Every failure -- validation, application error, or unhandled exception -- comes back in this shape.
One shape means a client can parse errors without special cases, and it means the API keeps its
promise to always return JSON.

``hint`` is the field that matters in practice. "model_unavailable" tells you what broke;
"Start it with `ollama serve`" tells you what to do about it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(description="Machine-readable code, e.g. model_unavailable.")
    message: str = Field(description="What went wrong, in a sentence.")
    hint: str = Field(default="", description="What to do about it.")
    request_id: str = Field(default="", description="Correlates with the server log line.")


class ErrorResponse(BaseModel):
    error: ErrorDetail
