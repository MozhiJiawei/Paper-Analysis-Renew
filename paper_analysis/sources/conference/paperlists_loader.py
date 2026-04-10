"""Resolve supported conference/year targets inside the paperlists checkout."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from paper_analysis.cli.common import CliInputError
from paper_analysis.shared.paths import ROOT_DIR

if TYPE_CHECKING:
    from pathlib import Path

PAPERLISTS_ROOT = ROOT_DIR / "third_party" / "paperlists"

VENUE_ALIASES = {
    "iclr": "iclr",
    "neurips": "nips",
    "nips": "nips",
    "cvpr": "cvpr",
    "icml": "icml",
    "corl": "corl",
    "emnlp": "emnlp",
    "siggraph": "siggraph",
    "siggraphasia": "siggraphasia",
    "siggraph-asia": "siggraphasia",
}

VENUE_DISPLAY_NAMES = {
    "iclr": "ICLR",
    "nips": "NeurIPS",
    "cvpr": "CVPR",
    "icml": "ICML",
    "corl": "CoRL",
    "emnlp": "EMNLP",
    "siggraph": "SIGGRAPH",
    "siggraphasia": "SIGGRAPH Asia",
}


@dataclass(slots=True)
class PaperlistsTarget:
    """Resolved conference/year location inside the paperlists repository."""

    venue_key: str
    venue_name: str
    year: int
    root: Path
    json_path: Path


def resolve_paperlists_target(
    venue: str,
    year: int,
    root: Path | None = None,
) -> PaperlistsTarget:
    """Validate a venue/year pair and resolve the backing paperlists JSON path."""
    normalized_venue = VENUE_ALIASES.get(venue.strip().lower())
    if normalized_venue is None:
        supported = ", ".join(sorted(VENUE_ALIASES))
        raise CliInputError(f"不支持的会议：{venue}。可选值：{supported}")

    resolved_root = (root or PAPERLISTS_ROOT).resolve()
    if not resolved_root.exists():
        raise CliInputError(
            f"paperlists 数据源不存在：{resolved_root}。"
            "请先执行 `git submodule update --init --recursive`"
        )

    json_path = resolved_root / normalized_venue / f"{normalized_venue}{year}.json"
    if not json_path.exists():
        raise CliInputError(f"未找到会议年份文件：{json_path}")

    return PaperlistsTarget(
        venue_key=normalized_venue,
        venue_name=VENUE_DISPLAY_NAMES.get(normalized_venue, normalized_venue.upper()),
        year=year,
        root=resolved_root,
        json_path=json_path,
    )
