"""Default AI client with OpenRouter primary and Doubao fallback."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Protocol

from paper_analysis.utils.doubao_client import DoubaoClient
from paper_analysis.utils.openrouter_client import OpenRouterClient


class AiEmbeddingResponse(Protocol):
    """Minimal embedding response shared by provider clients."""

    success: bool
    vectors: list[list[float]]
    model: str
    error: str | None


class AiProviderClient(Protocol):
    """Provider client surface used by fallback routing."""

    @property
    def resolved_api_key(self) -> str | None:
        """Return the resolved API key when configured."""
        ...

    @property
    def resolved_embedding_model(self) -> str | None:
        """Return the resolved embedding model when configured."""
        ...

    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> Future[dict[str, Any]]:
        """Submit one chat-completion request."""
        ...

    def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> AiEmbeddingResponse:
        """Embed a batch of texts."""
        ...


@dataclass(slots=True)
class FallbackAiClient:
    """AI client that tries OpenRouter first and falls back to Doubao on failure."""

    primary: AiProviderClient | None = None
    fallback: AiProviderClient | None = None
    concurrency: int = 1
    _executor: ThreadPoolExecutor | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        """Build default providers when callers do not inject test doubles."""
        if self.primary is None:
            self.primary = OpenRouterClient(concurrency=self.concurrency)
        if self.fallback is None:
            self.fallback = DoubaoClient(concurrency=self.concurrency)

    @property
    def resolved_api_key(self) -> str | None:
        """Return the first configured API key across primary and fallback providers."""
        primary_key = self.primary.resolved_api_key if self.primary is not None else None
        fallback_key = self.fallback.resolved_api_key if self.fallback is not None else None
        return primary_key or fallback_key

    @property
    def resolved_embedding_model(self) -> str | None:
        """Return the primary embedding model, falling back to Doubao when needed."""
        primary_model = (
            self.primary.resolved_embedding_model if self.primary is not None else None
        )
        fallback_model = (
            self.fallback.resolved_embedding_model if self.fallback is not None else None
        )
        return primary_model or fallback_model

    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> Future[dict[str, Any]]:
        """Submit one chat-completion request through OpenRouter, then Doubao if needed."""
        return self._get_executor().submit(self._run_chat_sync, messages, stream=stream)

    def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> AiEmbeddingResponse:
        """Embed texts with OpenRouter first, then Doubao if OpenRouter fails."""
        primary_model = model or (
            self.primary.resolved_embedding_model if self.primary is not None else None
        )
        primary_error: str | None = None
        if self.primary is not None:
            try:
                primary_response = self.primary.embed_texts(texts, model=primary_model)
            except (RuntimeError, ValueError) as exc:
                primary_error = str(exc)
            else:
                if primary_response.success:
                    return primary_response
                primary_error = primary_response.error

        if self.fallback is None:
            raise RuntimeError(primary_error or "OpenRouter embedding 调用失败，且未配置兜底 provider。")
        fallback_model = self.fallback.resolved_embedding_model
        fallback_response = self.fallback.embed_texts(texts, model=fallback_model)
        if not fallback_response.success and primary_error:
            fallback_response.error = (
                f"OpenRouter 调用失败：{primary_error}；Doubao 兜底也失败："
                f"{fallback_response.error or '未知错误'}"
            )
        return fallback_response

    def _run_chat_sync(self, messages: list[dict[str, Any]], *, stream: bool = False) -> dict[str, Any]:
        primary_error: str | None = None
        if self.primary is not None:
            try:
                primary_result = self.primary.submit(messages, stream=stream).result()
            except (RuntimeError, TimeoutError, ValueError) as exc:
                primary_error = str(exc)
            else:
                if bool(primary_result.get("success")):
                    return primary_result
                primary_error = str(primary_result.get("error") or "未知错误")

        if self.fallback is None:
            raise RuntimeError(primary_error or "OpenRouter chat 调用失败，且未配置兜底 provider。")
        fallback_result = self.fallback.submit(messages, stream=stream).result()
        if not bool(fallback_result.get("success")) and primary_error:
            fallback_result["error"] = (
                f"OpenRouter 调用失败：{primary_error}；Doubao 兜底也失败："
                f"{fallback_result.get('error') or '未知错误'}"
            )
        return fallback_result

    def _get_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.concurrency)
        return self._executor
