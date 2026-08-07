"""Error taxonomy.

Every failure the API can surface has a type here, and every type carries a message meant to be read
by a human operator rather than grepped out of a traceback. ``backend/app_factory.py`` maps each one
onto an HTTP status in a single table, so the mapping lives in exactly one place.

The list mirrors the failures Phase 2 must handle gracefully: invalid PDF, empty PDF, missing Ollama,
missing model, vector store unavailable, no documents ingested, invalid request.
"""

from __future__ import annotations


class VulnerableRagError(Exception):
    """Base for everything this application raises deliberately."""

    #: Short machine-readable code, returned in the JSON error envelope.
    code = "internal_error"

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        #: What the operator should do about it. Surfaced in the API response.
        self.hint = hint


# -- ingestion ---------------------------------------------------------------------------------


class InvalidDocumentError(VulnerableRagError):
    """The upload is not a readable PDF."""

    code = "invalid_document"


class EmptyDocumentError(VulnerableRagError):
    """The PDF parsed, but no extractable text was found.

    Usually a scanned image with no text layer. Worth its own type because the fix is different from
    a corrupt file: the operator needs OCR, not a different upload.
    """

    code = "empty_document"


class DocumentTooLargeError(VulnerableRagError):
    """The upload exceeds ``ingestion.max_upload_mb``."""

    code = "document_too_large"


class UnsupportedFileTypeError(VulnerableRagError):
    """Not in ``ingestion.supported_types``."""

    code = "unsupported_file_type"


class DocumentNotFoundError(VulnerableRagError):
    """No document with that id."""

    code = "document_not_found"


# -- model -------------------------------------------------------------------------------------


class ModelUnavailableError(VulnerableRagError):
    """Ollama is not reachable."""

    code = "model_unavailable"


class ModelNotFoundError(VulnerableRagError):
    """Ollama is reachable but does not have the configured model pulled."""

    code = "model_not_found"


class ModelTimeoutError(VulnerableRagError):
    """The model did not respond within ``model.timeout_s``."""

    code = "model_timeout"


class EmptyModelResponseError(VulnerableRagError):
    """The model returned no answer text.

    The usual cause is a thinking model such as Qwen3 spending its entire ``num_predict`` budget on
    internal reasoning, so Ollama returns a populated ``thinking`` field and an empty ``response``.
    Worth its own type because "the model answered nothing" and "the model is missing" need
    completely different fixes, and silently returning an empty string would hide both.
    """

    code = "empty_model_response"


# -- storage -----------------------------------------------------------------------------------


class VectorStoreUnavailableError(VulnerableRagError):
    """ChromaDB could not be opened or queried."""

    code = "vector_store_unavailable"


class NoDocumentsError(VulnerableRagError):
    """A question was asked before anything was ingested.

    Not an error in the retrieval layer -- the corpus is genuinely empty -- but answering from a
    corpus of zero chunks would produce a pure hallucination, so the caller is told plainly instead.
    """

    code = "no_documents"


class InvalidRequestError(VulnerableRagError):
    """Malformed input that Pydantic did not already reject."""

    code = "invalid_request"
