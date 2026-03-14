from __future__ import annotations

import json
from typing import Any
from urllib import error, request


class OllamaClientError(RuntimeError):
    """Raised when the local Ollama runtime cannot satisfy a request."""


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str,
        llm_model: str,
        embed_model: str,
        timeout_sec: int = 60,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._llm_model = llm_model
        self._embed_model = embed_model
        self._timeout_sec = timeout_sec

    def generate_summary(self, *, search_text: str) -> str:
        prompt = (
            "/no_think\n"
            "Summarize the following note search document for a note card. "
            "Return plain text only, in 1-2 concise sentences, and do not add bullets or labels.\n\n"
            f"{search_text}"
        )
        payload = self._post_json(
            "/api/generate",
            {
                "model": self._llm_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        response_text = payload.get("response")
        if not isinstance(response_text, str):
            raise OllamaClientError("Ollama generate response did not include text")
        return response_text.strip()

    def embed_text(self, *, text: str) -> list[float]:
        payload = self._post_json(
            "/api/embed",
            {
                "model": self._embed_model,
                "input": text,
            },
        )
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or not embeddings:
            raise OllamaClientError("Ollama embed response did not include embeddings")

        embedding = embeddings[0]
        if not isinstance(embedding, list):
            raise OllamaClientError("Ollama embed response returned an invalid embedding")

        try:
            return [float(value) for value in embedding]
        except (TypeError, ValueError) as exc:
            raise OllamaClientError("Ollama embed response returned a non-numeric embedding") from exc

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        target = f"{self._base_url}{path}"
        raw_body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            target,
            data=raw_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self._timeout_sec) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OllamaClientError(f"Ollama request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise OllamaClientError(f"Ollama request failed: {exc.reason}") from exc

        if not isinstance(response_payload, dict):
            raise OllamaClientError("Ollama response payload was not a JSON object")

        return response_payload
