"""Validation tests -- the upload boundary.

WHY THESE ARE SEPARATE FROM THE CONTROL TESTS
    The controls run *inside* the pipeline. :class:`~backend.validation.UploadValidator` runs in
    front of it, before a single byte reaches the PDF parser. That ordering is the point of the
    class, and it deserves its own suite.

THE PROPERTY THAT MATTERS MOST
    A file's extension and its declared ``Content-Type`` are both supplied by the client, and both
    are trivially forged. Only the magic-byte check tests something the client cannot lie about
    without also making the file useless for its claimed purpose.
"""

from __future__ import annotations

import pytest

from backend.validation import MAGIC_WINDOW, UploadValidator
from rag.errors import (
    DocumentTooLargeError,
    InvalidDocumentError,
    InvalidRequestError,
    UnsupportedFileTypeError,
)
from rag.security_config import UploadSecuritySettings

PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


def validator(**overrides: object) -> UploadValidator:
    return UploadValidator(UploadSecuritySettings(**overrides))  # type: ignore[arg-type]  # pydantic validates


# -- filenames -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("../../../report.pdf", "report.pdf"),
        (r"C:\Windows\system32\evil.pdf", "evil.pdf"),
        ("subdir/report.pdf", "report.pdf"),
        ("  spaced.pdf  ", "spaced.pdf"),
        (".hidden.pdf", "hidden.pdf"),
    ],
)
def test_a_filename_is_reduced_to_a_base_name(supplied: str, expected: str) -> None:
    """A filename is attacker-controlled and reaches the filesystem, the database, and the prompt."""
    assert UploadValidator.safe_filename(supplied) == expected


def test_windows_paths_are_stripped_on_any_host() -> None:
    """An upload arrives over HTTP from any client, so a Windows path can reach a POSIX server.

    ``os.path.basename`` alone would leave the backslashes untouched on Linux.
    """
    assert "\\" not in UploadValidator.safe_filename(r"..\..\evil.pdf")


def test_a_null_byte_is_removed() -> None:
    """A classic truncation trick against anything downstream that speaks C."""
    assert "\x00" not in UploadValidator.safe_filename("report\x00.exe.pdf")


def test_an_unusable_filename_is_refused() -> None:
    with pytest.raises(InvalidRequestError):
        UploadValidator.safe_filename("   ")


def test_a_very_long_filename_is_bounded() -> None:
    assert len(UploadValidator.safe_filename("a" * 500 + ".pdf")) <= 255


# -- size ------------------------------------------------------------------------------------------


def test_an_empty_upload_is_refused() -> None:
    with pytest.raises(InvalidRequestError, match="empty"):
        validator().validate(filename="report.pdf", content=b"")


def test_an_oversized_upload_is_refused() -> None:
    oversized = b"%PDF-1.7\n" + b"x" * (2 * 1024 * 1024)

    with pytest.raises(DocumentTooLargeError, match="limit"):
        validator(max_upload_mb=1).validate(filename="report.pdf", content=oversized)


def test_the_size_check_reports_the_actual_size() -> None:
    """An error that says "too large" without saying how large leaves the operator guessing."""
    with pytest.raises(DocumentTooLargeError) as excinfo:
        validator(max_upload_mb=1).validate(
            filename="r.pdf", content=b"%PDF-1.7\n" + b"x" * (2 * 1024 * 1024)
        )

    assert "2.0 MB" in str(excinfo.value)


# -- type ------------------------------------------------------------------------------------------


def test_a_disallowed_extension_is_refused() -> None:
    """`.txt` joined the allowlist; `.exe` did not, and never should."""
    with pytest.raises(UnsupportedFileTypeError):
        validator().validate(filename="payload.exe", content=PDF)


def test_a_text_file_is_accepted() -> None:
    assert validator().validate(filename="notes.txt", content=b"Refunds take 14 days.")


