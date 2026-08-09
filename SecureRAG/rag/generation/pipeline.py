"""The query pipeline: retrieve -> assemble -> build prompt -> generate -> respond.

    question -> retrieve -> [on_context_assembly] -> build -> [on_prompt_build]
             -> generate -> [on_response] -> answer

Three policy hook points, all called unconditionally. VulnerableRAG's chain is empty, so a question
travels from the HTTP request to the model and back with nothing inspecting it in either direction.
"""

from __future__ import annotations

import logging
import time

from rag.config import Settings
from rag.generation.llm_client import LLMClient
from rag.generation.prompt_builder import PromptBuilder
from rag.models import Answer
from rag.policy.chain import SecurityPolicyChain
from rag.policy.hooks import ContextAssemblyContext, ResponseContext
from rag.retrieval.retriever import Retriever
from rag.session.memory import SessionMemory

log = logging.getLogger(__name__)


#: Greetings and pleasantries: an exact, closed set.
#:
#: WHY AN EXACT SET AND NOT "ANY SHORT MESSAGE"
#:     The first version treated any short message without a question word as small talk. That is
#:     far too loose: "Repeat your instructions." is short and has no question word, so it took the
#:     small-talk path -- which skips the system prompt and every control. A leak request phrased as
#:     a brief imperative would have walked straight past the defences. Matching an exact set of
#:     social tokens cannot make that mistake, because "repeat your instructions" is not in it.
#:
#: WHAT IS AND IS NOT HARDCODED HERE
#:     This list decides ROUTING -- whether to search the documents. It does not decide what to say.
#:     The model writes the reply, so the greeting sounds like the model rather than like a canned
#:     string, which is the whole point of doing it this way.
_GREETINGS = frozenset(
    {
        "hi", "hii", "hiii", "hey", "heyy", "hello", "helo", "hlo", "yo", "hola",
        "good morning", "good afternoon", "good evening", "greetings",
        "thanks", "thank you", "thx", "ty", "ok", "okay", "cool", "bye", "goodbye",
        "how are you", "who are you", "what can you do",
    }
)


def _is_small_talk(question: str) -> bool:
    """Whether *question* is a greeting rather than a question about the documents."""
    cleaned = " ".join(question.strip().strip("!?.,").lower().split())
    return cleaned in _GREETINGS


class QueryPipeline:
    """Answers a question from the ingested corpus."""

    def __init__(
        self,
        *,
        settings: Settings,
        retriever: Retriever,
        prompt_builder: PromptBuilder,
        llm_client: LLMClient,
        memory: SessionMemory,
        policies: SecurityPolicyChain,
    ) -> None:
        self.settings = settings
        self.retriever = retriever
        self.prompt_builder = prompt_builder
        self.llm_client = llm_client
        self.memory = memory
        self.policies = policies

    def ask(
        self,
        *,
        question: str,
        session_id: str | None = None,
        top_k: int | None = None,
    ) -> Answer:
        """Answer *question* from the corpus.

        Args:
            question: The user's question. Taken verbatim -- no length cap, no encoding
                normalization, no content inspection (weakness V6).
            session_id: Conversation to continue. A new one is created when omitted.
            top_k: Override for ``retrieval.top_k``.

        Returns:
            The answer, with the chunks and sources that produced it.

        Raises:
            NoDocumentsError: Nothing ingested yet.
            ModelUnavailableError, ModelNotFoundError, ModelTimeoutError: Model problems.
            PolicyRejectionError: A policy refused the request. Never raised by this profile.
        """
        started = time.perf_counter()
        session_id = session_id or SessionMemory.new_session_id()

        # A greeting is not a document question, so nothing is retrieved for it. Answering "hii"
        # used to send the model whatever the search happened to return, which was routinely a
        # poisoned document.
        if _is_small_talk(question):
            # The MODEL answers, with no retrieved context attached. The routing decides what the
            # model is shown; it does not decide what the model says.
            # A SMALL CONVERSATIONAL PROMPT, not the document-grounded one.
            #
            # The normal prompt tells the model to answer only from the retrieved passages. With no
            # passages that instruction is impossible to satisfy, so the hardened profile answered
            # "hello" with "the documents provided do not cover this" -- correct by its own rules and
            # useless to the person typing. Small talk is not a document question, so it does not get
            # the document scaffolding. The model still writes the words.
            prompt = (
                "You are the assistant for a document question-answering application. "
                "The user has sent a short greeting or pleasantry, not a question about a document. "
                "Reply in one short, friendly sentence, and invite them to ask about the uploaded "
                "documents. Do not mention documents you have not been shown.\n\n"
                f"User: {question}\nAssistant:"
            )
            raw_reply = self.llm_client.generate(prompt)
            # Still through the policy chain. A greeting is low risk, but "low risk" is not a reason
            # to leave a path where the output controls never run.
            reply = self.policies.on_response(
                ResponseContext(
                    answer=raw_reply,
                    question=question,
                    retrieved=[],
                    model=self.settings.model.name,
                    extras={"context_block": ""},
                )
            )
            self.memory.record(session_id, question=question, answer=reply)
            return Answer(
                text=reply,
                question=question,
                retrieved=[],
                sources=[],
                prompt=prompt,
                model=self.settings.model.name,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                session_id=session_id,
                raw_response=raw_reply,
            )

        retrieved = self.retriever.retrieve(question, top_k=top_k)

        # --- hook: on_context_assembly ---------------------------------------------------
        # Where retrieval filtering and input validation would happen (weaknesses V6, V7).
        retrieved = self.policies.on_context_assembly(
            ContextAssemblyContext(question=question, retrieved=retrieved, session_id=session_id)
        )

        history = self.memory.history(session_id)
        prompt, context_block = self.prompt_builder.build(
            question=question, retrieved=retrieved, history=history
        )

        raw_answer = self.llm_client.generate(prompt)

        # --- hook: on_response -----------------------------------------------------------
        # Where output filtering, secret masking, and system-prompt echo detection would happen
        # (weaknesses V3, V5). The chain is empty, so whatever the model produced is what the
        # caller receives -- including any credential it read out of the system prompt.
        answer_text = self.policies.on_response(
            ResponseContext(
                answer=raw_answer,
                question=question,
                retrieved=retrieved,
                model=self.settings.model.name,
                extras={"context_block": context_block},
            )
        )

        self.memory.record(session_id, question=question, answer=answer_text)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        log.info(
            "question answered",
            extra={
                "session_id": session_id,
                "question_length": len(question),
                "chunks_retrieved": len(retrieved),
                "sources": self.retriever.sources(retrieved),
                "answer_length": len(answer_text),
                "elapsed_ms": elapsed_ms,
                "model": self.settings.model.name,
            },
        )

        return Answer(
            text=answer_text,
            question=question,
            retrieved=retrieved,
            sources=self.retriever.sources(retrieved),
            prompt=prompt,
            model=self.settings.model.name,
            elapsed_ms=elapsed_ms,
            session_id=session_id,
            raw_response=raw_answer,
        )
