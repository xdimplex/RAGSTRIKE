"""``POST /chat`` -- ask a question.

The primary attack surface, and the endpoint RAGStrike will spend most of its time against.

The question is passed to the pipeline verbatim. Nothing normalizes its encoding, caps its length,
or inspects its content, and nothing filters what comes back. The response deliberately includes the
retrieved chunks and (on request) the assembled prompt, because an injection that cannot be inspected
cannot be confirmed -- only guessed at.

``POST /chat/reset`` clears one session. It exists so a poisoning demonstration can prove the effect
survives into a *new*, clean session rather than lingering in conversation history.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from backend.dependencies import get_engine
from backend.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ResetSessionRequest,
    ResetSessionResponse,
    RetrievedChunkModel,
    SessionHistoryResponse,
    SessionTurn,
)
from rag.engine import Engine
from rag.errors import InvalidRequestError
from rag.policy.controls.input_validator import InputValidator

log = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse, summary="Ask a question about the corpus")
async def chat(
    engine: Annotated[Engine, Depends(get_engine)],
    request: ChatRequest,
) -> ChatResponse:
    if not request.message.strip():
        raise InvalidRequestError(
            "The message is empty.", hint="Send a question in the `message` field."
        )

    # -----------------------------------------------------------------------------------------
    # Validate at the boundary, BEFORE the pipeline.
    #
    # The InputValidator also runs inside the chain, at `on_context_assembly` -- but that hook
    # fires *after* retrieval, and retrieval embeds the question. An over-long question therefore
    # reached the embedding model and returned a 500 ("the input length exceeds the context
    # length") before the control that exists to bound it ever ran. The chain could refuse the
    # request but could not prevent the expensive call, which is most of what the limit is for.
    #
    # A test caught this. The fix is the same shape as the upload path: cheap checks in front of
    # the expensive component. The in-chain validator stays, so a non-HTTP caller is still
    # protected and the control keeps its place in the documented chain.
    # -----------------------------------------------------------------------------------------
    InputValidator(
        max_question_chars=engine.settings.security.validation.max_question_chars,
        min_question_chars=engine.settings.security.validation.min_question_chars,
        normalize_unicode=engine.settings.security.validation.normalize_unicode,
        reject_control_characters=engine.settings.security.validation.reject_control_characters,
    ).validate(request.message)

    # The pipeline is synchronous end to end (Chroma and httpx both block), so it runs in a worker
    # thread. A single slow model call must not stall every other request.
    answer = await run_in_threadpool(
        engine.query.ask,
        question=request.message,
        session_id=request.session_id,
        top_k=request.top_k,
    )

    expose_chunks = engine.settings.api.expose_retrieved_chunks
    expose_sources = engine.settings.api.expose_sources

    return ChatResponse(
        answer=answer.text,
        question=answer.question,
        session_id=answer.session_id,
        model=answer.model,
        elapsed_ms=answer.elapsed_ms,
        chunk_count=answer.chunk_count,
        retrieved_chunks=(
            [RetrievedChunkModel(**r.to_dict()) for r in answer.retrieved] if expose_chunks else []
        ),
        sources=answer.sources if expose_sources else [],
        prompt=answer.prompt if request.include_prompt else None,
        raw_response=answer.raw_response if request.include_prompt else None,
    )


@router.post(
    "/chat/reset", response_model=ResetSessionResponse, summary="Clear one conversation session"
)
async def reset_session(
    engine: Annotated[Engine, Depends(get_engine)],
    request: ResetSessionRequest,
) -> ResetSessionResponse:
    engine.memory.reset(request.session_id)
    return ResetSessionResponse(session_id=request.session_id, reset=True)


@router.get(
    "/chat/session/{session_id}",
    response_model=SessionHistoryResponse,
    summary="Replay one conversation",
)
async def session_history(
    engine: Annotated[Engine, Depends(get_engine)],
    session_id: str,
) -> SessionHistoryResponse:
    """Every turn recorded for a session, oldest first.

    WHY THIS EXISTS
        The chat page kept its conversation in Streamlit's session state and the session ID in the
        URL. Streamlit discards session state on a browser refresh, so F5 left the operator holding
        a valid session ID pointing at a conversation the UI could no longer display -- the history
        vanished from the screen while still existing on the server and still being replayed into
        every subsequent prompt. The transcript was not lost; only the client's copy of it was.

        With this route the page can rebuild what it is already part of.

    READ-ONLY, and it returns what the model was actually shown -- the same turns
    ``SessionMemory.history`` replays into the next prompt. A "history" that disagreed with the
    prompt would be a second, subtly wrong record of the conversation.
    """
    turns = engine.memory.history(session_id)
    return SessionHistoryResponse(
        session_id=session_id,
        turns=[SessionTurn(role=str(t.get("role", "")), content=str(t.get("content", ""))) for t in turns],
    )
