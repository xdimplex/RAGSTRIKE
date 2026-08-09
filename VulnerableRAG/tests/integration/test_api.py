"""API tests: health, upload, chat, documents.

Everything runs against the real application with a scripted model client and a hash-based embedder,
so the whole suite works with Ollama stopped.

The acceptance criterion for Phase 2 is covered end to end here: upload a PDF, ask a question through
``POST /chat``, receive JSON containing an answer, the retrieved chunks, and the source documents.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

# ------------------------------------------------------------------------------------------------
# Health
# ------------------------------------------------------------------------------------------------


def test_health_returns_json_and_declares_capabilities(api_client: TestClient) -> None:
    response = api_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "vulnerable"
    assert "CHAT" in body["capabilities"]
    assert "INGEST_DOCUMENT" in body["capabilities"]
    assert "RETURN_CHUNKS" in body["capabilities"]


def test_health_reports_no_security_policies(api_client: TestClient) -> None:
    """The empty list is the honest, machine-readable signal that no defences are active."""
    body = api_client.get("/health").json()

    assert body["security_policies"] == []
    assert "INTENTIONALLY VULNERABLE" in body["warning"]


def test_health_discloses_the_system_prompt_on_request(api_client: TestClient) -> None:
    """Weakness V5: the application hands out its own instructions, unauthenticated."""
    body = api_client.get("/health", params={"include_prompt": "true"}).json()

    assert body["system_prompt"] is not None
    assert "VRAG-CANARY-SECRET" in body["system_prompt"]


def test_health_omits_the_prompt_by_default(api_client: TestClient) -> None:
    assert api_client.get("/health").json()["system_prompt"] is None


# ------------------------------------------------------------------------------------------------
# Upload
# ------------------------------------------------------------------------------------------------


def test_upload_ingests_a_pdf(api_client: TestClient, sample_pdf: Path) -> None:
    response = api_client.post(
        "/upload",
        files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document"]["filename"] == "handbook.pdf"
    assert body["document"]["page_count"] == 1
    assert body["chunk_count"] > 0


def test_upload_exposes_pdf_metadata(api_client: TestClient, sample_pdf: Path) -> None:
    body = api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    ).json()

    assert body["document"]["pdf_metadata"]["Title"] == "AcmeCorp Employee Handbook"


def test_upload_rejects_an_unsupported_type(api_client: TestClient) -> None:
    """`.txt` is now INGESTED, so the refusal case needs a genuinely unsupported format.

    The allowlist grew to pdf/txt/md/csv because an operator should be able to upload the documents
    they actually have. It is still an allowlist: an executable is refused on its extension before a
    byte reaches a parser.
    """
    response = api_client.post(
        "/upload", files={"file": ("payload.exe", b"MZ\x90\x00", "application/octet-stream")}
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_upload_accepts_a_text_document(api_client: TestClient) -> None:
    response = api_client.post(
        "/upload", files={"file": ("notes.txt", b"Refunds take 14 days.", "text/plain")}
    )

    assert response.status_code == 200, response.text
    assert response.json()["chunk_count"] >= 1


def test_upload_rejects_an_empty_file(api_client: TestClient) -> None:
    response = api_client.post("/upload", files={"file": ("empty.pdf", b"", "application/pdf")})

    assert response.status_code == 400
    assert response.json()["error"]["hint"]


def test_upload_rejects_a_corrupt_pdf(api_client: TestClient) -> None:
    response = api_client.post(
        "/upload", files={"file": ("broken.pdf", b"not a pdf at all", "application/pdf")}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_document"


def test_duplicate_upload_is_reported_but_allowed(api_client: TestClient, sample_pdf: Path) -> None:
    """Refusing a duplicate would be a control -- and would break the corpus-flooding exercise."""
    payload = {"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}

    first = api_client.post("/upload", files=payload).json()
    second = api_client.post("/upload", files=payload).json()

    assert second["duplicate_of"] == first["document"]["id"]
    assert second["document"]["id"] != first["document"]["id"]


def test_traversal_filename_cannot_escape_the_upload_directory(
    api_client: TestClient, sample_pdf: Path, settings
) -> None:
    """Path traversal is a real bug, not one of this lab's nine documented lessons."""
    api_client.post(
        "/upload",
        files={"file": ("../../escaped.pdf", sample_pdf.read_bytes(), "application/pdf")},
    )

    assert not (settings.storage.upload_dir.parent.parent / "escaped.pdf").exists()
    assert list(settings.storage.upload_dir.glob("*.pdf"))


