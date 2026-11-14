"""Choose a real embedding provider (API or local) and implement this contract."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class OllamaEmbedder:
    """Embedding provider using a local Ollama instance."""

    def __init__(self, model_name: str | None = None, base_url: str | None = None) -> None:
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL") or "nomic-embed-text"
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")

        # Test connection and infer vector dimensions
        try:
            sample_vec = self._request_embedding("probe")
            self.dimensions = len(sample_vec)
        except Exception as exc:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url} with model '{self.model_name}'. "
                f"Ensure Ollama is running and the model is downloaded (`ollama pull {self.model_name}`). "
                f"Error details: {exc}"
            ) from exc

    def _post(self, endpoint: str, data: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _request_embedding(self, text: str) -> list[float]:
        # Try modern /api/embed first
        try:
            res = self._post("/api/embed", {"model": self.model_name, "input": text})
            if "embeddings" in res and res["embeddings"]:
                return res["embeddings"][0]
        except urllib.error.HTTPError as err:
            if err.code != 404:
                raise

        # Fallback to older /api/embeddings endpoint
        res = self._post("/api/embeddings", {"model": self.model_name, "prompt": text})
        return res["embedding"]

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []

        # Nomic models perform best with prefix "search_document: "
        is_nomic = "nomic" in self.model_name.lower()
        formatted_texts = [
            f"search_document: {t}" if is_nomic and not t.startswith("search_document:") else t
            for t in texts
        ]

        results: list[list[float]] = []
        for i in range(0, len(formatted_texts), batch_size):
            batch = formatted_texts[i : i + batch_size]
            try:
                res = self._post("/api/embed", {"model": self.model_name, "input": batch})
                if "embeddings" in res and len(res["embeddings"]) == len(batch):
                    results.extend(res["embeddings"])
                    continue
            except Exception:
                pass

            # Fallback one by one if batch fails or older Ollama version
            for text in batch:
                results.append(self._request_embedding(text))

        return results

    def embed_query(self, question: str) -> list[float]:
        is_nomic = "nomic" in self.model_name.lower()
        formatted_question = (
            f"search_query: {question}" if is_nomic and not question.startswith("search_query:") else question
        )
        return self._request_embedding(formatted_question)


# Alias to satisfy the lab contract
MyEmbedder = OllamaEmbedder
