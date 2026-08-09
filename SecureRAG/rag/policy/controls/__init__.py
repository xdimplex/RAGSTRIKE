"""The security controls, and the one function that composes them.

ORDER IS PART OF THE DESIGN
    The chain applies every policy at every hook, in list order. The list below is ordered so that
    at each hook point the sub-order is correct:

    ============================  ==========================================================
    Hook                          Controls, in order
    ============================  ==========================================================
    ``on_ingest`` / ``on_chunk``  ContextSanitizer
    ``on_context_assembly``       InputValidator, then RetrievalFilter
    ``on_prompt_build``           SessionBounder
    ``on_response``               CitationGrounder, OutputFilter, then SecretMasker
    ============================  ==========================================================

    Two orderings matter and are not arbitrary:

    **InputValidator before RetrievalFilter.** A question that will be refused should be refused
    before anything spends effort filtering the chunks retrieved for it.

    **SecretMasker last.** It is the final thing that touches the answer, so nothing downstream can
    reintroduce a value it masked. Any control added later that inspects the answer must go *before*
    it -- a test asserts the masker is last, so this cannot be broken silently.

NO PARTIAL CHAINS
    :func:`build_controls` composes every implemented control. The secure profile's README states
    this as a rule -- "a partially composed chain" is forbidden -- because a control that exists in
    the tree but not in the chain is a defence an operator believes they have.

    The declared-but-unbuilt controls in :mod:`future_controls` are excluded by construction: they
    are pass-throughs, and composing them would produce silent no-op coverage.
"""

from typing import Any

from rag.policy.controls.citation_grounder import CitationGrounder
from rag.policy.controls.context_sanitizer import ContextSanitizer
from rag.policy.controls.future_controls import (
    DECLARED_CONTROLS,
    Authenticator,
    Authorizer,
    DeclaredControl,
    RateLimiter,
    describe_declared,
)
from rag.policy.controls.input_validator import InputValidator
from rag.policy.controls.output_filter import OutputFilter
from rag.policy.controls.retrieval_filter import RetrievalFilter
from rag.policy.controls.secret_masker import SecretMasker
from rag.policy.controls.session_bounder import SessionBounder
from rag.policy.protocol import SecurityPolicy

__all__ = [
    "DECLARED_CONTROLS",
    "Authenticator",
    "Authorizer",
    "CitationGrounder",
    "ContextSanitizer",
    "DeclaredControl",
    "InputValidator",
    "OutputFilter",
    "RateLimiter",
    "RetrievalFilter",
    "SecretMasker",
    "SessionBounder",
    "build_controls",
    "describe_declared",
]


def build_controls(security: Any, *, system_prompt: str = "") -> list[SecurityPolicy]:
    """Compose every implemented control, in chain order.

    Args:
        security: The validated ``SecuritySettings`` from ``configs/security.yaml``. Annotated as
            ``Any`` -- with justification -- to keep this module free of an import back to
            ``rag.config``, which imports the policy package to describe the chain. The attributes
            read below are validated by pydantic before they arrive here.
        system_prompt: The profile's system prompt. The output filter needs it to detect an echo;
            it cannot know what to look for otherwise.

    Returns:
        The controls, ordered as documented above. Never partial: a control whose configuration
        disables its individual checks is still composed, so ``GET /health`` reports it and an
        operator can see that it ran and did nothing, rather than seeing nothing at all.
    """
    sanitizer = security.sanitizer
    validation = security.validation
    retrieval = security.retrieval
    session = security.session
    output = security.output
    masking = security.masking
    citations = security.citations

    return [
        ContextSanitizer(
            normalize_unicode=sanitizer.normalize_unicode,
            strip_invisible=sanitizer.strip_invisible_characters,
            neutralize_instructions=sanitizer.neutralize_instructions,
        ),
        InputValidator(
            max_question_chars=validation.max_question_chars,
            min_question_chars=validation.min_question_chars,
            normalize_unicode=validation.normalize_unicode,
            reject_control_characters=validation.reject_control_characters,
        ),
        RetrievalFilter(
            min_score=retrieval.min_score,
            max_chunks=retrieval.max_chunks,
            max_chunk_chars=retrieval.max_chunk_chars,
            max_instruction_density=retrieval.max_instruction_density,
        ),
        SessionBounder(
            max_history_turns=session.max_history_turns,
            max_prompt_chars=session.max_prompt_chars,
        ),
        CitationGrounder(annotate=citations.annotate_ungrounded),
        OutputFilter(
            max_answer_chars=output.max_answer_chars,
            detect_prompt_echo=output.detect_prompt_echo,
            echo_window=output.echo_window,
            system_prompt=system_prompt,
            normalize_whitespace=output.normalize_whitespace,
        ),
        # Last, always. A test enforces this.
        SecretMasker(
            mask_emails=masking.mask_emails,
            mask_phone_numbers=masking.mask_phone_numbers,
            fingerprint_chars=masking.fingerprint_chars,
            refuse_on_secret=masking.refuse_on_secret,
            match_context_values=masking.match_context_values,
        ),
    ]
