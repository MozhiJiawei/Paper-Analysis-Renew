"""Shared OpenRouter API client for chat completion, embedding, and audit logging."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml
from paper_analysis.shared.paths import ARTIFACTS_DIR, ROOT_DIR

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_CHAT_MODEL = "deepseek/deepseek-v4-pro"
DEFAULT_EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
DEFAULT_EMBEDDING_BATCH_SIZE = 128
DEFAULT_CONFIG_DIR_NAME = ".paper-analysis"
DEFAULT_CONFIG_FILE_NAME = "openrouter.yaml"
TEMPLATE_CONFIG_PATH = ROOT_DIR / "paper_analysis" / "config" / "openrouter.template.yaml"
DEFAULT_AUDIT_LOG_PATH = ARTIFACTS_DIR / "audit" / "openrouter-api.jsonl"
DEFAULT_AUDIT_REQUESTS_DIR = ARTIFACTS_DIR / "audit" / "openrouter-api" / "requests"
Transport = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]
_AUDIT_LOG_LOCK = threading.Lock()
MAX_CONCURRENCY = 10
MAX_EMBEDDING_BATCH_SIZE = 256
REQUEST_TIMEOUT_SECONDS = 1800


@dataclass(slots=True)
class OpenRouterConfig:
    """Resolved configuration values for one OpenRouter client instance."""

    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    chat_model: str = DEFAULT_CHAT_MODEL
    embedding_model: str | None = DEFAULT_EMBEDDING_MODEL
    http_referer: str | None = None
    app_title: str | None = "paper-analysis"


@dataclass(slots=True)
class OpenRouterUsage:
    """Token usage snapshot returned by OpenRouter APIs."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(slots=True)
class OpenRouterResponse:
    """Normalized chat completion result returned to repository callers."""

    success: bool
    content: str | None
    error: str | None = None
    usage: OpenRouterUsage | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the normalized response to a JSON-serializable payload."""
        payload = asdict(self)
        if self.usage is None:
            payload["usage"] = None
        return payload


@dataclass(slots=True)
class OpenRouterEmbeddingResponse:
    """Normalized embedding result returned to repository callers."""

    success: bool
    vectors: list[list[float]]
    model: str
    error: str | None = None
    usage: OpenRouterUsage | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the embedding result to a JSON-serializable payload."""
        payload = asdict(self)
        if self.usage is None:
            payload["usage"] = None
        return payload


