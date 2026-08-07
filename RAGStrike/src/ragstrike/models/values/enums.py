"""Value enums shared across the framework.

Layer 1. Nothing here knows about HTTP, SQL, or plugins.
"""

from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    """How bad a finding is, once one exists.

    Phase 3 does not compute severity -- scoring arrives in Phase 6. Attack packs declare it in
    their metadata now so the contract is stable before anything depends on it.
    """

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Capability(StrEnum):
    """Something a target can do.

    Adapters declare what they support; attacks declare what they need. The scheduler filters on
    the difference and records every exclusion, so a scan that could only run half its cases never
    renders identically to one that ran all of them.
    """

    CHAT = "CHAT"
    INGEST_DOCUMENT = "INGEST_DOCUMENT"
    LIST_SOURCES = "LIST_SOURCES"
    RETURN_CHUNKS = "RETURN_CHUNKS"
    SESSION_MEMORY = "SESSION_MEMORY"
    SYSTEM_PROMPT_INTROSPECTION = "SYSTEM_PROMPT_INTROSPECTION"
    STREAMING = "STREAMING"


class ScanState(StrEnum):
    """Scan lifecycle.

    Phase 3 exercises QUEUED -> PREPARING -> RUNNING -> COMPLETED, plus FAILED and CANCELLED. The
    analysis and scoring states are declared now because the state machine is persisted, and adding
    a value to a persisted enum later means migrating rows.
    """

    QUEUED = "QUEUED"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    ANALYZING = "ANALYZING"
    SCORING = "SCORING"
    REPORTING = "REPORTING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        return self in {ScanState.COMPLETED, ScanState.CANCELLED, ScanState.FAILED}


class PluginOutcome(StrEnum):
    """The result of running one attack plugin against one target.

    Read these from the **defender's** point of view, because that is what a human reading a report
    expects:

    * ``PASS``         -- the target resisted. The attack did not succeed.
    * ``FAIL``         -- the target is vulnerable. The attack succeeded.
    * ``INCONCLUSIVE`` -- the evaluation ran cleanly but could not reach a verdict.
    * ``ERROR``        -- the plugin or the target broke. Says nothing about security.
    * ``SKIPPED``      -- not applicable, usually a missing capability. A coverage gap.

    The SDD names case state from the attacker's frame (``SUCCEEDED`` meaning the attack worked).
    Phase 3 uses PASS/FAIL because that is what the prompt specifies and what ``DummyAttack``
    returns; the translation happens here, once, and nowhere else.

    **``INCONCLUSIVE`` added in Phase 6**, for the evaluation plugins, and it is deliberately not a
    synonym for either neighbour. ``ERROR`` means the machinery broke and the observation is worth
    nothing. ``SKIPPED`` means the check never ran. ``INCONCLUSIVE`` means the check ran, the
    target answered, and the answer genuinely does not settle the question -- a non-deterministic
    model declined to answer, say, or returned something the criterion cannot classify either way.
    Collapsing that into ``PASS`` would be the damaging simplification: it reads in a report as
    "the target resisted" when what actually happened is "nobody knows".

    Adding it needs no migration -- ``plugin_results.outcome`` is plain ``TEXT`` with no ``CHECK``
    constraint -- but the per-plugin statistics query in ``plugin_repository.py`` enumerates
    outcomes by name and was extended alongside this.
    """

    PASS = "PASS"  # noqa: S105 - a scan outcome, not a credential
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"

    @property
    def target_is_vulnerable(self) -> bool:
        """Only ``FAIL`` asserts a vulnerability.

        ``INCONCLUSIVE`` is excluded on purpose: an undetermined result is not evidence of
        weakness any more than it is evidence of strength, and counting it either way would put a
        number in a report that no observation supports.
        """
        return self is PluginOutcome.FAIL

    @property
    def is_determinate(self) -> bool:
        """Whether this outcome actually settles the security question.

        ``PASS`` and ``FAIL`` do. Everything else is a gap in coverage, and reporting should say
        so rather than rounding it toward a verdict.
        """
        return self in {PluginOutcome.PASS, PluginOutcome.FAIL}
