"""Request and response models for ``POST /chat``.

This is the contract RAGStrike's HTTP adapter maps onto with JSONPath, so the field names matter more
than they normally would: renaming ``answer`` to ``response`` later would silently break every
configured target definition. Treat this shape as stable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        description=(
            "The question. Taken verbatim: no length cap, no encoding normalization, no content "
            "inspection. All three would be security controls (weakness V6)."
        ),
        examples=["What is the remote work policy?"],
    )
    session_id: str | None = Field(
        default=None,
        description="Continue an existing conversation. A new session is created when omitted.",
    )
    top_k: int | None = Field(
        default=None, ge=1, le=50, description="Override the configured retrieval depth."
    )
    include_prompt: bool = Field(
        default=False,
        description=(
            "Return the fully assembled prompt. Enabled so the exact text sent to the model is "
            "inspectable -- which is how an indirect injection is confirmed rather than guessed."
        ),
    )


class RetrievedChunkModel(BaseModel):
    chunk_id: str
    document_id: str
    source_name: str
    page: int
    index: int
    text: str
    score: float
    distance: float


class ChatResponse(BaseModel):
    answer: str
    question: str
    session_id: str
    model: str
    elapsed_ms: int
    chunk_count: int
    retrieved_chunks: list[RetrievedChunkModel] = Field(
        default_factory=list,
        description=(
            "The chunks that produced this answer. Exposed deliberately: retrieval introspection is "
            "what makes retrieval-integrity and citation testing possible, and what makes an "
            "injection visible to a learner rather than invisible."
        ),
    )
    sources: list[str] = Field(
        default_factory=list,
        description=(
            "Distinct source documents actually retrieved. Note this is the HONEST list. Any "
            "citations inside `answer` come from the model and are not checked against it "
            "(weakness V9)."
        ),
    )
    prompt: str | None = Field(
        default=None, description="The assembled prompt, when `include_prompt` was set."
    )
    raw_response: str | None = Field(
        default=None,
        description="Model output before <think> stripping. Often where an injection first shows.",
    )


class ResetSessionRequest(BaseModel):
    session_id: str


class ResetSessionResponse(BaseModel):
    session_id: str
    reset: bool


class SessionTurn(BaseModel):
    """One recorded message. `role` is "user" or "assistant"."""

    role: str
    content: str


class SessionHistoryResponse(BaseModel):
    """A conversation, oldest turn first, so a refreshed page can rebuild itself."""

    session_id: str
    turns: list[SessionTurn] = Field(default_factory=list)