def test_a_binary_file_renamed_to_text_is_refused() -> None:
    """A NUL byte does not occur in a UTF-8 document and does occur in every binary format."""
    from rag.errors import InvalidDocumentError

    with pytest.raises(InvalidDocumentError):
        validator().validate(filename="payload.txt", content=b"MZ\x90\x00\x00binary")


def test_a_file_with_no_extension_is_refused() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        validator().validate(filename="report", content=PDF)


def test_a_disallowed_mime_type_is_refused() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        validator().validate(filename="r.pdf", content=PDF, content_type="text/html")


def test_octet_stream_is_accepted_because_the_magic_check_makes_it_safe() -> None:
    """Several HTTP clients send it for every upload. Rejecting it would break legitimate callers,
    and the signature check is what makes accepting it safe."""
    assert validator().validate(
        filename="r.pdf", content=PDF, content_type="application/octet-stream"
    )


def test_a_mime_type_with_parameters_is_accepted() -> None:
    """``application/pdf; charset=binary`` is a real thing browsers send."""
    assert validator().validate(
        filename="r.pdf", content=PDF, content_type="application/pdf; charset=binary"
    )


def test_extensions_are_normalized_regardless_of_how_they_are_configured() -> None:
    """Three spellings of the same extension in a config file is a bug waiting to happen: the
    allowlist would pass for one and fail for the others."""
    settings = UploadSecuritySettings(allowed_extensions=[".PDF", "pdf", "Pdf"])

    assert settings.allowed_extensions == ["pdf"]


def test_an_empty_extension_allowlist_is_refused_at_load_time() -> None:
    """It would accept nothing at all, which is a configuration mistake rather than a policy."""
    with pytest.raises(ValueError, match="empty"):
        UploadSecuritySettings(allowed_extensions=[])


# -- content ---------------------------------------------------------------------------------------


def test_a_renamed_file_is_caught_by_its_content() -> None:
    """The check that matters. Extension and Content-Type are both client-supplied and forged in one
    line; the first bytes are not."""
    with pytest.raises(InvalidDocumentError, match="signature"):
        validator().validate(
            filename="totally_a.pdf",
            content=b"MZ\x90\x00this is a windows executable",
            content_type="application/pdf",
        )


def test_a_pdf_with_leading_junk_is_still_accepted() -> None:
    """The PDF specification tolerates leading bytes before ``%PDF-``, and real readers do too."""
    assert validator().validate(filename="r.pdf", content=b"\n\n   " + PDF)


def test_a_signature_beyond_the_window_is_refused() -> None:
    """Scanning the whole file would accept anything that merely mentions ``%PDF-`` in its body."""
    with pytest.raises(InvalidDocumentError):
        validator().validate(filename="r.pdf", content=b"x" * (MAGIC_WINDOW + 10) + PDF)


def test_magic_verification_can_be_turned_off() -> None:
    """Configurable, and the config file says plainly what turning it off costs."""
    assert validator(verify_magic_bytes=False).validate(filename="r.pdf", content=b"not a pdf")


def test_an_allowed_extension_with_no_known_signature_is_refused() -> None:
    """Adding a format to the allowlist without adding its signature would silently disable the
    content check for that format -- the exact failure the check exists to prevent."""
    with pytest.raises(InvalidDocumentError, match="No content signature"):
        validator(allowed_extensions=["docx"]).validate(filename="r.docx", content=b"PK\x03\x04")


# -- the happy path --------------------------------------------------------------------------------


def test_an_ordinary_pdf_passes_every_check() -> None:
    """The test that keeps the validator usable. Everything above is worthless if this fails."""
    assert (
        validator().validate(filename="handbook.pdf", content=PDF, content_type="application/pdf")
        == "handbook.pdf"
    )


def test_checks_run_cheapest_first() -> None:
    """Size bounds the cost of every check after it, so an enormous file is refused on its length
    rather than after a signature scan."""
    enormous = b"not a pdf at all" * 1_000_000

    with pytest.raises(DocumentTooLargeError):
        validator(max_upload_mb=1).validate(filename="r.pdf", content=enormous)
