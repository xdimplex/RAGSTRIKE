"""``ragstrike.sdk.base`` -- the base classes every plugin builds its output from.

Four names, matching the Phase 5 brief exactly:

* :class:`BasePayload` -- a re-export of :class:`~ragstrike.plugins.base.attack.Payload`. Not a
  new type: the engine already defines what a payload is, and a plugin's ``payloads()`` method
  must return that exact type or the scheduler will not accept it. ``BasePayload`` is the SDK's
  name for it, so plugin code can write ``from ragstrike.sdk.base import BasePayload`` without
  knowing which internal module ``Payload`` actually lives in.
* :class:`BaseRecommendation` -- likewise, a re-export of
  :class:`~ragstrike.plugins.base.attack.Recommendation`.
* :class:`BaseResult` -- new in the SDK: :class:`~ragstrike.sdk.base.result.AttackResult`, the
  standard per-payload result object described in the Phase 5 brief. See ``result.py`` for why
  this is a plugin-internal bookkeeping type, folded into the engine's ``Analysis`` by
  :mod:`ragstrike.sdk.result_builder`, rather than a new engine contract.
* :class:`BaseEvidence` -- new in the SDK: one structured fact, accumulated via
  :class:`~ragstrike.sdk.base.evidence.EvidenceCollection` and folded into ``Analysis.evidence``.

**Why re-export rather than subclass.** ``Payload`` and ``Recommendation`` are frozen dataclasses
Phase 3/4 already finalized. Subclassing a frozen dataclass to add nothing would create a second
type the engine's ``isinstance`` checks and the scheduler's return-type expectations were never
written against. A plain alias means ``BasePayload(id=..., content=...)`` constructs *exactly* the
object the engine already accepts -- zero risk of an SDK type silently diverging from the engine
type it claims to represent.

Phase 6 adds a fifth name, :class:`EvaluationAttack` (with its :class:`Verdict`), for plugins that
check an expected security behaviour rather than exploit a weakness. It is optional and additive --
the four names above are unchanged, and the raw ``BaseAttack`` contract remains the reference style.
"""

from ragstrike.plugins.base.attack import Payload as BasePayload
from ragstrike.plugins.base.attack import Recommendation as BaseRecommendation
from ragstrike.sdk.base.evaluation import EvaluationAttack, Verdict
from ragstrike.sdk.base.evidence import BaseEvidence, EvidenceCollection
from ragstrike.sdk.base.result import AttackResult, utc_now
from ragstrike.sdk.base.result import AttackResult as BaseResult

__all__ = [
    "AttackResult",
    "BaseEvidence",
    "BasePayload",
    "BaseRecommendation",
    "BaseResult",
    "EvaluationAttack",
    "EvidenceCollection",
    "Verdict",
    "utc_now",
]
