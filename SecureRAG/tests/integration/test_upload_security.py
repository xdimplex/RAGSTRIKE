"""Upload tests -- the ingestion path, end to end through the API.

The unit suite proves :class:`~backend.validation.UploadValidator` refuses the right things. This
one proves the API actually calls it, returns the documented status, and that a document which does
get in has been sanitized on the way through.

The distinction matters: a validator nobody invokes passes every unit test it has.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from scripts.make_pdf import write_pdf


def upload(client: TestClient, name: str, content: bytes, content_type: str = "application/pdf"):
    return client.post("/upload", files={"file": (name, content, content_type)})


def test_an_ordinary_pdf_is_ingested(api_client: TestClient, sample_pdf: Path) -> None:
    response = upload(api_client, "handbook.pdf", sample_pdf.read_bytes())

    assert response.status_code == 200
    body = response.json()
    assert body["chunk_count"] > 0
    assert body["document"]["filename"] == "handbook.pdf"


def test_a_renamed_executable_is_refused_before_the_parser(api_client: TestClient) -> None:
    """The check that justifies validating at the boundary rather than in the policy chain."""
    response = upload(api_client, "invoice.pdf", b"MZ\x90\x00" + b"\x00" * 200)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_document"


def test_a_text_file_is_refused_on_its_extension(api_client: TestClient) -> None:
    response = upload(api_client, "notes.txt", b"hello", "text/plain")

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_an_empty_upload_is_refused(api_client: TestClient) -> None:
    response = upload(api_client, "empty.pdf", b"")

    assert response.status_code == 400


def test_an_oversized_upload_is_refused(api_client: TestClient, settings, monkeypatch) -> None:
    """413, so a client can distinguish "too big" from "wrong type" without parsing prose."""
    monkeypatch.setattr(settings.security.uploads, "max_upload_mb", 1)

    response = upload(api_client, "huge.pdf", b"%PDF-1.7\n" + b"x" * (2 * 1024 * 1024))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "document_too_large"


def test_a_traversal_filename_cannot_escape_the_upload_directory(
    api_client: TestClient, sample_pdf: Path, settings
) -> None:
    """Path traversal is a real bug, not one of the lab's documented lessons -- it is closed in both
    applications, and this test is inherited unchanged."""
    upload(api_client, "../../escaped.pdf", sample_pdf.read_bytes())

    assert not (settings.storage.upload_dir.parent.parent / "escaped.pdf").exists()


def test_a_traversal_filename_is_recorded_under_its_base_name(
    api_client: TestClient, sample_pdf: Path
) -> None:
    """The stored name is what the model later sees as a citation source, so it has to be clean."""
    body = upload(api_client, "../../etc/passwd.pdf", sample_pdf.read_bytes()).json()

    assert body["document"]["filename"] == "passwd.pdf"


def test_a_poisoned_document_is_sanitized_on_the_way_in(
    api_client: TestClient, poisoned_pdf: Path
) -> None:
    """The document is accepted -- refusing it would break any corpus that discusses security -- and
    its instruction framing is neutralized before it is chunked and embedded."""
    body = upload(api_client, "quarterly_update.pdf", poisoned_pdf.read_bytes()).json()
    document_id = body["document"]["id"]

    chunks = api_client.get(f"/documents/{document_id}/chunks").json()
    stored = " ".join(chunk["text"] for chunk in chunks["chunks"])

    assert "[neutralized:" in stored


def test_hidden_unicode_does_not_survive_ingestion(api_client: TestClient, tmp_path: Path) -> None:
    """Zero-width characters are how an instruction hides from a human reviewer while staying
    perfectly legible to the model."""
    pdf = write_pdf(
        tmp_path / "sneaky.pdf",
        lines=["Revenue grew​​​ steadily across all regions."],
        metadata={"Title": "Update"},
    )

    body = upload(api_client, "sneaky.pdf", pdf.read_bytes()).json()
    chunks = api_client.get(f"/documents/{body['document']['id']}/chunks").json()
    stored = " ".join(chunk["text"] for chunk in chunks["chunks"])

    assert "​" not in stored


def test_uploading_the_same_document_twice_is_idempotent(
    api_client: TestClient, sample_pdf: Path
) -> None:
    content = sample_pdf.read_bytes()

    first = upload(api_client, "handbook.pdf", content).json()
    second = upload(api_client, "handbook.pdf", content).json()

    assert second["document"]["id"] == first["document"]["id"]
    assert api_client.get("/documents").json()["count"] == 1


def test_a_duplicate_does_not_double_its_weight_in_retrieval(
    api_client: TestClient, sample_pdf: Path
) -> None:
    """The reason idempotence is a security property and not only a tidiness one: ingesting a
    document twice doubles its weight in every subsequent retrieval, which quietly biases every
    future answer."""
    content = sample_pdf.read_bytes()
    upload(api_client, "handbook.pdf", content)
    first_total = api_client.get("/documents").json()["total_chunks"]

    upload(api_client, "handbook.pdf", content)

    assert api_client.get("/documents").json()["total_chunks"] == first_total


def test_a_different_document_with_the_same_name_is_still_ingested(
    api_client: TestClient, sample_pdf: Path, poisoned_pdf: Path
) -> None:
    """Deduplication is by content hash, not by filename. Keying on the name would let a client
    suppress an upload by choosing a name that already existed."""
    upload(api_client, "report.pdf", sample_pdf.read_bytes())
    upload(api_client, "report.pdf", poisoned_pdf.read_bytes())

    assert api_client.get("/documents").json()["count"] == 2


def test_a_refused_upload_leaves_no_trace(api_client: TestClient, settings) -> None:
    """A rejected file must not be written to disk or recorded. Otherwise "refused" means "stored
    but not indexed", which is a worse outcome than either."""
    upload(api_client, "evil.pdf", b"MZ\x90\x00not a pdf")

    assert api_client.get("/documents").json()["count"] == 0
    assert not list(settings.storage.upload_dir.glob("*"))


def test_every_upload_refusal_uses_the_shared_error_envelope(api_client: TestClient) -> None:
    for name, content, content_type in (
        ("notes.txt", b"x", "text/plain"),
        ("empty.pdf", b"", "application/pdf"),
        ("fake.pdf", b"MZ\x90\x00", "application/pdf"),
    ):
        body = upload(api_client, name, content, content_type).json()
        assert set(body["error"]) == {"code", "message", "hint", "request_id"}
        assert body["error"]["hint"], "a refusal with no next step is a dead end"
