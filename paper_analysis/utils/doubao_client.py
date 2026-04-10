"""Shared Doubao API client for chat completion, embedding, and audit logging."""

from __future__ import annotations

import importlib
import json
import os
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, Self, cast

import yaml  # type: ignore[import-untyped]
from paper_analysis.shared.paths import ARTIFACTS_DIR, ROOT_DIR

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seed-2-0-pro-260215"
DEFAULT_EMBEDDING_BATCH_SIZE = 128
DEFAULT_CONFIG_DIR_NAME = ".paper-analysis"
DEFAULT_CONFIG_FILE_NAME = "doubao.yaml"
TEMPLATE_CONFIG_PATH = ROOT_DIR / "paper_analysis" / "config" / "doubao.template.yaml"
DEFAULT_AUDIT_LOG_PATH = ARTIFACTS_DIR / "audit" / "doubao-api.jsonl"
DEFAULT_AUDIT_REQUESTS_DIR = ARTIFACTS_DIR / "audit" / "doubao-api" / "requests"
Runner = Callable[[list[dict[str, Any]]], dict[str, Any]]
_AUDIT_LOG_LOCK = threading.Lock()
MAX_CONCURRENCY = 10
MAX_EMBEDDING_BATCH_SIZE = 256


class _EmbeddingItemProtocol(Protocol):
    embedding: list[float] | tuple[float, ...] | None


class _EmbeddingResponseProtocol(Protocol):
    data: list[_EmbeddingItemProtocol] | None
    usage: object


class _EmbeddingEndpointProtocol(Protocol):
    def create(self, *, model: str, input: list[str]) -> _EmbeddingResponseProtocol: ...  # noqa: A002


class _MultimodalEmbeddingDataProtocol(Protocol):
    embedding: list[float] | tuple[float, ...] | None


class _MultimodalEmbeddingResponseProtocol(Protocol):
    data: _MultimodalEmbeddingDataProtocol | None
    usage: object


class _MultimodalEmbeddingEndpointProtocol(Protocol):
    def create(
        self,
        *,
        model: str,
        input: list[dict[str, str]],  # noqa: A002
    ) -> _MultimodalEmbeddingResponseProtocol: ...


class _MessageProtocol(Protocol):
    content: str | None


class _ChoiceProtocol(Protocol):
    message: _MessageProtocol | None


class _DeltaProtocol(Protocol):
    content: str | None


class _StreamingChoiceProtocol(Protocol):
    delta: _DeltaProtocol


class _ChatResponseProtocol(Protocol):
    choices: list[_ChoiceProtocol]
    usage: object


class _StreamingChunkProtocol(Protocol):
    choices: list[_StreamingChoiceProtocol]
    usage: object


class _StreamingResponseProtocol(Protocol):
    usage: object

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool | None: ...

    def __iter__(self) -> Iterator[_StreamingChunkProtocol]: ...


class _ChatCompletionsEndpointProtocol(Protocol):
    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool,
    ) -> _ChatResponseProtocol | _StreamingResponseProtocol: ...


class _ChatEndpointProtocol(Protocol):
    completions: _ChatCompletionsEndpointProtocol


class _ArkClientProtocol(Protocol):
    embeddings: _EmbeddingEndpointProtocol
    multimodal_embeddings: _MultimodalEmbeddingEndpointProtocol
    chat: _ChatEndpointProtocol


@dataclass(slots=True)
class DoubaoConfig:
    """Resolved configuration values for one Doubao client instance."""

    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    embedding_model: str | None = None


@dataclass(slots=True)
class DoubaoUsage:
    """Token usage snapshot returned by Doubao chat or embedding APIs."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(slots=True)
class DoubaoResponse:
    """Normalized chat completion result returned to repository callers."""

    success: bool
    content: str | None
    error: str | None = None
    usage: DoubaoUsage | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the normalized response to a JSON-serializable payload."""
        payload = asdict(self)
        if self.usage is None:
            payload["usage"] = None
        return payload


