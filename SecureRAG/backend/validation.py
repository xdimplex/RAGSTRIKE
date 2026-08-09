"""Upload validation, enforced at the API boundary.

WHY VALIDATION HAPPENS HERE AND NOT IN THE POLICY CHAIN
    The policy chain's earliest hook, ``on_ingest``, receives text that has *already been extracted*
    from the file. By then the application has spent the cost of parsing an untrusted document, and
    a malformed PDF has already been through the parser -- which is the component most likely to have
    a memory-safety bug in it.

    Size, type, and magic-byte checks belong in front of the parser. That ordering is the whole point
    of validating at the boundary.

WHY MAGIC BYTES AND NOT THE FILENAME OR THE CONTENT-TYPE
    Both are supplied by the client and both are trivially forged. ``report.pdf`` with a
    ``Content-Type: application/pdf`` header can be anything at all. The first bytes of the file are
    the only part of an upload the client cannot lie about without also making the file useless for
    its claimed purpose.

    This is also why ``application/octet-stream`` is in the allowed MIME list: several HTTP clients
    send it for every upload, so rejecting it would break legitimate callers, and the magic-byte
    check is what makes accepting it safe.

WHAT VALIDATION HERE DOES NOT CLAIM
    A file that passes these checks is a *plausible* PDF, not a safe one. PDF is a large format with
    an executable heritage, and a determined malformed-input attack against the parser is not
    something a header check prevents. Sandboxing the parser is the real answer and is out of scope
    for this lab -- stated here rather than implied away.
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath, PureWindowsPath

from rag.errors import (
    DocumentTooLargeError,
    InvalidDocumentError,
    InvalidRequestError,
    UnsupportedFileTypeError,
)
from rag.security_config import UploadSecuritySettings

log = logging.getLogger(__name__)

#: Magic bytes by extension. A PDF starts with ``%PDF-``; the specification allows leading junk, but
#: nothing this application should accept does.
MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    "pdf": (b"%PDF-",),
}

#: Formats with no signature to check, because plain text has none.
#:
#: They are NOT waved through. A file claiming to be text is verified to actually BE text: decodable
#: as UTF-8 and free of NUL bytes. That is the strongest statement available for these formats, and
#: it still refuses the case this check exists for -- an executable or an archive renamed to ``.txt``
#: to slip past the extension allowlist.
TEXTUAL_TYPES: frozenset[str] = frozenset({"txt", "md", "csv"})

#: How far into the file to look for the signature. The PDF specification tolerates up to 1024 bytes
#: of leading garbage before ``%PDF-``; readers vary. Scanning a small window accepts real-world
#: files without accepting a file that merely mentions ``%PDF-`` somewhere in its body.
MAGIC_WINDOW = 1024


class UploadValidator:
    """Validates an upload before a single byte reaches the parser."""

    def __init__(self, settings: UploadSecuritySettings) -> None:
        self.settings = settings

    def validate(self, *, filename: str, content: bytes, content_type: str = "") -> str:
        """Check one upload and return the safe filename to record.

        Args:
            filename: As supplied by the client. Treated as hostile.
            content: The uploaded bytes.
            content_type: The declared MIME type, if any.

        Returns:
            The sanitized base filename.

        Raises:
            InvalidRequestError: Empty upload or unusable filename.
            DocumentTooLargeError: Over ``max_upload_mb``.
            UnsupportedFileTypeError: Extension or MIME type not allowed.
            InvalidDocumentError: Content does not match its claimed type.
        """
        safe_name = self.safe_filename(filename)

        if not content:
            raise InvalidRequestError(
                f"{safe_name!r} is empty.",
                hint="Choose a file with content and try again.",
            )

        # Size first: cheapest check, and the one that bounds the cost of every check after it.
        if len(content) > self.settings.max_upload_bytes:
            raise DocumentTooLargeError(
                f"{safe_name!r} is {len(content) / 1024 / 1024:.1f} MB; the limit is "
                f"{self.settings.max_upload_mb} MB.",
                hint="Split the document or raise security.uploads.max_upload_mb.",
            )

        extension = self.extension_of(safe_name)
        if extension not in self.settings.allowed_extensions:
            raise UnsupportedFileTypeError(
                f"{safe_name!r} has extension {extension or '(none)'!r}; this application accepts "
                f"{', '.join(self.settings.allowed_extensions)}.",
                hint="Convert the document and upload it again.",
            )

        declared = (content_type or "").split(";")[0].strip().lower()
        if declared and declared not in self.settings.allowed_mime_types:
            raise UnsupportedFileTypeError(
                f"{safe_name!r} declared content type {declared!r}, which is not accepted.",
                hint=f"Accepted: {', '.join(self.settings.allowed_mime_types)}.",
            )

        if self.settings.verify_magic_bytes:
            self._verify_magic(safe_name, extension, content)

        log.info(
            "upload validated",
            extra={
                "source_name": safe_name,
                "bytes": len(content),
                "extension": extension,
                "declared_type": declared,
            },
        )
        return safe_name

    # -- pieces -----------------------------------------------------------------------------------

    @staticmethod
    def safe_filename(filename: str) -> str:
        """Reduce a client-supplied filename to a base name with no path in it.

        A filename is attacker-controlled and reaches the filesystem, the database, and the prompt.
        ``../../etc/passwd`` and ``C:\\Windows\\system32\\x.pdf`` both reduce to their last segment.

        Both path flavours are stripped regardless of host platform: an upload arrives over HTTP from
        any client, so a Windows path can reach a POSIX server and vice versa. Using only
        ``os.path.basename`` would leave backslashes untouched on Linux.
        """
        candidate = filename.strip().replace("\x00", "")
        candidate = PureWindowsPath(PurePosixPath(candidate).name).name
        # Leading dots would create a hidden file; a bare extension is not a name.
        candidate = candidate.lstrip(". ")
        if not candidate:
            raise InvalidRequestError(
                "The upload has no usable filename.",
                hint="Send the file with a name, for example report.pdf.",
            )
        return candidate[:255]

    @staticmethod
    def extension_of(filename: str) -> str:
        _, _, extension = filename.rpartition(".")
        return extension.lower() if "." in filename else ""

    @staticmethod
    def _verify_magic(filename: str, extension: str, content: bytes) -> None:
        if extension in TEXTUAL_TYPES:
            UploadValidator._check_is_text(content, extension)
            return

        signatures = MAGIC_BYTES.get(extension)
        if not signatures:
            # An allowed extension with no known signature. Refuse rather than wave it through:
            # adding a format to the allowlist without adding its signature would silently disable
            # this check for that format, which is the failure mode the check exists to prevent.
            raise InvalidDocumentError(
                f"No content signature is registered for {extension!r} uploads.",
                hint="Add the format's magic bytes to backend/validation.py before allowing it.",
            )

        window = content[:MAGIC_WINDOW]
        if not any(signature in window for signature in signatures):
            raise InvalidDocumentError(
                f"{filename!r} does not contain a {extension.upper()} signature in its first "
                f"{MAGIC_WINDOW} bytes; its contents do not match its extension.",
                hint="The file may be renamed, corrupt, or truncated.",
            )


    @staticmethod
    def _check_is_text(content: bytes, extension: str) -> None:
        """Verify a file claiming to be text really is text.

        Plain text has no magic bytes, so the signature check cannot apply -- but "no signature"
        must not become "no check". A NUL byte does not occur in a UTF-8 text document and does
        occur in essentially every binary format, which makes it a cheap, reliable discriminator;
        failing to decode is the other half.

        This is the same refusal the signature check makes, phrased for a format that has none: the
        file is not what it says it is.
        """
        if b"\x00" in content[:MAGIC_WINDOW]:
            raise InvalidDocumentError(
                f"This file is not {extension} text -- it contains binary data.",
                hint="Rename it to its real extension, or convert it to text first.",
            )
        try:
            content[:MAGIC_WINDOW].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidDocumentError(
                f"This file is not readable as {extension} text.",
                hint="Save it as UTF-8 and upload it again.",
            ) from exc