@dataclass(slots=True)
class OpenRouterClient:
    """Thread-safe OpenRouter client with lazy executor and audit logging."""

    transport: Transport | None = None
    api_key: str | None = None
    base_url: str | None = None
    chat_model: str | None = None
    embedding_model: str | None = None
    config_path: Path | None = None
    audit_log_path: Path | None = None
    concurrency: int = 1
    embedding_batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE
    _config: OpenRouterConfig = field(init=False, repr=False)
    _executor: ThreadPoolExecutor | None = field(init=False, default=None, repr=False)
    _executor_lock: threading.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Load configuration, validate limits, and initialize lazy state."""
        self.concurrency = _validate_concurrency(self.concurrency)
        self.embedding_batch_size = _validate_embedding_batch_size(self.embedding_batch_size)
        config_payload = self._load_config()
        self._config = OpenRouterConfig(
            api_key=self.api_key or os.getenv("OPENROUTER_API_KEY") or config_payload.get("api_key"),
            base_url=self.base_url
            or os.getenv("OPENROUTER_BASE_URL")
            or config_payload.get("base_url", DEFAULT_BASE_URL),
            chat_model=self.chat_model
            or os.getenv("OPENROUTER_CHAT_MODEL")
            or os.getenv("OPENROUTER_MODEL")
            or config_payload.get("chat_model")
            or config_payload.get("model", DEFAULT_CHAT_MODEL),
            embedding_model=_resolve_optional_config(
                self.embedding_model,
                os.getenv("OPENROUTER_EMBEDDING_MODEL"),
                config_payload.get("embedding_model"),
                DEFAULT_EMBEDDING_MODEL,
            ),
            http_referer=os.getenv("OPENROUTER_HTTP_REFERER")
            or config_payload.get("http_referer"),
            app_title=os.getenv("OPENROUTER_APP_TITLE")
            or config_payload.get("app_title", "paper-analysis"),
        )
        self._executor_lock = threading.Lock()

    @property
    def resolved_api_key(self) -> str | None:
        """Return the resolved API key after env/config fallback."""
        return self._config.api_key

    @property
    def resolved_base_url(self) -> str:
        """Return the resolved OpenRouter base URL."""
        return self._config.base_url

    @property
    def resolved_model(self) -> str:
        """Return the resolved default chat model."""
        return self._config.chat_model

    @property
    def resolved_chat_model(self) -> str:
        """Return the resolved default chat model."""
        return self._config.chat_model

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

    def close(self) -> None:
        """Release any worker threads owned by this client."""
        with self._executor_lock:
            executor = self._executor
            self._executor = None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=False)

    def __enter__(self) -> Self:
        """Return this client for context-manager use."""
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close worker resources when leaving a context manager."""
        self.close()

    def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> OpenRouterEmbeddingResponse:
        """Embed a batch of texts through OpenRouter's embedding API."""
        if not texts:
            return OpenRouterEmbeddingResponse(success=True, vectors=[], model=model or "")
        resolved_model = model or self.resolved_embedding_model
        if not resolved_model:
            raise ValueError(
                "OpenRouter embedding 模型未设置，请在 ~/.paper-analysis/openrouter.yaml 的 "
                "`openrouter.embedding_model` 中填写可调用的 embedding model。"
            )
        if not self.resolved_api_key:
            raise ValueError(
                "OpenRouter API 密钥未设置，请检查 OPENROUTER_API_KEY，或在用户私有配置中创建 "
                f"{_default_config_path()}（可参考模板 {TEMPLATE_CONFIG_PATH}）。"
            )
        started_at = time.perf_counter()
        request_id = str(uuid.uuid4())
        try:
            normalized = self._embed_texts_sync(texts=texts, model=resolved_model)
        except Exception as exc:  # noqa: BLE001 - network and provider failures are normalized
            normalized = OpenRouterEmbeddingResponse(
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
            source="transport" if self.transport is not None else "http",
            model=resolved_model,
        )
        return normalized

    def _embed_texts_sync(
        self,
        *,
        texts: list[str],
        model: str,
    ) -> OpenRouterEmbeddingResponse:
        vectors: list[list[float]] = []
        usage: OpenRouterUsage | None = OpenRouterUsage()
        for batch in _chunk_list(texts, self.embedding_batch_size):
            response = self._post_json(
                "/embeddings",
                {
                    "model": model,
                    "input": batch,
                },
            )
            normalized = _normalize_embedding_response(response=response, model=model)
            vectors.extend(normalized.vectors)
            usage = _merge_usage(usage, normalized.usage)
        return OpenRouterEmbeddingResponse(
            success=True,
            vectors=vectors,
            model=model,
            usage=usage,
        )

    def _run_chat_sync(self, messages: list[dict[str, Any]], *, stream: bool = False) -> dict[str, Any]:
        started_at = time.perf_counter()
        request_id = str(uuid.uuid4())
        source = "transport" if self.transport is not None else "http"
        if not self.resolved_api_key:
            raise ValueError(
                "OpenRouter API 密钥未设置，请检查 OPENROUTER_API_KEY，或在用户私有配置中创建 "
                f"{_default_config_path()}（可参考模板 {TEMPLATE_CONFIG_PATH}）。"
            )
        try:
            response = self._post_json(
                "/chat/completions",
                {
                    "model": self.resolved_chat_model,
                    "messages": messages,
                    "stream": stream,
                },
            )
            normalized = _normalize_chat_response(response)
        except Exception as exc:  # noqa: BLE001 - network and provider failures are normalized
            normalized = OpenRouterResponse(success=False, content=None, error=str(exc))
        result = normalized.to_dict()
        self._write_audit_log(
            request_id=request_id,
            messages=messages,
            response=result,
            stream=stream,
            duration_ms=_duration_ms(started_at),
            source=source,
            model=self.resolved_chat_model,
        )
        return result

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = _join_url(self.resolved_base_url, path)
        headers = self._headers()
        if self.transport is not None:
            return self.transport(url, payload, headers)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=data, headers=headers, method="POST")  # noqa: S310
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"OpenRouter 网络调用失败：{exc.reason}") from exc
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise TypeError("OpenRouter 响应不是 JSON object。")
        return parsed

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.resolved_api_key}",
            "Content-Type": "application/json",
        }
        if self._config.http_referer:
            headers["HTTP-Referer"] = self._config.http_referer
        if self._config.app_title:
            headers["X-Title"] = self._config.app_title
        return headers

    def _get_executor(self) -> ThreadPoolExecutor:
        if self._executor is not None:
            return self._executor
        with self._executor_lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=self.concurrency)
        return self._executor

    def _load_config(self) -> dict[str, Any]:
        config_path = self.config_path or _default_config_path()
        if not config_path.exists():
            return {}
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        openrouter_config = payload.get("openrouter")
        return dict(openrouter_config) if isinstance(openrouter_config, dict) else {}

    def _write_audit_log(
        self,
        *,
        request_id: str,
        messages: list[dict[str, Any]],
        response: dict[str, Any],
        stream: bool,
        duration_ms: int,
        source: str,
        model: str,
    ) -> None:
        audit_path = self.audit_log_path or DEFAULT_AUDIT_LOG_PATH
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        request_dir = self._resolve_request_dir(audit_path, request_id)
        prompt_path = request_dir / "prompt.md"
        response_path = request_dir / "response.md"
        error_path = request_dir / "error.txt"
        prompt_path.write_text(_render_prompt_markdown(messages), encoding="utf-8")
        response_content = str(response.get("content", "") or "")
        if not response_content and response.get("vectors"):
            response_content = json.dumps(response.get("vectors"), ensure_ascii=False)
        response_path.write_text(response_content, encoding="utf-8")
        error_value = response.get("error")
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "provider": "openrouter",
            "source": source,
            "model": model,
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
            requests_root = audit_path.parent / "openrouter-api" / "requests"
        else:
            requests_root = DEFAULT_AUDIT_REQUESTS_DIR
        request_dir = requests_root / request_id
        request_dir.mkdir(parents=True, exist_ok=True)
        return request_dir


