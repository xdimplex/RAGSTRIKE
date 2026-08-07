"""HTTP client for the FastAPI backend.

**The frontend never calls Ollama, ChromaDB, or the database directly.** The path is always

    Streamlit -> FastAPI -> RAG engine -> Ollama

That is not decoration. RAGStrike attacks the API, so every capability the UI has must exist as an
API capability; if the UI reached past the backend, the API would quietly drift into being
incomplete and the scanner would be testing a smaller surface than the one users actually have.

Errors arrive in the backend's envelope. :class:`ApiError` carries the code, message, and hint
through so a page can show a real diagnosis instead of a stack trace.
"""

from __future__ import annotations

from typing import Any

import httpx


class ApiError(Exception):
    """A structured error from the backend."""

    def __init__(self, code: str, message: str, hint: str = "", status: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.status = status

    def __str__(self) -> str:
        return f"{self.message} ({self.hint})" if self.hint else self.message


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 300.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # -- system ------------------------------------------------------------------------------

    def health(self, include_prompt: bool = False) -> dict[str, Any]:
        return self._get("/health", params={"include_prompt": str(include_prompt).lower()})

    def reachable(self) -> tuple[bool, str]:
        """Cheap probe for the page banners. Never raises."""
        try:
            httpx.get(f"{self.base_url}/health", timeout=5).raise_for_status()
            return True, ""
        except httpx.HTTPError as exc:
            return False, str(exc)

    # -- documents ---------------------------------------------------------------------------

    def upload(self, filename: str, content: bytes) -> dict[str, Any]:
        return self._request(
            "POST",
            "/upload",
            files={"file": (filename, content, "application/pdf")},
            timeout=180.0,
        )

    def documents(self) -> dict[str, Any]:
        return self._get("/documents")

    def document_chunks(self, document_id: str) -> dict[str, Any]:
        return self._get(f"/documents/{document_id}/chunks")

    def delete_document(self, document_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/documents/{document_id}")

    # -- chat --------------------------------------------------------------------------------

    def chat(
        self,
        message: str,
        *,
        session_id: str | None = None,
        top_k: int | None = None,
        include_prompt: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/chat",
            json={
                "message": message,
                "session_id": session_id,
                "top_k": top_k,
                "include_prompt": include_prompt,
            },
        )

    def reset_session(self, session_id: str) -> dict[str, Any]:
        return self._request("POST", "/chat/reset", json={"session_id": session_id})

    # -- internals ---------------------------------------------------------------------------

    def _get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self._request("GET", path, **kwargs)

    def _request(
        self, method: str, path: str, *, timeout: float | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.request(method, url, timeout=timeout or self.timeout, **kwargs)
        except httpx.ConnectError as exc:
            raise ApiError(
                "api_unreachable",
                f"Cannot reach the API at {self.base_url}.",
                "Start it with `python -m profiles.vulnerable.main_api`.",
            ) from exc
        except httpx.TimeoutException as exc:
            raise ApiError(
                "api_timeout",
                "The API did not respond in time.",
                "The model may still be loading. Try again in a moment.",
            ) from exc

        if response.status_code >= 400:
            raise self._to_error(response)
        return response.json()

    @staticmethod
    def _to_error(response: httpx.Response) -> ApiError:
        try:
            detail = response.json().get("error", {})
            return ApiError(
                code=detail.get("code", "unknown"),
                message=detail.get("message", response.text[:300]),
                hint=detail.get("hint", ""),
                status=response.status_code,
            )
        except ValueError:
            return ApiError("unknown", response.text[:300], status=response.status_code)
