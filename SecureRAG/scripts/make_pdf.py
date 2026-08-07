"""Minimal PDF writer.

Used by ``seed_corpus.py`` and by the test fixtures. Writing the PDF bytes directly avoids adding a
document-generation dependency for what amounts to a few pages of plain text.

It supports one thing beyond plain text, and it is the interesting one: ``hidden_text`` renders in
white, which is invisible in a viewer and fully extractable by ``pypdf``. That gap between what a
human sees and what the ingestion pipeline reads is exactly the surface a hidden-instruction exercise
targets.
"""

from __future__ import annotations

from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _content_stream(lines: list[str], hidden: list[str]) -> str:
    parts = ["BT", "/F1 11 Tf", "1 0 0 1 56 760 Tm", "14 TL"]
    for line in lines:
        parts.append(f"({_escape(line)}) Tj")
        parts.append("T*")
    if hidden:
        # White on white: invisible on screen, plain text to any extractor.
        parts.append("1 1 1 rg")
        for line in hidden:
            parts.append(f"({_escape(line)}) Tj")
            parts.append("T*")
        parts.append("0 0 0 rg")
    parts.append("ET")
    return "\n".join(parts)


def write_pdf(
    path: Path,
    *,
    lines: list[str],
    hidden_lines: list[str] | None = None,
    metadata: dict[str, str] | None = None,
) -> Path:
    """Write a single-page PDF.

    Args:
        path: Destination.
        lines: Visible text, one entry per line.
        hidden_lines: Text rendered in white. Invisible to a reader, extracted by pypdf.
        metadata: PDF metadata (``Title``, ``Subject``, ...). Also invisible in a viewer, also
            ingested.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = _content_stream(lines, hidden_lines or [])
    stream_bytes = stream.encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
    )
    objects.append(
        b"<< /Length "
        + str(len(stream_bytes)).encode()
        + b" >>\nstream\n"
        + stream_bytes
        + b"\nendstream"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    info_ref = b""
    if metadata:
        fields = b" ".join(
            b"/"
            + key.encode("latin-1", "replace")
            + b" ("
            + _escape(value).encode("latin-1", "replace")
            + b")"
            for key, value in metadata.items()
        )
        objects.append(b"<< " + fields + b" >>")
        info_ref = b" /Info " + str(len(objects)).encode() + b" 0 R"

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(number).encode() + b" 0 obj\n" + body + b"\nendobj\n"

    xref_at = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()

    out += (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode()
        + b" /Root 1 0 R"
        + info_ref
        + b" >>\n"
        b"startxref\n" + str(xref_at).encode() + b"\n%%EOF\n"
    )

    path.write_bytes(bytes(out))
    return path