def _normalize_chat_response(response: dict[str, Any]) -> OpenRouterResponse:
    choices = response.get("choices")
    content = ""
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message")
            if isinstance(message, dict):
                content = str(message.get("content", "") or "")
    return OpenRouterResponse(
        success=True,
        content=content,
        usage=_extract_usage(response),
    )


def _normalize_embedding_response(
    *,
    response: dict[str, Any],
    model: str,
) -> OpenRouterEmbeddingResponse:
    data = response.get("data")
    if not isinstance(data, list):
        raise TypeError("OpenRouter embedding 响应中缺少 data 数组。")
    vectors: list[list[float]] = []
    for item in data:
        if not isinstance(item, dict):
            raise TypeError("OpenRouter embedding data 项不是 JSON object。")
        embedding = item.get("embedding")
        if not isinstance(embedding, list):
            raise TypeError("OpenRouter embedding data 项缺少 embedding 数组。")
        vectors.append([float(value) for value in embedding])
    return OpenRouterEmbeddingResponse(
        success=True,
        vectors=vectors,
        model=model,
        usage=_extract_usage(response),
    )


def _extract_usage(response: dict[str, Any]) -> OpenRouterUsage | None:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    return OpenRouterUsage(
        prompt_tokens=_optional_int(usage.get("prompt_tokens")),
        completion_tokens=_optional_int(usage.get("completion_tokens")),
        total_tokens=_optional_int(usage.get("total_tokens")),
    )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _resolve_optional_config(
    explicit: str | None,
    env_value: str | None,
    config_value: object,
    default: str,
) -> str | None:
    if explicit is not None:
        return explicit
    if env_value is not None:
        return env_value
    if isinstance(config_value, str):
        return config_value
    return default


def _merge_usage(
    base: OpenRouterUsage | None,
    extra: OpenRouterUsage | None,
) -> OpenRouterUsage | None:
    if base is None:
        return extra
    if extra is None:
        return base
    return OpenRouterUsage(
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


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


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
    raise ValueError(f"OpenRouter 并发非法：{value}；允许范围：1~{MAX_CONCURRENCY}")


def _validate_embedding_batch_size(value: int) -> int:
    if 1 <= value <= MAX_EMBEDDING_BATCH_SIZE:
        return value
    raise ValueError(
        f"OpenRouter embedding batch 非法：{value}；允许范围：1~{MAX_EMBEDDING_BATCH_SIZE}"
    )