# ------------------------------------------------------------------------------------------------
# Documents
# ------------------------------------------------------------------------------------------------


def test_documents_starts_empty(api_client: TestClient) -> None:
    body = api_client.get("/documents").json()

    assert body["count"] == 0
    assert body["documents"] == []


def test_documents_lists_after_upload(api_client: TestClient, sample_pdf: Path) -> None:
    api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    )

    body = api_client.get("/documents").json()

    assert body["count"] == 1
    assert body["total_chunks"] > 0


def test_document_chunks_are_inspectable(api_client: TestClient, sample_pdf: Path) -> None:
    uploaded = api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    ).json()

    body = api_client.get(f"/documents/{uploaded['document']['id']}/chunks").json()

    assert body["count"] > 0
    assert any("remotely" in chunk["text"] for chunk in body["chunks"])


def test_delete_removes_document_and_vectors(api_client: TestClient, sample_pdf: Path) -> None:
    uploaded = api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    ).json()
    document_id = uploaded["document"]["id"]

    deleted = api_client.delete(f"/documents/{document_id}").json()

    assert deleted["deleted"] is True
    assert deleted["chunks_removed"] > 0
    assert api_client.get("/documents").json()["count"] == 0


def test_delete_unknown_document_returns_404(api_client: TestClient) -> None:
    response = api_client.delete("/documents/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


# ------------------------------------------------------------------------------------------------
# Chat
# ------------------------------------------------------------------------------------------------


def test_chat_before_any_upload_explains_itself(api_client: TestClient) -> None:
    response = api_client.post("/chat", json={"message": "What is the policy?"})

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "no_documents"
    assert "seed_corpus" in body["error"]["hint"]


def test_chat_returns_answer_chunks_and_sources(api_client: TestClient, sample_pdf: Path) -> None:
    """The Phase 2 acceptance path, end to end."""
    api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    )

    response = api_client.post("/chat", json={"message": "What is the remote work policy?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["chunk_count"] > 0
    assert body["retrieved_chunks"]
    assert "handbook.pdf" in body["sources"]
    assert body["elapsed_ms"] >= 0
    assert body["session_id"]


def test_chat_rejects_an_empty_message(api_client: TestClient) -> None:
    response = api_client.post("/chat", json={"message": "   "})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_chat_rejects_a_malformed_body(api_client: TestClient) -> None:
    response = api_client.post("/chat", json={"question": "wrong field name"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_chat_continues_a_session(api_client: TestClient, sample_pdf: Path) -> None:
    api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    )

    first = api_client.post("/chat", json={"message": "Remote work?"}).json()
    second = api_client.post(
        "/chat", json={"message": "And expenses?", "session_id": first["session_id"]}
    ).json()

    assert second["session_id"] == first["session_id"]


def test_chat_can_return_the_assembled_prompt(api_client: TestClient, sample_pdf: Path) -> None:
    """Being able to read the exact prompt is what turns a suspicion into a confirmation."""
    api_client.post(
        "/upload", files={"file": ("handbook.pdf", sample_pdf.read_bytes(), "application/pdf")}
    )

    body = api_client.post("/chat", json={"message": "Remote work?", "include_prompt": True}).json()

    assert body["prompt"]
    assert "VRAG-CANARY-SECRET" in body["prompt"]  # weakness V4: the secret is in every prompt


def test_every_response_is_json_including_errors(api_client: TestClient) -> None:
    for response in (
        api_client.get("/health"),
        api_client.get("/documents"),
        api_client.delete("/documents/nope"),
        api_client.post("/chat", json={}),
    ):
        assert response.headers["content-type"].startswith("application/json")


def test_responses_carry_request_id_and_timing(api_client: TestClient) -> None:
    response = api_client.get("/health")

    assert response.headers["X-Request-ID"]
    assert int(response.headers["X-Response-Time-ms"]) >= 0
