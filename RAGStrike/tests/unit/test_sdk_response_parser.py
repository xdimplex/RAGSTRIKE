"""ResponseParser tests.

Several of these assert on the *honest limitation*, not just the happy path -- ``status_code()``
and ``headers()`` are best-effort against a ``TargetResponse`` that was never designed to carry
them, and the tests pin down exactly what that means rather than letting the behaviour drift
silently.
"""

from __future__ import annotations

from ragstrike.core.contracts.target_adapter import TargetResponse
from ragstrike.sdk.response_parser import ResponseParser


def make_response(**overrides) -> TargetResponse:
    defaults = {"text": "hello world", "latency_ms": 42, "session_id": "s1"}
    defaults.update(overrides)
    return TargetResponse(**defaults)


def test_text() -> None:
    assert ResponseParser(make_response(text="hi")).text() == "hi"


def test_chunks_and_sources_pass_through() -> None:
    response = make_response(retrieved_chunks=[{"text": "chunk"}], sources=["doc.pdf"])
    parser = ResponseParser(response)

    assert parser.chunks() == [{"text": "chunk"}]
    assert parser.sources() == ["doc.pdf"]


def test_chunks_default_to_empty_list() -> None:
    assert ResponseParser(make_response()).chunks() == []


def test_session_id_and_latency() -> None:
    parser = ResponseParser(make_response(session_id="abc", latency_ms=99))

    assert parser.session_id() == "abc"
    assert parser.latency_ms() == 99


def test_error_and_ok() -> None:
    clean = ResponseParser(make_response())
    assert clean.ok() is True
    assert clean.error() == ""

    broken = ResponseParser(make_response(text="", error="boom"))
    assert broken.ok() is False
    assert broken.error() == "boom"


# -- json() -----------------------------------------------------------------------------------


def test_json_parses_valid_json_text() -> None:
    parser = ResponseParser(make_response(text='{"key": "value"}'))

    assert parser.json() == {"key": "value"}


def test_json_returns_none_for_prose() -> None:
    """Most chat responses are prose. That is not a parsing failure worth raising over."""
    assert ResponseParser(make_response(text="This is a normal sentence.")).json() is None


# -- raw() / metadata() ------------------------------------------------------------------------


def test_raw_returns_the_verbatim_dict() -> None:
    response = make_response(raw={"foo": "bar"})

    assert ResponseParser(response).raw() == {"foo": "bar"}


def test_metadata_excludes_already_surfaced_keys() -> None:
    response = make_response(raw={"answer": "hi", "sources": ["x"], "extra_field": "kept"})

    metadata = ResponseParser(response).metadata()

    assert "answer" not in metadata
    assert "sources" not in metadata
    assert metadata == {"extra_field": "kept"}


# -- status_code(): best-effort, two fallback paths --------------------------------------------


def test_status_code_from_explicit_raw_key() -> None:
    response = make_response(raw={"status_code": 429})

    assert ResponseParser(response).status_code() == 429


def test_status_code_parsed_from_error_prefix() -> None:
    """This is the ONLY source of a status code today against the shipped FastAPIAdapter, which
    writes 'HTTP 404: ...' into TargetResponse.error and nothing into raw."""
    response = make_response(text="", error="HTTP 404: not found")

    assert ResponseParser(response).status_code() == 404


def test_status_code_is_none_when_neither_source_is_present() -> None:
    """The honest answer for a normal successful response today: nothing captures 200
    explicitly, so this must return None rather than guess."""
    assert ResponseParser(make_response()).status_code() is None


# -- headers(): honest about not being populated today ------------------------------------------


def test_headers_returns_empty_dict_by_default() -> None:
    """FastAPIAdapter does not populate a 'headers' key. This is the correct behaviour against
    every adapter shipped today, not a bug."""
    assert ResponseParser(make_response()).headers() == {}


def test_headers_returns_them_when_an_adapter_does_provide_them() -> None:
    response = make_response(raw={"headers": {"Content-Type": "application/json"}})

    assert ResponseParser(response).headers() == {"Content-Type": "application/json"}


# -- citations(): explicit key, else falls back to sources ---------------------------------------


def test_citations_prefers_explicit_citations_key() -> None:
    response = make_response(sources=["doc.pdf"], raw={"citations": ["cite-1", "cite-2"]})

    assert ResponseParser(response).citations() == ["cite-1", "cite-2"]


def test_citations_falls_back_to_sources() -> None:
    response = make_response(sources=["doc.pdf"])

    assert ResponseParser(response).citations() == ["doc.pdf"]


# -- excerpt() --------------------------------------------------------------------------------


def test_excerpt_returns_short_text_unchanged() -> None:
    assert ResponseParser(make_response(text="short")).excerpt(80) == "short"


def test_excerpt_truncates_long_text_with_ellipsis() -> None:
    long_text = "x" * 300
    excerpt = ResponseParser(make_response(text=long_text)).excerpt(10)

    assert len(excerpt) == 10
    assert excerpt.endswith("…")
