"""The dashboard's error taxonomy, and the one place a technical failure becomes a sentence.

WHY A TAXONOMY AND NOT `except Exception`
    The brief lists six failures to handle gracefully -- backend offline, plugin failure, database
    failure, report failure, missing target, configuration error -- and they call for different
    *advice*, not just different wording. "Connection refused" tells an operator nothing; "the API
    is not running, start it with ..." tells them what to do next.

WHY THE MESSAGE LIVES WITH THE EXCEPTION
    Splitting the class from its remedy guarantees that adding an error class silently produces a
    blank remedy somewhere. Here, a new subclass cannot exist without one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FriendlyError:
    """What the UI actually renders: a title, a plain sentence, and a next step."""

    title: str
    message: str
    remedy: str = ""
    severity: str = "error"


class DashboardError(Exception):
    """Base for every failure the dashboard shows rather than raises to Streamlit."""

    title = "Something went wrong"
    remedy = ""
    severity = "error"

    def __init__(self, message: str = "", *, detail: str = "") -> None:
        super().__init__(message or self.title)
        self.message = message or self.title
        self.detail = detail

    def friendly(self) -> FriendlyError:
        return FriendlyError(
            title=self.title,
            message=self.message,
            remedy=self.remedy,
            severity=self.severity,
        )


class BackendUnavailableError(DashboardError):
    """The API could not be reached at all: refused, timed out, DNS, or not started."""

    title = "Backend offline"
    remedy = (
        "Start the RAGStrike API and reload. "
        "Set RAGSTRIKE_DASHBOARD__API_BASE_URL if it listens somewhere other than "
        "http://127.0.0.1:8000/api/v1."
    )


class NotImplementedByBackendError(DashboardError):
    """The endpoint exists in the design but the running backend does not serve it.

    Distinct from :class:`BackendUnavailableError` because the operator's next action is different: there
    is nothing to restart, the capability simply is not there yet. Rendered as a notice rather than
    an error, since it is a known state and not a fault.
    """

    title = "Not available yet"
    severity = "info"
    remedy = "This view needs an API endpoint that the running backend does not expose."


class BackendRequestError(DashboardError):
    """The backend answered, and the answer was a refusal."""

    title = "Request rejected"
    remedy = "Check the details below; the backend explained why."

    def __init__(self, message: str = "", *, status: int = 0, code: str = "", detail: str = ""):
        super().__init__(message, detail=detail)
        self.status = status
        self.code = code


class TargetMissingError(DashboardError):
    """A target was named that the backend does not know."""

    title = "Target not found"
    remedy = "Pick a target from the Targets page, or add one there."


class PluginFailureError(DashboardError):
    """A plugin operation -- enable, disable, reload, validate -- failed."""

    title = "Plugin operation failed"
    remedy = "Run `ragstrike plugins validate` for the full validation report."


class DatabaseFailureError(DashboardError):
    """The backend reported that its storage is unavailable."""

    title = "Storage unavailable"
    remedy = "The engine could not reach its database. Check the API logs and disk space."


class ReportFailureError(DashboardError):
    """Report generation or export failed."""

    title = "Report could not be produced"
    remedy = "Try a different format. PDF is a declared placeholder and does not render yet."


class ConfigurationProblemError(DashboardError):
    """The dashboard's own configuration is wrong."""

    title = "Configuration problem"
    severity = "warning"
    remedy = "Check the RAGSTRIKE_DASHBOARD__* environment variables on the Settings page."


class ScanRejectedError(DashboardError):
    """The backend refused to start a scan -- most often an authorization or scope refusal.

    Kept separate from :class:`BackendRequestError` because a refused scan is the framework working
    correctly, and phrasing it as an error trains operators to click past the one message that
    exists to stop them testing something they are not authorized to test.
    """

    title = "Scan refused"
    severity = "warning"
    remedy = (
        "RAGStrike only scans targets it is authorized and in scope for. "
        "Check the target's authorization block and the safety policy."
    )


#: Maps a backend error envelope ``code`` (SDD 22.1) onto the class that phrases it best. Codes the
#: backend has not defined yet fall through to :class:`BackendRequestError`, which shows the
#: backend's own message rather than inventing one.
ERROR_CODES: dict[str, type[DashboardError]] = {
    "authorization_missing": ScanRejectedError,
    "target_out_of_scope": ScanRejectedError,
    "target_not_found": TargetMissingError,
    "plugin_error": PluginFailureError,
    "plugin_validation_failed": PluginFailureError,
    "storage_error": DatabaseFailureError,
    "report_error": ReportFailureError,
    "configuration_error": ConfigurationProblemError,
}


def from_envelope(status: int, envelope: object) -> DashboardError:
    """Turn the API's error envelope into the right exception.

    The envelope is ``{"error": {"code", "message", "details", "correlation_id"}}``. Anything else
    -- an HTML error page from a proxy, an empty body -- still produces a usable error rather than a
    parse failure on top of the original failure.
    """
    code = ""
    message = ""
    detail = ""
    if isinstance(envelope, dict):
        error = envelope.get("error")
        if isinstance(error, dict):
            code = str(error.get("code", ""))
            message = str(error.get("message", ""))
            correlation = str(error.get("correlation_id", ""))
            details = error.get("details")
            detail = f"{details}" if details else ""
            if correlation:
                detail = f"{detail}\ncorrelation_id: {correlation}".strip()

    cls = ERROR_CODES.get(code, BackendRequestError)
    if cls is BackendRequestError:
        return BackendRequestError(
            message or f"The backend returned HTTP {status}.",
            status=status,
            code=code,
            detail=detail,
        )
    return cls(message or cls.title, detail=detail)
