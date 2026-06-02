"""Translate final arXiv gated reports through OpenRouter."""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, wait
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from paper_analysis.cli.common import CliInputError
from paper_analysis.shared.paths import ARTIFACTS_DIR
from paper_analysis.utils.openrouter_client import OpenRouterClient

DEFAULT_TRANSLATION_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_BATCH_SIZE = 3
DEFAULT_CONCURRENCY = 3
DEFAULT_SINGLE_RETRY_ATTEMPTS = 3
SUBSCRIPTION_DATE_PARTS = 2
LONG_ABSTRACT_SOURCE_CHARS = 500
MIN_LONG_ABSTRACT_TRANSLATION_CHARS = 120
MIN_FENCED_BLOCK_LINES = 3
ProgressCallback = Callable[[str], None]

if TYPE_CHECKING:
    from pathlib import Path


class ChatClient(Protocol):
    """Minimal chat client protocol used by the translator and tests."""

    @property
    def resolved_chat_model(self) -> str:
        """Return the configured model name."""

    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> Future[dict[str, Any]]:
        """Submit one chat request."""


@dataclass(frozen=True, slots=True)
class FinalReportTranslationRequest:
    """Request for translating one arXiv final gated report."""

    subscription_date: str | None = None
    input_json_path: Path | None = None
    output_markdown_path: Path | None = None
    model: str = DEFAULT_TRANSLATION_MODEL
    batch_size: int = DEFAULT_BATCH_SIZE
    concurrency: int = DEFAULT_CONCURRENCY
    client: ChatClient | None = None
    progress: ProgressCallback | None = None


@dataclass(frozen=True, slots=True)
class FinalReportTranslationResult:
    """Paths and counts produced by a translation run."""

    input_json_path: Path
    output_markdown_path: Path
    model: str
    subscription_date: str
    translated_count: int
    accepted_count: int
    borderline_count: int
    missed_count: int


def translate_final_report(
    request: FinalReportTranslationRequest,
) -> FinalReportTranslationResult:
    """Translate final gated arXiv report titles/abstracts and render Markdown."""
    input_json_path = _resolve_input_json_path(request)
    output_markdown_path = request.output_markdown_path or input_json_path.with_name(
        "final-summary.zh.md"
    )
    payload = _load_json_object(input_json_path)
    subscription_date = _content_date(payload, request.subscription_date)
    sections = _extract_final_sections(payload)
    items = [
        *sections["accepted"],
        *sections["borderline"],
        *sections["missed"],
    ]
    if not items:
        raise CliInputError("最终报告没有可翻译的 gated 论文条目。")

    batch_size = _validate_positive("batch_size", request.batch_size)
    concurrency = _validate_positive("concurrency", request.concurrency)
    runtime_client = request.client or OpenRouterClient(
        chat_model=request.model,
        concurrency=concurrency,
    )
    owns_client = request.client is None
    try:
        translations = _translate_items(
            items=items,
            client=runtime_client,
            batch_size=batch_size,
            progress=request.progress,
        )
    finally:
        close_client = getattr(runtime_client, "close", None)
        if owns_client and callable(close_client):
            close_client()

    markdown = _render_bilingual_markdown(
        payload=payload,
        sections=sections,
        translations=translations,
        model=runtime_client.resolved_chat_model,
        subscription_date=subscription_date,
    )
    output_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_markdown_path.write_text(markdown, encoding="utf-8")
    return FinalReportTranslationResult(
        input_json_path=input_json_path,
        output_markdown_path=output_markdown_path,
        model=runtime_client.resolved_chat_model,
        subscription_date=subscription_date,
        translated_count=len(items),
        accepted_count=len(sections["accepted"]),
        borderline_count=len(sections["borderline"]),
        missed_count=len(sections["missed"]),
    )


def _resolve_input_json_path(request: FinalReportTranslationRequest) -> Path:
    if request.input_json_path is not None:
        return request.input_json_path
    if not request.subscription_date:
        latest_path = ARTIFACTS_DIR / "e2e" / "arxiv" / "latest" / "result.json"
        if latest_path.exists():
            return latest_path
        raise CliInputError("缺少 --subscription-date，且 latest/result.json 不存在。")
    yyyy_mm, mm_dd = _split_subscription_date(request.subscription_date)
    return (
        ARTIFACTS_DIR
        / "e2e"
        / "arxiv"
        / "daily"
        / yyyy_mm
        / mm_dd
        / "final-result.json"
    )


