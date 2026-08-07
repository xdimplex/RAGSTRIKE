"""Ollama chat client.

One HTTP call to ``/api/generate``, with the failure modes an operator actually hits mapped onto the
error taxonomy: Ollama not running, model not pulled, model too slow.

The frontend never talks to this. Streamlit calls FastAPI, FastAPI calls the RAG engine, the RAG
engine calls Ollama. Keeping that chain intact is what makes the API a stable attack surface.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol

import httpx

from rag.config import Settings
from rag.errors import (
    EmptyModelResponseError,
    ModelNotFoundError,
    ModelTimeoutError,
    ModelUnavailableError,
)

log = logging.getLogger(__name__)

#: Qwen3 emits its chain of thought in <think> tags. Kept out of the visible answer, but preserved
#: in the raw response so the Chat page can show it on request -- it is often where an injection
#: becomes visible before the final answer is even written.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    """The interface the generation pipeline depends on.

    A protocol rather than a concrete class so tests can substitute a scripted client and run the
    whole API without Ollama.
    """

    def generate(self, prompt: str) -> str: ...

    def health(self) -> dict[str, Any]: ...


class OllamaClient:
    """Talks to a local Ollama server."""

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.model.base_url.rstrip("/")
        self.model = settings.model.name
        self.temperature = settings.model.temperature
        self.max_tokens = settings.model.max_tokens
        self.timeout_s = settings.model.timeout_s
        self.strip_thinking = settings.model.strip_thinking
        self.think = settings.model.think

    def generate(self, prompt: str) -> str:
        """Send *prompt* and return the model's answer.

        Raises:
            ModelUnavailableError: Ollama is not reachable, or returned an error.
            ModelNotFoundError: The configured model is not pulled.
            ModelTimeoutError: No response within ``model.timeout_s``.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            # Qwen3 is a thinking model. Left on, it can spend the entire num_predict budget on
            # internal reasoning and return an empty answer -- and a lab whose answers sometimes
            # vanish is a lab nobody trusts. Off by default; `model.think: true` re-enables it.
            "think": self.think,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        try:
            response = httpx.post(
                f"{self.base_url}/api/generate", json=payload, timeout=self.timeout_s
            )
        except httpx.ConnectError as exc:
            raise ModelUnavailableError(
                f"Cannot reach Ollama at {self.base_url}.",
                hint="Start it with `ollama serve`, then retry.",
            ) from exc
        except httpx.TimeoutException as exc:
            raise ModelTimeoutError(
                f"The model did not respond within {self.timeout_s}s.",
                hint="Raise model.timeout_s, or use a smaller model such as qwen3:4b.",
            ) from exc

        if response.status_code == 404:
            raise ModelNotFoundError(
                f"Ollama does not have the model {self.model!r}.",
                hint=f"Run `ollama pull {self.model}`.",
            )
        if response.status_code >= 400:
            raise ModelUnavailableError(
                f"Ollama returned {response.status_code}: {response.text[:200]}",
                hint="Check the Ollama server logs.",
            )

        data: dict[str, Any] = response.json()
        raw = data.get("response", "") or ""
        # Thinking models return reasoning in its own field rather than inline <think> tags.
        thinking = data.get("thinking", "") or ""
        answer = self._clean(raw)

        if not answer:
            raise EmptyModelResponseError(
                f"{self.model!r} returned no answer text"
                + (
                    f" after {len(thinking)} characters of internal reasoning." if thinking else "."
                ),
                hint=(
                    "The token budget was spent on reasoning. Raise model.max_tokens, or set "
                    "model.think: false in configs/config.yaml."
                    if thinking
                    else "Check the Ollama server logs; the model may have been interrupted."
                ),
            )
        return answer

    def health(self) -> dict[str, Any]:
        """Report whether Ollama is up and whether the configured models are present.

        Never raises. The System Status page needs a diagnosis, not an exception.
        """
        status: dict[str, Any] = {
            "reachable": False,
            "base_url": self.base_url,
            "model": self.model,
            "model_available": False,
            "available_models": [],
            "detail": "",
        }
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            status["detail"] = f"Cannot reach Ollama at {self.base_url}: {exc}"
            return status

        status["reachable"] = True
        names = [m.get("name", "") for m in response.json().get("models", [])]
        status["available_models"] = names
        # Ollama reports "qwen3:4b"; a config of "qwen3" should still match.
        status["model_available"] = any(
            name == self.model or name.split(":")[0] == self.model.split(":")[0] for name in names
        )
        if not status["model_available"]:
            status["detail"] = (
                f"Model {self.model!r} is not pulled. Run `ollama pull {self.model}`."
            )
        return status

    def _clean(self, raw: str) -> str:
        text = _THINK_BLOCK.sub("", raw) if self.strip_thinking else raw
        return text.strip()
