from __future__ import annotations

from pathlib import Path

from paper_analysis.cli.common import CliInputError, read_json_file
from paper_analysis.domain.paper import Paper
from paper_analysis.domain.preference import PreferenceProfile


def load_papers(path: Path) -> list[Paper]:
    raw_items = read_json_file(path)
    if not isinstance(raw_items, list):
        raise CliInputError(f"论文输入必须是 JSON 数组：{path}")

    papers: list[Paper] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise CliInputError(f"论文输入项必须是对象：{path}")
        try:
            papers.append(Paper(**item))
        except TypeError as exc:
            raise CliInputError(f"论文输入字段不完整或不合法：{path}") from exc
    return papers


def load_preferences(path: Path) -> PreferenceProfile:
    raw = read_json_file(path)
    if not isinstance(raw, dict):
        raise CliInputError(f"偏好输入必须是 JSON 对象：{path}")
    try:
        return PreferenceProfile(**raw)
    except TypeError as exc:
        raise CliInputError(f"偏好输入字段不完整或不合法：{path}") from exc
