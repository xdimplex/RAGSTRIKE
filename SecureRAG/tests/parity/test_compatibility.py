"""Compatibility tests -- the drift gate.

WHY THIS FILE IS THE MOST IMPORTANT ONE IN THE REPOSITORY

    ADR-009 rejected two independent repositories for one reason: *they drift*. A UI change lands in
    one, a chunker is tuned in the other, and once they diverge the differential comparison stops
    measuring security and starts measuring incidental difference -- **while continuing to look
    correct**. That failure mode is silent, which is what makes it dangerous.

    SecureRAG was built as a separate repository anyway, on an explicit decision. This file is the
    mitigation. It is the executable half of ``docs/compatibility-guide.md``: it asserts that the two
    applications expose the same endpoints with the same response schemas, and it fails loudly the
    moment one side grows a field the other lacks.

WHAT IT ASSERTS AND WHAT IT CANNOT

    It compares SecureRAG against a **recorded contract** -- the endpoint set and the response field
    names -- rather than against a live VulnerableRAG, because a test that needs a second repository
    checked out beside this one is a test that gets skipped in CI and rots.

    The contract below was extracted from VulnerableRAG at the commit this repository was forked
    from. When VulnerableRAG changes its API, this file must be updated deliberately, and that edit
    is the moment someone notices the two have diverged. That is the entire point: make drift require
    a decision instead of happening by omission.

    ``scripts/check_compatibility.py`` compares against a live VulnerableRAG when one is running, for
    the stronger check. This suite is the one that always runs.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

# =================================================================================================
# The recorded contract.
#
# Extracted from VulnerableRAG. Every entry here is a promise SecureRAG makes to a client that was
# written against the other application.
# =================================================================================================

#: Every route both applications must expose, as ``(method, path)``.
CONTRACT_ROUTES: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("POST", "/upload"),
    ("GET", "/documents"),
    # Chunk inspection is how an operator confirms what was actually stored for a document. It is
    # part of the contract because RAGStrike's retrieval-integrity checks read it.
    ("GET", "/documents/{document_id}/chunks"),
    ("DELETE", "/documents/{document_id}"),
    ("POST", "/chat"),
    ("POST", "/chat/reset"),
}

#: The five the brief names explicitly as unchangeable.
REQUIRED_BY_BRIEF: set[tuple[str, str]] = {
    ("POST", "/upload"),
    ("POST", "/chat"),
    ("GET", "/documents"),
    ("DELETE", "/documents/{document_id}"),
    ("GET", "/health"),
}

CONTRACT_HEALTH_FIELDS: set[str] = {
    "status",
    "profile",
    "version",
    "model",
    "embedding_model",
    "document_count",
    "chunk_count",
    "session_count",
    "components",
    "capabilities",
    "security_policies",
    "system_prompt",
    "warning",
}

CONTRACT_CHAT_FIELDS: set[str] = {
    "answer",
    "question",
    "session_id",
    "model",
    "elapsed_ms",
    "chunk_count",
    "retrieved_chunks",
    "sources",
    "prompt",
    "raw_response",
}

CONTRACT_DOCUMENT_FIELDS: set[str] = {
    "id",
    "filename",
    "stored_filename",
    "content_type",
    "size_bytes",
    "page_count",
    "chunk_count",
    "sha256",
    "uploaded_at",
    "pdf_metadata",
}

CONTRACT_UPLOAD_FIELDS: set[str] = {"document", "chunk_count", "duplicate_of"}

CONTRACT_ERROR_FIELDS: set[str] = {"code", "message", "hint", "request_id"}

#: Capabilities RAGStrike negotiates against before scheduling attacks. A capability that silently
#: disappeared would make packs *skip* rather than fail -- and a skipped pack looks like a clean
#: result unless coverage is read alongside the grade.
CONTRACT_CAPABILITIES: set[str] = {"CHAT", "INGEST_DOCUMENT", "LIST_SOURCES", "SESSION_MEMORY"}


# =================================================================================================
# Routes
# =================================================================================================


def routes_of(client: TestClient) -> set[tuple[str, str]]:
    """The published route set, read from ``/openapi.json``.

    Read from the OpenAPI document rather than by walking ``app.routes``: the schema is what a client
    generator and a scanner actually consume, so it is the surface that has to match. Walking the
    router would also assert against an internal attribute whose shape is Starlette's business.
    """
    schema = client.get("/openapi.json").json()
    return {
        (method.upper(), path)
        for path, operations in schema.get("paths", {}).items()
        for method in operations
        if method.upper() not in {"HEAD", "OPTIONS"}
    }


def test_every_contract_route_is_present(api_client: TestClient) -> None:
    """A client written against VulnerableRAG must reach the same endpoints here."""
    missing = CONTRACT_ROUTES - routes_of(api_client)

    assert not missing, f"SecureRAG is missing endpoints VulnerableRAG exposes: {sorted(missing)}"


def test_the_five_endpoints_the_brief_names_are_unchanged(api_client: TestClient) -> None:
    assert routes_of(api_client) >= REQUIRED_BY_BRIEF


def test_no_endpoint_was_added(api_client: TestClient) -> None:
    """ "Expose the EXACT same REST API" cuts both ways.

    An extra endpoint is a compatibility break in the other direction: a scanner enumerating the
    surface would find something on one application and not the other, and would report a difference
    that has nothing to do with security posture.
    """
    extra = routes_of(api_client) - CONTRACT_ROUTES

    assert not extra, f"SecureRAG exposes endpoints VulnerableRAG does not: {sorted(extra)}"


# =================================================================================================
# Response schemas
# =================================================================================================


def test_health_response_schema_is_identical(api_client: TestClient) -> None:
    body = api_client.get("/health").json()

    assert set(body) == CONTRACT_HEALTH_FIELDS


def test_the_system_prompt_field_survives_even_though_it_is_never_populated(
    api_client: TestClient,
) -> None:
    """The single API-behaviour difference between the pair, kept schema-compatible.

    Removing the field would break a client written against VulnerableRAG. Returning null tells that
    client the truth and keeps it working.
    """
    body = api_client.get("/health", params={"include_prompt": "true"}).json()

    assert "system_prompt" in body
    assert body["system_prompt"] is None


def test_chat_response_schema_is_identical(api_client: TestClient, sample_pdf: Path) -> None:
    api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    )

    body = api_client.post("/chat", json={"message": "What is the remote work policy?"}).json()

    assert set(body) == CONTRACT_CHAT_FIELDS


def test_upload_response_schema_is_identical(api_client: TestClient, sample_pdf: Path) -> None:
    body = api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    ).json()

    assert set(body) == CONTRACT_UPLOAD_FIELDS
    assert set(body["document"]) == CONTRACT_DOCUMENT_FIELDS


def test_document_list_schema_is_identical(api_client: TestClient, sample_pdf: Path) -> None:
    api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    )

    body = api_client.get("/documents").json()

    assert set(body) == {"documents", "count", "total_chunks"}
    assert set(body["documents"][0]) == CONTRACT_DOCUMENT_FIELDS


def test_the_error_envelope_is_identical(api_client: TestClient) -> None:
    """Every client that handles a VulnerableRAG error must handle a SecureRAG one.

    SecureRAG produces *more* errors -- that is what a validation layer does -- so the envelope
    matters more here, not less.
    """
    body = api_client.delete("/documents/does-not-exist").json()

    assert set(body) == {"error"}
    assert set(body["error"]) == CONTRACT_ERROR_FIELDS


def test_a_policy_refusal_uses_the_same_envelope(api_client: TestClient) -> None:
    """The refusal path is new behaviour, but not a new shape."""
    response = api_client.post("/chat", json={"message": "   "})

    assert response.status_code == 400
    assert set(response.json()["error"]) == CONTRACT_ERROR_FIELDS


def test_every_response_is_json_including_refusals(api_client: TestClient) -> None:
    for response in (
        api_client.get("/health"),
        api_client.get("/documents"),
        api_client.post("/chat", json={"message": ""}),
        api_client.post("/chat", json={}),
        api_client.post("/upload", files={"file": ("x.txt", b"not a pdf", "text/plain")}),
    ):
        assert response.headers["content-type"].startswith("application/json")


# =================================================================================================
# Capabilities and behaviour
# =================================================================================================


def test_declared_capabilities_are_not_reduced(api_client: TestClient) -> None:
    """Hardening must not be achieved by becoming less capable.

    A pack that skips because a capability vanished produces no findings, which reads as a clean
    result. SecureRAG scoring well by refusing to do things is not a security improvement -- it is
    the differential comparison being fooled.
    """
    capabilities = set(api_client.get("/health").json()["capabilities"])

    assert capabilities >= CONTRACT_CAPABILITIES


def test_retrieved_chunks_and_sources_stay_exposed(
    api_client: TestClient, sample_pdf: Path
) -> None:
    """They are how an operator verifies an answer is grounded, and RAGStrike's retrieval-integrity
    checks need them. Withholding them would make SecureRAG *look* better by being less
    inspectable."""
    api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    )

    body = api_client.post("/chat", json={"message": "What is the remote work policy?"}).json()

    assert body["retrieved_chunks"]
    assert body["sources"]
    assert set(body["retrieved_chunks"][0]) == {
        "chunk_id",
        "document_id",
        "source_name",
        "page",
        "index",
        "text",
        "score",
        "distance",
    }


def test_a_benign_question_is_answered_rather_than_refused(
    api_client: TestClient, sample_pdf: Path
) -> None:
    """Functional parity, which is the property that makes the pair comparable at all.

    If SecureRAG refused ordinary questions, every RAGStrike finding against it would be absent for
    the wrong reason.
    """
    api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    )

    response = api_client.post("/chat", json={"message": "What is the remote work policy?"})

    assert response.status_code == 200
    assert response.json()["answer"]


def test_an_ordinary_pdf_is_accepted(api_client: TestClient, sample_pdf: Path) -> None:
    """The upload path stays usable. A validation layer that rejected normal documents would make
    the corpus impossible to load, and the two applications would no longer share one."""
    response = api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    )

    assert response.status_code == 200
    assert response.json()["chunk_count"] > 0


def test_the_profile_name_is_the_only_identity_difference(api_client: TestClient) -> None:
    """RAGStrike keys its differential comparison on this field."""
    body = api_client.get("/health").json()

    assert body["profile"] == "secure"
    assert body["version"]
