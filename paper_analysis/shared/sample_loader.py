"""JSON sample loaders shared by CLI entrypoints and integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from paper_analysis.cli.common import CliInputError, read_json_file
from paper_analysis.domain.paper import Paper
from paper_analysis.domain.preference import PreferenceProfile

if TYPE_CHECKING:
    from pathlib import Path


def load_papers(path: Path) -> list[Paper]:
    """Load fixture papers from JSON and validate the item shape."""
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
    """Load one preference profile from JSON and validate the payload shape."""
    raw = read_json_file(path)
    if not isinstance(raw, dict):
        raise CliInputError(f"偏好输入必须是 JSON 对象：{path}")
    try:
        return PreferenceProfile(**raw)
    except TypeError as exc:
        raise CliInputError(f"偏好输入字段不完整或不合法：{path}") from exc
