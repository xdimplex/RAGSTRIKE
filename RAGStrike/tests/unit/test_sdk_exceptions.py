"""SDK exception hierarchy tests.

The property that matters here is not "can I construct these" but "does each one land where a
plugin author or the engine would expect to catch it" -- i.e. the inheritance chain, since that
chain is what lets ``except RAGStrikeError`` (CLI) and ``except TargetUnreachableError`` (engine)
keep working against SDK-raised exceptions without either one knowing the SDK exists.
"""

from __future__ import annotations

from ragstrike.core.errors import (
    ConfigurationError,
    PluginError,
    RAGStrikeError,
    TargetTimeoutError,
    TargetUnreachableError,
)
from ragstrike.sdk.exceptions import (
    PayloadError,
    PluginConfigurationError,
    PluginTimeoutError,
    SdkError,
    TargetConnectionError,
    ValidationError,
)


def test_sdk_error_is_a_ragstrike_error() -> None:
    assert issubclass(SdkError, RAGStrikeError)


def test_payload_error_is_a_plugin_error() -> None:
    assert issubclass(PayloadError, PluginError)
    assert issubclass(PayloadError, RAGStrikeError)


def test_validation_error_is_an_sdk_error() -> None:
    assert issubclass(ValidationError, SdkError)


def test_target_connection_error_is_still_catchable_as_target_unreachable() -> None:
    """The engine's existing ``except TargetUnreachableError`` must keep working unmodified."""
    assert issubclass(TargetConnectionError, TargetUnreachableError)


def test_plugin_configuration_error_is_a_configuration_error() -> None:
    assert issubclass(PluginConfigurationError, ConfigurationError)


def test_plugin_timeout_error_is_still_catchable_as_target_timeout() -> None:
    assert issubclass(PluginTimeoutError, TargetTimeoutError)


def test_plugin_timeout_error_is_not_named_timeout_error() -> None:
    """Regression guard for the deliberate naming decision documented in the exceptions module --
    shadowing the builtin ``TimeoutError`` would make ``except TimeoutError`` ambiguous."""
    assert PluginTimeoutError.__name__ != "TimeoutError"


def test_every_sdk_exception_carries_a_message_and_optional_hint() -> None:
    error = ValidationError("something failed", hint="do this instead")

    assert error.message == "something failed"
    assert error.hint == "do this instead"
    assert str(error) == "something failed"


def test_hint_defaults_to_empty_string() -> None:
    assert SdkError("boom").hint == ""


def test_each_exception_has_a_distinct_error_code() -> None:
    codes = {
        SdkError("x").code,
        PayloadError("x").code,
        ValidationError("x").code,
        TargetConnectionError("x").code,
        PluginConfigurationError("x").code,
        PluginTimeoutError("x").code,
    }

    assert len(codes) == 6


def test_all_sdk_exceptions_are_catchable_as_ragstrike_error() -> None:
    for exc_cls in (
        SdkError,
        PayloadError,
        ValidationError,
        TargetConnectionError,
        PluginConfigurationError,
        PluginTimeoutError,
    ):
        try:
            raise exc_cls("boom")
        except RAGStrikeError as caught:
            assert isinstance(caught, exc_cls)
        else:
            raise AssertionError(f"{exc_cls} was not caught as RAGStrikeError")