@dataclass(slots=True)
class DoubaoEmbeddingResponse:
    """Normalized embedding result returned to repository callers."""

    success: bool
    vectors: list[list[float]]
    model: str
    error: str | None = None
    usage: DoubaoUsage | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the embedding result to a JSON-serializable payload."""
        payload = asdict(self)
        if self.usage is None:
            payload["usage"] = None
        return payload


@dataclass(slots=True)
class DoubaoClient:
    """Thread-safe Doubao client with lazy SDK construction and audit logging."""

    runner: Runner | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    config_path: Path | None = None
    audit_log_path: Path | None = None
    concurrency: int = 1
    embedding_batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE
    _thread_local: threading.local = field(init=False, repr=False)
    _config: DoubaoConfig = field(init=False, repr=False)
    _executor: ThreadPoolExecutor | None = field(init=False, default=None, repr=False)
    _executor_lock: threading.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Load configuration, validate limits, and initialize lazy state."""
        self.concurrency = _validate_concurrency(self.concurrency)
        self.embedding_batch_size = _validate_embedding_batch_size(self.embedding_batch_size)
        config_payload = self._load_config()
        self._config = DoubaoConfig(
            api_key=self.api_key or os.getenv("ARK_API_KEY") or config_payload.get("api_key"),
            base_url=self.base_url or config_payload.get("base_url", DEFAULT_BASE_URL),
            model=self.model or config_payload.get("model", DEFAULT_MODEL),
            embedding_model=config_payload.get("embedding_model"),
        )
        self._thread_local = threading.local()
        self._executor_lock = threading.Lock()

    @property
    def resolved_api_key(self) -> str | None:
        """Return the resolved API key after env/config fallback."""
        return self._config.api_key

    @property
    def resolved_base_url(self) -> str:
        """Return the resolved Doubao base URL."""
        return self._config.base_url

    @property
    def resolved_model(self) -> str:
        """Return the resolved default chat model."""
        return self._config.model

    @property
    def resolved_embedding_model(self) -> str | None:
        """Return the resolved embedding model when configured."""
        return self._config.embedding_model

    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> Future[dict[str, Any]]:
        """Submit one chat-completion request to the shared executor."""
        return self._get_executor().submit(self._run_chat_sync, messages, stream=stream)

    def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> DoubaoEmbeddingResponse:
        """Embed a batch of texts through the standard or multimodal API surface."""
        if not texts:
            return DoubaoEmbeddingResponse(success=True, vectors=[], model=model or "")
        resolved_model = model or self.resolved_embedding_model
        if not resolved_model:
            raise ValueError(
                "Doubao embedding 模型未设置，请在 ~/.paper-analysis/doubao.yaml 的 "
                "`doubao.embedding_model` 中填写可调用的 embedding endpoint / model。"
            )
        if not self.resolved_api_key:
            raise ValueError(
                "Doubao API 密钥未设置，请检查 ARK_API_KEY，或在用户私有配置中创建 "
                f"{_default_config_path()}（可参考模板 {TEMPLATE_CONFIG_PATH}）。"
            )
        started_at = time.perf_counter()
        request_id = str(uuid.uuid4())
        try:
            normalized = self._embed_texts_via_standard_api(
                texts=texts,
                model=resolved_model,
            )
        except Exception as exc:  # noqa: BLE001 - provider SDK raises backend-specific exception classes
            if _should_use_multimodal_embedding_api(resolved_model, exc):
                normalized = self._embed_texts_via_multimodal(
                    texts=texts,
                    model=resolved_model,
                )
            else:
                normalized = DoubaoEmbeddingResponse(
                    success=False,
                    vectors=[],
                    model=resolved_model,
                    error=str(exc),
                )
        self._write_audit_log(
            request_id=request_id,
            messages=[{"role": "embedding", "content": text} for text in texts],
            response=normalized.to_dict(),
            stream=False,
            duration_ms=_duration_ms(started_at),
            source="ark_sdk",
        )
        return normalized

    def _embed_texts_via_standard_api(
        self,
        *,
        texts: list[str],
        model: str,
    ) -> DoubaoEmbeddingResponse:
        vectors: list[list[float]] = []
        usage: DoubaoUsage | None = DoubaoUsage()
        for batch in _chunk_list(texts, self.embedding_batch_size):
            response = self._get_client().embeddings.create(model=model, input=batch)
            normalized = self._normalize_embedding_response(response=response, model=model)
            vectors.extend(normalized.vectors)
            usage = _merge_usage(usage, normalized.usage)
        return DoubaoEmbeddingResponse(
            success=True,
            vectors=vectors,
            model=model,
            usage=usage,
        )

    def _embed_texts_via_multimodal(
        self,
        *,
        texts: list[str],
        model: str,
    ) -> DoubaoEmbeddingResponse:
        vectors: list[list[float]] = []
        usage: DoubaoUsage | None = None
        try:
            for text in texts:
                response = self._get_client().multimodal_embeddings.create(
                    model=model,
                    input=[{"type": "text", "text": text}],
                )
                vectors.append(_extract_multimodal_embedding_vector(response))
                usage = _extract_usage(response) or usage
            return DoubaoEmbeddingResponse(
                success=True,
                vectors=vectors,
                model=model,
                usage=usage,
            )
        except Exception as exc:  # noqa: BLE001 - provider SDK raises backend-specific exception classes
            return DoubaoEmbeddingResponse(
                success=False,
                vectors=[],
                model=model,
                error=str(exc),
            )

    def _normalize_embedding_response(
        self,
        *,
        response: object,
        model: str,
    ) -> DoubaoEmbeddingResponse:
        typed_response = cast("_EmbeddingResponseProtocol", response)
        data = typed_response.data or []
        return DoubaoEmbeddingResponse(
            success=True,
            vectors=[list(item.embedding or []) for item in data],
            model=model,
            usage=_extract_usage(typed_response),
        )

    def _run_chat_sync(self, messages: list[dict[str, Any]], *, stream: bool = False) -> dict[str, Any]:
        started_at = time.perf_counter()
        request_id = str(uuid.uuid4())
        source = "runner" if self.runner is not None else "ark_sdk"
        if self.runner is not None:
            result = self.runner(messages)
            self._write_audit_log(
                request_id=request_id,
                messages=messages,
                response=result,
                stream=stream,
                duration_ms=_duration_ms(started_at),
                source=source,
            )
            return result
        if not self.resolved_api_key:
            raise ValueError(
                "Doubao API 密钥未设置，请检查 ARK_API_KEY，或在用户私有配置中创建 "
                f"{_default_config_path()}（可参考模板 {TEMPLATE_CONFIG_PATH}）。"
            )
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=self.resolved_model,
                messages=messages,
                stream=stream,
            )
            normalized = self._normalize_response(response, stream=stream)
        except Exception as exc:  # noqa: BLE001 - provider SDK raises backend-specific exception classes
            normalized = DoubaoResponse(success=False, content=None, error=str(exc))
        result = normalized.to_dict()
        self._write_audit_log(
            request_id=request_id,
            messages=messages,
            response=result,
            stream=stream,
            duration_ms=_duration_ms(started_at),
            source=source,
        )
        return result

    def _get_executor(self) -> ThreadPoolExecutor:
        if self._executor is not None:
            return self._executor
        with self._executor_lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=self.concurrency)
        return self._executor

    def _get_client(self) -> _ArkClientProtocol:
        existing = getattr(self._thread_local, "client", None)
        if existing is not None:
            return cast("_ArkClientProtocol", existing)
        ark_module = importlib.import_module("volcenginesdkarkruntime")
        ark_client = ark_module.Ark

        client = ark_client(
            base_url=self.resolved_base_url,
            timeout=1800,
            api_key=self.resolved_api_key,
        )
        self._thread_local.client = client
        return cast("_ArkClientProtocol", client)

    def _load_config(self) -> dict[str, Any]:
        config_path = self.config_path or _default_config_path()
        if not config_path.exists():
            return {}
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        doubao_config = payload.get("doubao")
        return dict(doubao_config) if isinstance(doubao_config, dict) else {}

    def _normalize_response(
        self,
        response: _ChatResponseProtocol | _StreamingResponseProtocol,
        *,
        stream: bool,
    ) -> DoubaoResponse:
        if stream:
            return self._normalize_streaming_response(cast("_StreamingResponseProtocol", response))
        content = ""
        typed_response = cast("_ChatResponseProtocol", response)
        if typed_response.choices and typed_response.choices[0].message is not None:
            content = typed_response.choices[0].message.content or ""
        return DoubaoResponse(
            success=True,
            content=content,
            usage=_extract_usage(typed_response),
        )

    def _normalize_streaming_response(self, response: _StreamingResponseProtocol) -> DoubaoResponse:
        chunks: list[str] = []
        usage: DoubaoUsage | None = None
        with response:
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    chunks.append(chunk.choices[0].delta.content)
                usage = _extract_usage(chunk) or usage
        if usage is None:
            usage = _extract_usage(response)
        return DoubaoResponse(
            success=True,
            content="".join(chunks),
            usage=usage,
        )

    def _write_audit_log(
        self,
        *,
        request_id: str,
        messages: list[dict[str, Any]],
        response: dict[str, Any],
        stream: bool,
        duration_ms: int,
        source: str,
    ) -> None:
        audit_path = self.audit_log_path or DEFAULT_AUDIT_LOG_PATH
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        request_dir = self._resolve_request_dir(audit_path, request_id)
        prompt_path = request_dir / "prompt.md"
        response_path = request_dir / "response.md"
        error_path = request_dir / "error.txt"
        prompt_path.write_text(_render_prompt_markdown(messages), encoding="utf-8")
        response_content = str(response.get("content", "") or "")
        response_path.write_text(response_content, encoding="utf-8")
        error_value = response.get("error")
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "provider": "doubao",
            "source": source,
            "model": self.resolved_model,
            "base_url": self.resolved_base_url,
            "stream": stream,
            "message_count": len(messages),
            "message_roles": [str(message.get("role", "")) for message in messages],
            "success": bool(response.get("success")),
            "error": response.get("error"),
            "duration_ms": duration_ms,
            "response_chars": len(response_content),
            "prompt_path": str(prompt_path),
            "response_path": str(response_path),
            "usage": response.get("usage"),
        }
        if error_value:
            error_path.write_text(str(error_value), encoding="utf-8")
            payload["error_path"] = str(error_path)
        line = json.dumps(payload, ensure_ascii=False)
        with _AUDIT_LOG_LOCK, audit_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _resolve_request_dir(self, audit_path: Path, request_id: str) -> Path:
        if self.audit_log_path is not None:
            requests_root = audit_path.parent / "doubao-api" / "requests"
        else:
            requests_root = DEFAULT_AUDIT_REQUESTS_DIR
        request_dir = requests_root / request_id
        request_dir.mkdir(parents=True, exist_ok=True)
        return request_dir


