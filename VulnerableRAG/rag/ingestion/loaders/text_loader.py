"""Loaders for plain-text document formats: ``.txt``, ``.md`` and ``.csv``.

WHY THESE SHARE THE PDF'S SHAPE
    They return the same :class:`LoadedDocument` the PDF loader returns, so everything downstream --
    chunking, the ``on_ingest`` policy hook, embedding, retrieval, citation -- is identical. A text
    file and a PDF differ in how bytes become characters and in nothing else, and the moment they
    take separate paths the security controls have to be written twice.

WHY CSV IS TREATED AS TEXT
    A CSV is chunked as its rows, not parsed into columns. Interpreting it would mean deciding what
    a "record" is, which is a data-modelling question this lab has no answer to -- and a per-format
    representation would give the retrieval controls a second shape to reason about.

    Rows are joined with their header so a retrieved chunk carries the column names it belongs to;
    a bare row of values is unreadable out of context and would cite as nonsense.

WHY ENCODING IS FORGIVING
    ``errors="replace"`` rather than a hard failure. These files are uploaded by an operator, often
    from another machine, and a single bad byte should not reject the document -- a replacement
    character in one word is a far better outcome than an upload that fails with a UnicodeDecodeError
    the operator cannot act on.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

from rag.ingestion.loaders.pdf_loader import LoadedDocument, LoadedPage

log = logging.getLogger(__name__)

#: Suffixes this module handles, without the dot.
TEXT_SUFFIXES: frozenset[str] = frozenset({"txt", "md", "csv"})

#: Characters per synthetic "page".
#:
#: A text file has no pages, but the rest of the pipeline reports page numbers in citations, so one
#: has to be invented. 3000 characters is roughly a printed page and keeps a citation meaningful:
#: "page 4" should narrow the search for a human checking the claim, which is the only thing a page
#: number is for here.
PAGE_CHARS = 3000


def _paginate(text: str) -> list[LoadedPage]:
    """Split *text* into page-sized pieces, breaking on a line boundary where possible.

    Breaking mid-line would split a CSV row or a sentence across two citations, so the split point
    moves back to the last newline in the window unless that would produce a near-empty page.
    """
    if not text:
        return [LoadedPage(page=0, text="")]

    pages: list[LoadedPage] = []
    start = 0
    while start < len(text):
        end = min(start + PAGE_CHARS, len(text))
        if end < len(text):
            newline = text.rfind("\n", start, end)
            if newline > start + PAGE_CHARS // 2:
                end = newline + 1
        pages.append(LoadedPage(page=len(pages), text=text[start:end].strip()))
        start = end
    return pages


def _csv_to_text(raw: str) -> str:
    """Flatten a CSV into one labelled line per row.

    ``name: Ada | role: engineer`` rather than ``Ada,engineer``. The header travels with every row,
    because a chunk containing only values cannot be read -- or cited -- without it.

    Falls back to the raw text if the file will not parse: a malformed CSV is still a text document,
    and refusing it would be worse than indexing it as-is.
    """
    try:
        rows = list(csv.reader(io.StringIO(raw)))
    except csv.Error:
        log.warning("csv would not parse; indexing it as plain text")
        return raw
    if not rows:
        return ""

    header = [cell.strip() for cell in rows[0]]
    lines = [", ".join(header)]
    for row in rows[1:]:
        pairs = [
            f"{header[i] if i < len(header) else f'column {i + 1}'}: {cell.strip()}"
            for i, cell in enumerate(row)
            if cell.strip()
        ]
        if pairs:
            lines.append(" | ".join(pairs))
    return "\n".join(lines)


def load_text(path: Path) -> LoadedDocument:
    """Read a ``.txt``, ``.md`` or ``.csv`` file into the same shape a PDF produces."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower().lstrip(".")
    body = _csv_to_text(raw) if suffix == "csv" else raw

    pages = _paginate(body)
    log.info(
        "text document loaded",
        extra={"source": path.name, "format": suffix, "pages": len(pages)},
    )
    return LoadedDocument(
        pages=pages,
        # A text file carries no embedded metadata. An empty mapping keeps the field's meaning --
        # "what the file declared about itself" -- rather than inventing values for it.
        metadata={},
        page_count=len(pages),
    )