def _split_subscription_date(value: str) -> tuple[str, str]:
    parts = value.split("/")
    if len(parts) != SUBSCRIPTION_DATE_PARTS or not parts[0] or not parts[1]:
        raise CliInputError("subscription-date 格式必须为 YYYY-MM/MM-DD。")
    return parts[0], parts[1]


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CliInputError(f"找不到最终报告 JSON：{path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliInputError(f"最终报告 JSON 不是合法 JSON：{path}") from exc
    if not isinstance(payload, dict):
        raise CliInputError(f"最终报告 JSON 顶层不是对象：{path}")
    return payload


def _content_date(payload: dict[str, Any], fallback: str | None) -> str:
    review = payload.get("blue_team_review")
    if isinstance(review, dict):
        value = str(review.get("content_date", "") or "").strip()
        if value:
            return value
    return fallback or ""


def _extract_final_sections(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    raw_sections = payload.get("merged_recommendation_sections")
    if not isinstance(raw_sections, dict):
        raise CliInputError("最终报告缺少 merged_recommendation_sections，不能生成双语报告。")
    red_rows = _list_dicts(payload.get("papers"))
    red_by_id = {str(row.get("paper_id", "")): row for row in red_rows}
    candidate_rows = _list_dicts(payload.get("candidate_papers"))
    candidate_by_id = {str(row.get("paper_id", "")): row for row in candidate_rows}
    review = payload.get("blue_team_review")
    false_positive_items = _false_positive_items(
        red_by_id=red_by_id,
        review_payload=dict(review) if isinstance(review, dict) else {},
    )
    return {
        "accepted": _with_source_metadata(
            _normalize_items(raw_sections.get("blue_and_red_recommendations"), "accepted"),
            red_by_id,
        ),
        "borderline": [
            *_with_source_metadata(
                _normalize_items(
                    raw_sections.get("red_recommendations_blue_borderline"),
                    "borderline",
                ),
                red_by_id,
            ),
            *false_positive_items,
        ],
        "missed": _with_source_metadata(
            _normalize_items(raw_sections.get("blue_missed_recommendations"), "missed"),
            candidate_by_id,
        ),
    }


def _normalize_items(value: object, section: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        normalized["section"] = section
        items.append(normalized)
    return items


def _false_positive_items(
    *,
    red_by_id: dict[str, dict[str, Any]],
    review_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for review_item in _list_dicts(review_payload.get("false_positives")):
        paper_id = str(review_item.get("paper_id", ""))
        red_row = red_by_id.get(paper_id, {})
        item = {
            "paper_id": paper_id,
            "title": red_row.get("title") or review_item.get("title", ""),
            "abstract": red_row.get("abstract", ""),
            "authors": red_row.get("authors", ""),
            "organization": red_row.get("organization", ""),
            "category": red_row.get("sampled_reason", ""),
            "red_reason": _compact_red_reason(red_row),
            "blue_reason": review_item.get("reason", ""),
            "confidence": review_item.get("confidence", ""),
            "section": "false_positive",
        }
        if red_row.get("pdf_url"):
            item["pdf_url"] = red_row.get("pdf_url", "")
        items.append(item)
    return items


def _with_source_metadata(
    items: list[dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        paper_id = str(item.get("paper_id", ""))
        source = source_by_id.get(paper_id, {})
        enriched_item = dict(item)
        if not enriched_item.get("organization"):
            enriched_item["organization"] = source.get("organization", "")
        enriched.append(enriched_item)
    return enriched


def _compact_red_reason(row: dict[str, Any]) -> str:
    reasons = row.get("reasons")
    if not isinstance(reasons, list):
        return ""
    compact = [
        str(reason).strip()
        for reason in reasons
        if str(reason).strip()
        and not str(reason).startswith("基于标题、摘要与关键词宽召回主标签为")
    ]
    return "；".join(compact[:2])


def _translate_items(
    *,
    items: list[dict[str, Any]],
    client: ChatClient,
    batch_size: int,
    progress: ProgressCallback | None,
) -> dict[str, dict[str, str]]:
    batches = list(_chunk_list(items, batch_size))
    pending: dict[Future[dict[str, Any]], list[dict[str, Any]]] = {}
    for index, batch in enumerate(batches, start=1):
        _emit(progress, f"[translate-final-report] submit batch {index}/{len(batches)} size={len(batch)}")
        pending[client.submit(_build_translation_messages(batch), stream=False)] = batch

    translations: dict[str, dict[str, str]] = {}
    completed = 0
    while pending:
        done, _ = wait(pending.keys(), return_when=FIRST_COMPLETED)
        for future in done:
            batch = pending.pop(future)
            try:
                batch_translations = _parse_translation_result(future.result(), batch)
            except Exception as exc:  # noqa: BLE001 - provider formatting drift is retried per paper
                _emit(
                    progress,
                    "[translate-final-report] batch parse failed; "
                    f"retrying per paper: {exc}",
                )
                batch_translations = {
                    str(item.get("paper_id", "")): _retry_single_translation(
                        item=item,
                        client=client,
                    )
                    for item in batch
                }
            translations.update(batch_translations)
            completed += len(batch)
            _emit(progress, f"[translate-final-report] translated {completed}/{len(items)}")
    return translations


def _retry_single_translation(
    *,
    item: dict[str, Any],
    client: ChatClient,
) -> dict[str, str]:
    paper_id = str(item.get("paper_id", ""))
    last_error: Exception | None = None
    for _attempt in range(1, DEFAULT_SINGLE_RETRY_ATTEMPTS + 1):
        try:
            result = client.submit(_build_translation_messages([item]), stream=False).result()
            translations = _parse_translation_result(result, [item])
            translation = _single_translation(translations, paper_id)
        except Exception as exc:  # noqa: BLE001 - retry provider formatting drift
            last_error = exc
        else:
            return translation
    raise CliInputError(
        f"OpenRouter 单篇翻译重试 {DEFAULT_SINGLE_RETRY_ATTEMPTS} 次后仍失败：{last_error}"
    )


def _single_translation(
    translations: dict[str, dict[str, str]],
    paper_id: str,
) -> dict[str, str]:
    translation = translations.get(paper_id)
    if translation is None:
        raise CliInputError(f"OpenRouter 单篇翻译缺少 paper_id：{paper_id}")
    return translation


def _build_translation_messages(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    papers = [
        {
            "paper_id": str(item.get("paper_id", "")),
            "title": str(item.get("title", "")),
            "abstract": str(item.get("abstract", "")),
            "red_reason": str(item.get("red_reason", "")),
            "blue_reason": str(item.get("blue_reason", "")),
            "section": str(item.get("section", "")),
        }
        for item in items
    ]
    return [
        {
            "role": "system",
            "content": (
                "你是 arXiv 论文最终报告翻译助手。把英文标题和英文摘要忠实翻译为简体中文，"
                "保留 LLM、KV Cache、speculative decoding、VLM、"
                "latency、throughput、prefill、decode、GPU、MoE 等关键技术术语的英文或中英混写。"
                "不要压缩成一句话，不要改写成要点，不要新增原文没有的信息。"
                "只返回 JSON，不要 Markdown，不要解释。JSON 格式："
                '{"translations":[{"paper_id":"...","title_zh":"...","abstract_zh":"..."}]}。'
                "如果摘要为空，abstract_zh 返回空字符串。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"papers": papers}, ensure_ascii=False, indent=2),
        },
    ]


def _parse_translation_result(
    result: dict[str, Any],
    batch: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    if not result.get("success"):
        raise CliInputError(f"OpenRouter 翻译失败：{result.get('error') or 'unknown error'}")
    content = str(result.get("content", "") or "").strip()
    if not content:
        raise CliInputError("OpenRouter 翻译响应为空。")
    try:
        parsed = json.loads(_strip_code_fence(content))
    except json.JSONDecodeError as exc:
        raise CliInputError(f"OpenRouter 翻译响应不是合法 JSON：{content[:500]}") from exc
    if not isinstance(parsed, dict):
        raise CliInputError("OpenRouter 翻译响应顶层不是对象。")
    raw_translations = parsed.get("translations")
    if not isinstance(raw_translations, list):
        raise CliInputError("OpenRouter 翻译响应缺少 translations 数组。")

    expected_by_id = {str(item.get("paper_id", "")): item for item in batch}
    translations: dict[str, dict[str, str]] = {}
    for raw_item in raw_translations:
        if not isinstance(raw_item, dict):
            raise CliInputError("OpenRouter 翻译响应 translations 项不是对象。")
        paper_id = str(raw_item.get("paper_id", "") or "").strip()
        if paper_id not in expected_by_id:
            raise CliInputError(f"OpenRouter 翻译返回未知 paper_id：{paper_id}")
        translation = {
            "title_zh": str(raw_item.get("title_zh", "") or "").strip(),
            "abstract_zh": str(raw_item.get("abstract_zh", "") or "").strip(),
        }
        _validate_translation(expected_by_id[paper_id], translation)
        translations[paper_id] = translation

    missing = sorted(set(expected_by_id) - set(translations))
    if missing:
        raise CliInputError("OpenRouter 翻译缺少 paper_id：" + ", ".join(missing))
    return translations


def _validate_translation(item: dict[str, Any], translation: dict[str, str]) -> None:
    paper_id = str(item.get("paper_id", ""))
    source_value = str(item.get("abstract", "") or "").strip()
    translated_value = translation.get("abstract_zh", "").strip()
    if not source_value and not translated_value:
        return
    if not translated_value:
        raise CliInputError(f"paper_id={paper_id} 缺少 abstract_zh")
    if not _contains_cjk(translated_value):
        raise CliInputError(f"paper_id={paper_id} 的 abstract_zh 缺少中文内容")
    if (
        len(source_value) >= LONG_ABSTRACT_SOURCE_CHARS
        and len(translated_value) < MIN_LONG_ABSTRACT_TRANSLATION_CHARS
    ):
        raise CliInputError(
            f"paper_id={paper_id} 的摘要翻译过短，疑似被压缩：{len(translated_value)} 字"
        )


def _render_bilingual_markdown(
    *,
    payload: dict[str, Any],
    sections: dict[str, list[dict[str, Any]]],
    translations: dict[str, dict[str, str]],
    model: str,
    subscription_date: str,
) -> str:
    raw_review = payload.get("blue_team_review")
    review: dict[str, Any] = dict(raw_review) if isinstance(raw_review, dict) else {}
    raw_layers = payload.get("recommendation_layers")
    layers: dict[str, Any] = dict(raw_layers) if isinstance(raw_layers, dict) else {}
    lines = [
        "# arXiv 最终融合推荐报告（标题/摘要双语）",
        "",
        f"- 内容日期：{subscription_date}",
        f"- 标题/摘要翻译模型：{model}",
        f"- 分析候选：{layers.get('analyzed_count', len(payload.get('candidate_papers', [])))}",
        f"- 红军 strict 推荐：{layers.get('strict_positive_count', payload.get('count', ''))}",
        f"- 蓝军误推荐：{review.get('false_positive_count', 0)}",
        f"- 蓝军存疑：{review.get('borderline_count', 0)}",
        f"- 蓝军漏推荐：{review.get('missed_count', 0)}",
        "",
        "## 1. 蓝军推荐 + 红军推荐",
        "",
        *_render_section_items(sections["accepted"], translations, reason_label="蓝军意见"),
        "",
        "## 2. 红军推荐 + 蓝军存疑/误推荐",
        "",
        *_render_section_items(sections["borderline"], translations, reason_label="蓝军意见"),
        "",
        "## 3. 蓝军漏推荐",
        "",
        *_render_section_items(sections["missed"], translations, reason_label="蓝军漏推荐依据"),
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _render_section_items(
    items: list[dict[str, Any]],
    translations: dict[str, dict[str, str]],
    *,
    reason_label: str,
) -> list[str]:
    if not items:
        return ["- 无", ""]
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        paper_id = str(item.get("paper_id", ""))
        translation = translations.get(paper_id, {})
        lines.append(f"### {index}. {item.get('title', '')}")
        if translation.get("title_zh"):
            lines.append(f"- 中文标题：{translation['title_zh']}")
        if item.get("authors"):
            lines.append(f"- 作者：{item.get('authors', '')}")
        organization = str(item.get("organization", "") or "").strip()
        lines.append(f"- 组织：{organization or '未知'}")
        lines.append(f"- 推荐类别：{item.get('category', '') or '未分类'}")
        if item.get("abstract"):
            lines.append(f"- Abstract (EN)：{item.get('abstract', '')}")
            lines.append(f"- 摘要（中文）：{translation.get('abstract_zh', '')}")
        if item.get("red_reason"):
            lines.append(f"- 红军推荐依据：{item.get('red_reason', '')}")
        if item.get("blue_reason"):
            confidence = item.get("confidence", "")
            suffix = f" (confidence={confidence})" if confidence != "" else ""
            lines.append(f"- {reason_label}：{item.get('blue_reason', '')}{suffix}")
        if item.get("pdf_url"):
            lines.append(f"- 链接：PDF: {item.get('pdf_url', '')}")
        lines.append("")
    return lines


def _chunk_list(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _validate_positive(name: str, value: int) -> int:
    if value < 1:
        raise CliInputError(f"{name} 必须大于等于 1")
    return value


def _strip_code_fence(value: str) -> str:
    stripped = value.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= MIN_FENCED_BLOCK_LINES and lines[-1].strip() == "```":
        first = lines[0].strip()
        if first in {"```", "```json", "```JSON"}:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _emit(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)
