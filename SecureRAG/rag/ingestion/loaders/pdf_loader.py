"""PDF text extraction.

Deliberately faithful: whatever is in the file comes out of it, character for character.

Two properties here are attack surface, and both are intentional:

**Metadata is extracted and carried forward.** ``/Title``, ``/Subject``, ``/Keywords``, and friends
are read and prepended to the document text. A PDF's metadata is not visible when a human opens the
file, which makes it an excellent place to hide an instruction -- and this loader ingests it.

**Nothing is normalized.** Zero-width characters, bidirectional control marks, and text rendered in
white-on-white survive extraction unchanged, because ``pypdf`` reports the text layer regardless of
its rendered colour. Stripping any of it is a security control and belongs in
``rag/policy/controls/``, not here (weakness V2).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from rag.errors import EmptyDocumentError, InvalidDocumentError

log = logging.getLogger(__name__)

#: Metadata keys worth carrying into the text. Anything a PDF author controls is fair game.
_METADATA_KEYS = ("/Title", "/Subject", "/Keywords", "/Author", "/Creator", "/Producer")


@dataclass(frozen=True, slots=True)
class LoadedPage:
    page: int
    text: str


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    pages: list[LoadedPage]
    metadata: dict[str, str]
    page_count: int

    @property
    def text(self) -> str:
        """All pages joined, metadata first.

        Metadata leads because it is the least visible part of the file and therefore the most
        interesting one to test with.
        """
        parts: list[str] = []
        if self.metadata:
            rendered = "\n".join(f"{key}: {value}" for key, value in self.metadata.items())
            parts.append(f"[Document metadata]\n{rendered}")
        parts.extend(page.text for page in self.pages if page.text.strip())
        return "\n\n".join(parts)


def load_pdf(path: Path) -> LoadedDocument:
    """Extract text and metadata from a PDF.

    Args:
        path: Path to the file on disk.

    Returns:
        The extracted pages and metadata.

    Raises:
        InvalidDocumentError: The file is missing, unreadable, or not a PDF.
        EmptyDocumentError: The file parsed but yielded no extractable text.
    """
    if not path.exists():
        raise InvalidDocumentError(
            f"File not found: {path.name}",
            hint="The upload may have been removed from disk. Re-upload the document.",
        )

    try:
        reader = PdfReader(str(path))
    except (PdfReadError, OSError, ValueError) as exc:
        raise InvalidDocumentError(
            f"Could not read {path.name} as a PDF: {exc}",
            hint="Confirm the file is a valid, non-encrypted PDF.",
        ) from exc

    if reader.is_encrypted:
        # An empty-password decrypt covers the common "protected but not really" case.
        try:
            reader.decrypt("")
        except Exception as exc:  # noqa: BLE001 - pypdf raises several unrelated types here
            raise InvalidDocumentError(
                f"{path.name} is password protected.",
                hint="Remove the password before uploading. This lab does not accept credentials.",
            ) from exc

    pages: list[LoadedPage] = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - a single bad page must not lose the document
            log.warning(
                "page extraction failed",
                extra={"file": path.name, "page": number, "error": str(exc)},
            )
            text = ""
        pages.append(LoadedPage(page=number, text=text))

    metadata = _extract_metadata(reader)

    if not any(page.text.strip() for page in pages) and not metadata:
        raise EmptyDocumentError(
            f"No extractable text in {path.name}.",
            hint="The PDF is probably a scanned image with no text layer. OCR it first.",
        )

    log.info(
        "pdf loaded",
        extra={"file": path.name, "pages": len(pages), "metadata_keys": list(metadata)},
    )
    return LoadedDocument(pages=pages, metadata=metadata, page_count=len(pages))


def _extract_metadata(reader: PdfReader) -> dict[str, str]:
    """Pull the interesting metadata fields, verbatim."""
    raw = reader.metadata
    if not raw:
        return {}

    extracted: dict[str, str] = {}
    for key in _METADATA_KEYS:
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            # Stored exactly as written. No length cap, no character filtering -- both would be
            # controls, and this profile has none.
            extracted[key.lstrip("/")] = text
    return extracted
