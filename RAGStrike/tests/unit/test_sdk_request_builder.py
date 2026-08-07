"""TargetRequestBuilder tests."""

from __future__ import annotations

from ragstrike.sdk.request_builder import HttpMethod, RawRequestSpec, TargetRequestBuilder


def test_build_sets_the_prompt() -> None:
    request = TargetRequestBuilder().with_prompt("hello").build()

    assert request.prompt == "hello"


def test_an_unset_timeout_defers_to_the_target() -> None:
    """No timeout set means None, NOT the SDK default.

    This test previously asserted ``== DEFAULT_TIMEOUT_S`` and so locked in a real defect. The
    adapter resolves ``request.timeout_s or self.target.timeout_s``; stamping 60 here meant the
    right-hand side was unreachable and the ``timeout:`` in configs/targets.yaml never applied to
    an attack payload. Leaving it None is what lets an operator raise the timeout for a slow target.
    """
    request = TargetRequestBuilder().with_prompt("x").build()

    assert request.timeout_s is None


def test_explicit_timeout_overrides_the_default() -> None:
    request = TargetRequestBuilder().with_prompt("x").with_timeout(5).build()

    assert request.timeout_s == 5


def test_session_and_correlation_id() -> None:
    request = (
        TargetRequestBuilder()
        .with_prompt("x")
        .with_session("sess-1")
        .with_correlation_id("corr-1")
        .build()
    )

    assert request.session_id == "sess-1"
    assert request.correlation_id == "corr-1"


def test_session_defaults_to_none() -> None:
    assert TargetRequestBuilder().with_prompt("x").build().session_id is None


def test_metadata_key_value() -> None:
    request = TargetRequestBuilder().with_prompt("x").with_metadata("foo", "bar").build()

    assert request.metadata["foo"] == "bar"


def test_header_is_staged_under_metadata_headers() -> None:
    """Documented as not yet consumed by the shipped adapter -- this only checks it is staged."""
    request = TargetRequestBuilder().with_prompt("x").with_header("X-Test", "1").build()

    assert request.metadata["headers"] == {"X-Test": "1"}


def test_multiple_headers_accumulate() -> None:
    request = (
        TargetRequestBuilder().with_prompt("x").with_header("A", "1").with_header("B", "2").build()
    )

    assert request.metadata["headers"] == {"A": "1", "B": "2"}


def test_cookie_is_staged_under_metadata_cookies() -> None:
    request = TargetRequestBuilder().with_prompt("x").with_cookie("session", "abc").build()

    assert request.metadata["cookies"] == {"session": "abc"}


def test_auth_is_staged_as_scheme_and_credential() -> None:
    request = TargetRequestBuilder().with_prompt("x").with_auth("Bearer", "tok123").build()

    assert request.metadata["auth"] == {"scheme": "Bearer", "credential": "tok123"}


def test_builder_is_fluent_and_reusable_per_call() -> None:
    """Every method returns self; a fresh builder per request avoids stale state leaking
    between payloads."""
    first = TargetRequestBuilder().with_prompt("one").build()
    second = TargetRequestBuilder().with_prompt("two").build()

    assert first.prompt == "one"
    assert second.prompt == "two"


def test_building_performs_no_io() -> None:
    """Building is not sending -- there is no way to accidentally reach a network from here."""
    builder = TargetRequestBuilder().with_prompt("x")
    request = builder.build()

    assert request.prompt == "x"  # constructed a plain value object, nothing more


# -- architecture-only placeholders -------------------------------------------------------------


def test_http_method_enum_has_get_and_post() -> None:
    assert HttpMethod.GET == "GET"
    assert HttpMethod.POST == "POST"


def test_raw_request_spec_defaults() -> None:
    spec = RawRequestSpec()

    assert spec.method is HttpMethod.POST
    assert spec.headers == {}
    assert spec.body is None
    assert spec.stream is False
    assert spec.retries is None


def test_raw_request_spec_is_not_wired_to_anything() -> None:
    """It is a plain dataclass with no behaviour -- constructing one must not require a target,
    an adapter, or any I/O."""
    spec = RawRequestSpec(method=HttpMethod.GET, path="/aux", params={"q": "1"})

    assert spec.path == "/aux"
    assert spec.params == {"q": "1"}
