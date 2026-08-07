"""RAGStrike Attack SDK.

Everything a plugin needs beyond the bare :class:`~ragstrike.plugins.base.attack.BaseAttack`
contract, so a real attack is metadata, payloads, and a success criterion -- not request
plumbing, response parsing, or result bookkeeping reinvented per plugin. See
``docs/sdk-guide.md`` for the full guide and a worked example under 100 lines.

Quick reference::

    from ragstrike.sdk import (
        BasePayload, BaseRecommendation, BaseResult, BaseEvidence,   # base
        ScanContext,                                                  # context
        TargetRequestBuilder,                                        # request_builder
        ResponseParser,                                               # response_parser
        SdkPayloadLoader,                                            # payload_loader
        ResultBuilder, fold_results, pick_recommendation,            # result_builder
        Timer, new_uuid, FileHelper, JsonHelper, YamlHelper, retry_async,  # helpers
        StringUtils, FormattingUtils,                                 # utils
    )
    from ragstrike.sdk import validators
    from ragstrike.sdk import exceptions
    from ragstrike.sdk import constants
    from ragstrike.sdk import interfaces

No import-time side effects, matching the convention set by ``ragstrike/__init__.py``: nothing
here registers, connects, or configures anything on import.
"""

from ragstrike.sdk import constants, exceptions, interfaces, validators
from ragstrike.sdk.base import (
    AttackResult,
    BaseEvidence,
    BasePayload,
    BaseRecommendation,
    BaseResult,
    EvidenceCollection,
)
from ragstrike.sdk.context import ScanContext
from ragstrike.sdk.helpers import (
    FileHelper,
    JsonHelper,
    Timer,
    YamlHelper,
    new_short_id,
    new_uuid,
    retry_async,
)
from ragstrike.sdk.payload_loader import LoadResult, SdkPayloadLoader, SkippedPayloadFile
from ragstrike.sdk.request_builder import HttpMethod, RawRequestSpec, TargetRequestBuilder
from ragstrike.sdk.response_parser import ResponseParser
from ragstrike.sdk.result_builder import ResultBuilder, fold_results, pick_recommendation
from ragstrike.sdk.utils import FormattingUtils, StringUtils

__all__ = [
    "AttackResult",
    "BaseEvidence",
    "BasePayload",
    "BaseRecommendation",
    "BaseResult",
    "EvidenceCollection",
    "FileHelper",
    "FormattingUtils",
    "HttpMethod",
    "JsonHelper",
    "LoadResult",
    "RawRequestSpec",
    "ResponseParser",
    "ResultBuilder",
    "ScanContext",
    "SdkPayloadLoader",
    "SkippedPayloadFile",
    "StringUtils",
    "TargetRequestBuilder",
    "Timer",
    "YamlHelper",
    "constants",
    "exceptions",
    "fold_results",
    "interfaces",
    "new_short_id",
    "new_uuid",
    "pick_recommendation",
    "retry_async",
    "validators",
]
