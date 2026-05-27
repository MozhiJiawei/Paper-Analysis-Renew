from __future__ import annotations

import unittest
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from paper_analysis.utils.ai_client import FallbackAiClient
from paper_analysis.utils.openrouter_client import OpenRouterEmbeddingResponse


@dataclass(slots=True)
class FakeProvider:
    api_key: str | None = "key"
    embedding_model: str | None = "embedding-model"
    chat_result: dict[str, Any] | None = None
    embedding_result: OpenRouterEmbeddingResponse | None = None
    chat_calls: int = 0
    embedding_calls: int = 0
    last_embedding_model: str | None = None

    @property
    def resolved_api_key(self) -> str | None:
        return self.api_key

    @property
    def resolved_embedding_model(self) -> str | None:
        return self.embedding_model

    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> Future[dict[str, Any]]:
        self.chat_calls += 1
        future: Future[dict[str, Any]] = Future()
        future.set_result(self.chat_result or {"success": True, "content": "ok"})
        return future

    def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> OpenRouterEmbeddingResponse:
        self.embedding_calls += 1
        self.last_embedding_model = model
        return self.embedding_result or OpenRouterEmbeddingResponse(
            success=True,
            vectors=[[1.0]],
            model=model or "",
        )


class FallbackAiClientUnitTests(unittest.TestCase):
    def test_chat_uses_primary_when_openrouter_succeeds(self) -> None:
        primary = FakeProvider(chat_result={"success": True, "content": "openrouter"})
        fallback = FakeProvider(chat_result={"success": True, "content": "doubao"})
        client = FallbackAiClient(primary=primary, fallback=fallback)

        result = client.submit([{"role": "user", "content": "ping"}]).result(timeout=5)

        self.assertEqual("openrouter", result["content"])
        self.assertEqual(1, primary.chat_calls)
        self.assertEqual(0, fallback.chat_calls)

    def test_chat_falls_back_to_doubao_when_openrouter_fails(self) -> None:
        primary = FakeProvider(chat_result={"success": False, "error": "openrouter down"})
        fallback = FakeProvider(chat_result={"success": True, "content": "doubao"})
        client = FallbackAiClient(primary=primary, fallback=fallback)

        result = client.submit([{"role": "user", "content": "ping"}]).result(timeout=5)

        self.assertEqual("doubao", result["content"])
        self.assertEqual(1, primary.chat_calls)
        self.assertEqual(1, fallback.chat_calls)

    def test_embedding_falls_back_with_fallback_model(self) -> None:
        primary = FakeProvider(
            embedding_model="openrouter-embedding",
            embedding_result=OpenRouterEmbeddingResponse(
                success=False,
                vectors=[],
                model="openrouter-embedding",
                error="openrouter down",
            ),
        )
        fallback = FakeProvider(
            embedding_model="doubao-embedding",
            embedding_result=OpenRouterEmbeddingResponse(
                success=True,
                vectors=[[0.1, 0.2]],
                model="doubao-embedding",
            ),
        )
        client = FallbackAiClient(primary=primary, fallback=fallback)

        response = client.embed_texts(["hello"], model=client.resolved_embedding_model)

        self.assertTrue(response.success)
        self.assertEqual([[0.1, 0.2]], response.vectors)
        self.assertEqual("openrouter-embedding", primary.last_embedding_model)
        self.assertEqual("doubao-embedding", fallback.last_embedding_model)


if __name__ == "__main__":
    unittest.main()
