"""Target adapter tests: method, mapping, auth, and retry.

WHAT THESE PROVE
    The project's central extensibility claim is that **pointing RAGStrike at a different RAG system
    is a change to ``targets.yaml``, never a change to plugin code**. Until Phase 16 that claim was
    only ever exercised against one API shape -- VulnerableRAG's ``POST /chat`` -- which is the shape
    the adapter's defaults were written from.

    :func:`test_four_unrelated_api_shapes_need_only_configuration` is the test that actually puts the
    claim under load: four APIs that share no path, no method, no request shape, and no response
    shape, all driven through the same adapter with nothing but options.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from ragstrike.core.config.models import RetrySettings
from ragstrike.core.contracts.target_adapter import TargetRequest
from ragstrike.core.errors import ConfigurationError, TargetProtocolError, TargetUnreachableError
from ragstrike.models.entities.target import Authorization, Target
from ragstrike.target_adapters.fastapi.adapter import FastAPIAdapter
from ragstrike.target_adapters.fastapi.auth import build_auth
from ragstrike.target_adapters.fastapi.mapping import assign, extract

BASE = "http://127.0.0.1:9000"


def make_target(**options: Any) -> Target:
    return Target(
        id="t1",
        name="lab",
        adapter="fastapi",
        url=BASE,
        authorization=Authorization(authorized_by="tester", authorization_ref="LOCAL-LAB"),
        options=options,
    )


# ------------------------------------------------------------------------------------------------
# Mapping primitives
# ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "path", "expected"),
    [
        ({"answer": "hi"}, "answer", "hi"),
        ({"data": {"answer": "hi"}}, "data.answer", "hi"),
        ({"choices": [{"text": "hi"}]}, "choices.0.text", "hi"),
        ({"choices": [{"text": "hi"}]}, "$.choices[0].text", "hi"),
        ({"choices": [{"message": {"content": "hi"}}]}, "$..content", "hi"),
        ({"answer": "hi"}, "missing", None),
        ({"answer": "hi"}, "answer.deeper", None),
        ({"choices": []}, "choices.0.text", None),
    ],
)
def test_extract_resolves_dotted_and_jsonpath(body: Any, path: str, expected: Any) -> None:
    assert extract(body, path) == expected


def test_extract_returns_a_list_when_a_path_matches_several() -> None:
    """A wildcard that matched three things must not silently report only the first."""
    body = {"docs": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}

    assert extract(body, "$.docs[*].id") == ["a", "b", "c"]


def test_assign_creates_nested_objects() -> None:
    assert assign({}, "input.query", "hi") == {"input": {"query": "hi"}}


def test_assign_refuses_jsonpath() -> None:
    """A write path that can filter or wildcard has no single destination."""
    with pytest.raises(ConfigurationError):
        assign({}, "$.input.query", "hi")


# ------------------------------------------------------------------------------------------------
# The extensibility claim
# ------------------------------------------------------------------------------------------------

FOUR_APIS = [
    pytest.param(
        "/chat",
        "POST",
        {"prompt_field": "message", "answer_path": "answer"},
        {"answer": "chat-reply"},
        lambda body: body["message"] == "probe",
        id="POST /chat -- flat, the VulnerableRAG shape",
    ),
    pytest.param(
        "/generate",
        "POST",
        {"prompt_field": "input.query", "answer_path": "output.text"},
        {"output": {"text": "generate-reply"}},
        lambda body: body["input"]["query"] == "probe",
        id="POST /generate -- nested request and response",
    ),
    pytest.param(
        "/query",
        "PUT",
        {"prompt_field": "q", "answer_path": "$.choices[0].message.content"},
        {"choices": [{"message": {"content": "query-reply"}}]},
        lambda body: body["q"] == "probe",
        id="PUT /query -- answer inside a list, via JSONPath",
    ),
    pytest.param(
        "/ask",
        "POST",
        {"prompt_field": "question", "answer_path": "result"},
        {"result": "ask-reply"},
        lambda body: body["question"] == "probe",
        id="POST /ask -- different field names throughout",
    ),
]


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(("path", "method", "options", "response", "check_body"), FOUR_APIS)
async def test_four_unrelated_api_shapes_need_only_configuration(
    path: str,
    method: str,
    options: dict[str, Any],
    response: dict[str, Any],
    check_body: Any,
) -> None:
    """No plugin code, no adapter code -- only ``options``.

    If this test ever needs a change to ``adapter.py`` to pass, the extensibility claim has been
    broken and the README needs rewriting before the code does.
    """
    route = respx.request(method, f"{BASE}{path}").mock(
        return_value=httpx.Response(200, json=response)
    )
    adapter = FastAPIAdapter(make_target(chat_path=path, method=method, **options))

    result = await adapter.chat(TargetRequest(prompt="probe"))
    await adapter.close()

    assert result.text.endswith("-reply")
    assert result.ok
    assert check_body(json_of(route))


@respx.mock
@pytest.mark.asyncio
async def test_a_get_target_carries_the_prompt_in_the_query_string() -> None:
    route = respx.get(f"{BASE}/ask").mock(return_value=httpx.Response(200, json={"answer": "ok"}))
    adapter = FastAPIAdapter(
        make_target(chat_path="/ask", method="GET", prompt_field="q", answer_path="answer")
    )

    result = await adapter.chat(TargetRequest(prompt="probe"))
    await adapter.close()

    assert result.text == "ok"
    assert route.calls.last.request.url.params["q"] == "probe"


def test_an_unsupported_method_is_refused_at_construction() -> None:
    """Not at request time, when a scan is already ten minutes in."""
    with pytest.raises(ConfigurationError) as caught:
        FastAPIAdapter(make_target(method="DELETE"))

    assert "DELETE" in str(caught.value)


@respx.mock
@pytest.mark.asyncio
async def test_a_missing_answer_field_names_the_keys_that_were_there() -> None:
    respx.post(f"{BASE}/chat").mock(
        return_value=httpx.Response(200, json={"reply": "hi", "usage": {}})
    )
    adapter = FastAPIAdapter(make_target())

    with pytest.raises(TargetProtocolError) as caught:
        await adapter.chat(TargetRequest(prompt="probe"))
    await adapter.close()

    assert "reply" in caught.value.hint


# ------------------------------------------------------------------------------------------------
# Authentication
# ------------------------------------------------------------------------------------------------


def test_bearer_auth_reads_the_token_from_the_environment(monkeypatch: Any) -> None:
    monkeypatch.setenv("LAB_TOKEN", "s3cret")

    auth = build_auth({"auth": {"type": "bearer", "env": "LAB_TOKEN"}}, target_name="lab")

    assert auth.headers() == {"Authorization": "Bearer s3cret"}


def test_api_key_auth_defaults_its_header(monkeypatch: Any) -> None:
    monkeypatch.setenv("LAB_KEY", "abc123")

    auth = build_auth({"auth": {"type": "api_key", "env": "LAB_KEY"}}, target_name="lab")

    assert auth.headers() == {"X-API-Key": "abc123"}


def test_basic_auth_encodes_both_halves(monkeypatch: Any) -> None:
    monkeypatch.setenv("LAB_USER", "alice")
    monkeypatch.setenv("LAB_PASS", "hunter2")

    auth = build_auth(
        {"auth": {"type": "basic", "env": "LAB_PASS", "username_env": "LAB_USER"}},
        target_name="lab",
    )

    assert auth.headers() == {"Authorization": "Basic YWxpY2U6aHVudGVyMg=="}


def test_a_credential_never_appears_in_repr(monkeypatch: Any) -> None:
    """``repr`` reaches logs, tracebacks, and debugger output.

    A dataclass prints its fields by default, which would put the token in every one of those.
    """
    monkeypatch.setenv("LAB_TOKEN", "s3cret")

    auth = build_auth({"auth": {"type": "bearer", "env": "LAB_TOKEN"}}, target_name="lab")

    assert "s3cret" not in repr(auth)
    assert "***" in repr(auth)


def test_an_unset_credential_fails_at_construction(monkeypatch: Any) -> None:
    """Otherwise every request 401s and the report reads like a hardened target."""
    monkeypatch.delenv("ABSENT_TOKEN", raising=False)

    with pytest.raises(ConfigurationError) as caught:
        build_auth({"auth": {"type": "bearer", "env": "ABSENT_TOKEN"}}, target_name="lab")

    assert "ABSENT_TOKEN" in str(caught.value)


def test_auth_has_no_field_a_literal_secret_fits_in(monkeypatch: Any) -> None:
    """``targets.yaml`` is committed. The schema is the control, not the comment above it."""
    with pytest.raises(ConfigurationError):
        build_auth({"auth": {"type": "bearer", "token": "literal-secret"}}, target_name="lab")


@respx.mock
@pytest.mark.asyncio
async def test_a_stray_header_option_cannot_unset_the_credential(monkeypatch: Any) -> None:
    monkeypatch.setenv("LAB_TOKEN", "s3cret")
    route = respx.post(f"{BASE}/chat").mock(return_value=httpx.Response(200, json={"answer": "ok"}))
    adapter = FastAPIAdapter(
        make_target(
            headers={"Authorization": ""},
            auth={"type": "bearer", "env": "LAB_TOKEN"},
        )
    )

    await adapter.chat(TargetRequest(prompt="probe"))
    await adapter.close()

    assert route.calls.last.request.headers["authorization"] == "Bearer s3cret"


# ------------------------------------------------------------------------------------------------
# Retry
# ------------------------------------------------------------------------------------------------

NO_WAIT = RetrySettings(max_attempts=3, backoff_base_s=0.001, backoff_max_s=0.001)


@respx.mock
@pytest.mark.asyncio
async def test_a_5xx_is_retried_and_then_succeeds() -> None:
    route = respx.post(f"{BASE}/chat").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"answer": "recovered"}),
        ]
    )
    adapter = FastAPIAdapter(make_target(), retry=NO_WAIT)

    result = await adapter.chat(TargetRequest(prompt="probe"))
    await adapter.close()

    assert result.text == "recovered"
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_a_429_is_retried() -> None:
    """The one 4xx worth retrying, because it explicitly says "later"."""
    route = respx.post(f"{BASE}/chat").mock(
        side_effect=[httpx.Response(429), httpx.Response(200, json={"answer": "ok"})]
    )
    adapter = FastAPIAdapter(make_target(), retry=NO_WAIT)

    await adapter.chat(TargetRequest(prompt="probe"))
    await adapter.close()

    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_a_refusal_is_never_retried() -> None:
    """**The most important test in this file.**

    A target declining to answer is the most interesting result an attack pack can get. Retrying it
    would resend the payload, inflate the ``attempts`` count, and corrupt the
    ``successes / attempts`` exploitability ratio the whole scoring model rests on.
    """
    route = respx.post(f"{BASE}/chat").mock(return_value=httpx.Response(403, json={"detail": "no"}))
    adapter = FastAPIAdapter(make_target(), retry=NO_WAIT)

    result = await adapter.chat(TargetRequest(prompt="probe"))
    await adapter.close()

    assert route.call_count == 1
    assert not result.ok
    assert "403" in result.error


@respx.mock
@pytest.mark.asyncio
async def test_an_exhausted_retry_returns_the_status_as_data() -> None:
    """An attack that reliably provokes a 500 has learned something worth reporting."""
    route = respx.post(f"{BASE}/chat").mock(return_value=httpx.Response(500, text="boom"))
    adapter = FastAPIAdapter(make_target(), retry=NO_WAIT)

    result = await adapter.chat(TargetRequest(prompt="probe"))
    await adapter.close()

    assert route.call_count == 3
    assert not result.ok
    assert "500" in result.error


@respx.mock
@pytest.mark.asyncio
async def test_a_connection_refusal_raises_after_the_last_attempt() -> None:
    route = respx.post(f"{BASE}/chat").mock(side_effect=httpx.ConnectError("refused"))
    adapter = FastAPIAdapter(make_target(), retry=NO_WAIT)

    with pytest.raises(TargetUnreachableError):
        await adapter.chat(TargetRequest(prompt="probe"))
    await adapter.close()

    assert route.call_count == 3


def json_of(route: Any) -> dict[str, Any]:
    """The JSON body of a route's last request."""
    import json

    return dict(json.loads(route.calls.last.request.content))