def _extract_usage(response: object) -> DoubaoUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    if isinstance(usage, dict):
        return DoubaoUsage(
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )
    return DoubaoUsage(
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
    )


def _extract_multimodal_embedding_vector(response: object) -> list[float]:
    data = getattr(response, "data", None)
    embedding = getattr(data, "embedding", None)
    if embedding is None:
        raise ValueError("多模态 embedding 响应中缺少 embedding 字段。")
    return list(embedding)


def _should_use_multimodal_embedding_api(model: str, exc: Exception) -> bool:
    message = str(exc).lower()
    return "embedding-vision" in model.lower() and "does not support this api" in message


def _merge_usage(base: DoubaoUsage | None, extra: DoubaoUsage | None) -> DoubaoUsage | None:
    if base is None:
        return extra
    if extra is None:
        return base
    return DoubaoUsage(
        prompt_tokens=_sum_optional(base.prompt_tokens, extra.prompt_tokens),
        completion_tokens=_sum_optional(base.completion_tokens, extra.completion_tokens),
        total_tokens=_sum_optional(base.total_tokens, extra.total_tokens),
    )


def _sum_optional(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return None
    return (left or 0) + (right or 0)


def _chunk_list(items: list[Any], batch_size: int) -> list[list[Any]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def _duration_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _default_config_path() -> Path:
    config_root = os.getenv("PAPER_ANALYSIS_HOME")
    if config_root:
        return Path(config_root) / DEFAULT_CONFIG_FILE_NAME
    return Path.home() / DEFAULT_CONFIG_DIR_NAME / DEFAULT_CONFIG_FILE_NAME


def _render_prompt_markdown(messages: list[dict[str, Any]]) -> str:
    lines = ["# Prompt", ""]
    for index, message in enumerate(messages, start=1):
        role = str(message.get("role", ""))
        lines.append(f"## Message {index}")
        lines.append(f"- role: {role}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(message, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _validate_concurrency(value: int) -> int:
    if 1 <= value <= MAX_CONCURRENCY:
        return value
    raise ValueError(f"Doubao 并发非法：{value}；允许范围：1~{MAX_CONCURRENCY}")


def _validate_embedding_batch_size(value: int) -> int:
    if 1 <= value <= MAX_EMBEDDING_BATCH_SIZE:
        return value
    raise ValueError(
        f"Doubao embedding batch 非法：{value}；允许范围：1~{MAX_EMBEDDING_BATCH_SIZE}"
    )
