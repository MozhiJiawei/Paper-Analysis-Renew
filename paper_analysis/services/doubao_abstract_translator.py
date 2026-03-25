from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from paper_analysis.domain.benchmark import CandidatePaper
from paper_analysis.utils.doubao_client import DoubaoClient


Runner = Callable[[list[dict[str, Any]]], dict[str, Any]]


@dataclass(slots=True)
class DoubaoAbstractTranslator:
    runner: Runner | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    config_path: Path | None = None
    _client: DoubaoClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = DoubaoClient(
            runner=self.runner,
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            config_path=self.config_path,
        )

    def translate(self, candidate: CandidatePaper) -> str:
        abstract = candidate.abstract.strip()
        if not abstract:
            return ""
        messages = build_doubao_abstract_translation_messages(candidate)
        result = self._client.chat(messages, stream=False)
        if not result.get("success"):
            raise RuntimeError(f"Doubao 中文摘要生成失败：{result.get('error', '未知错误')}")
        return parse_doubao_abstract_translation_payload(str(result.get("content", "")))


def build_doubao_abstract_translation_messages(candidate: CandidatePaper) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是论文摘要翻译助手。你的任务是把英文论文摘要忠实翻译成简体中文。"
                "只输出中文摘要正文，不要输出标题、前后缀、解释、项目符号、引号或 Markdown。"
                "不要补充原文没有的信息，不要压缩成提纲。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"title={candidate.title}\n"
                f"abstract={candidate.abstract}"
            ),
        },
    ]


def parse_doubao_abstract_translation_payload(payload: str) -> str:
    text = payload.strip()
    if not text:
        raise ValueError("Doubao 未返回中文摘要")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Doubao 未返回中文摘要")
    normalized = "\n".join(lines)
    lowered = normalized.lower()
    if "```" in normalized:
        raise ValueError("Doubao 中文摘要输出格式非法")
    if any(fragment in lowered for fragment in ("translation:", "here is")):
        raise ValueError("Doubao 中文摘要包含附加说明")
    if any(fragment in normalized for fragment in ("中文翻译：", "以下是", "摘要翻译：")):
        raise ValueError("Doubao 中文摘要包含附加说明")
    if not _contains_cjk(normalized):
        raise ValueError("Doubao 中文摘要缺少中文内容")
    return normalized


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)
