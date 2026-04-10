"""Sampling helpers for conference paper candidates."""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paper_analysis.domain.paper import Paper


def sample_papers(papers: list[Paper], limit: int = 10, seed: int = 42) -> list[Paper]:
    """Return up to ``limit`` papers with stable sampling reasons attached."""
    if len(papers) <= limit:
        return [
            _with_sample_reason(paper, "候选不足 10 篇，返回全部已录用论文")
            for paper in papers
        ]

    rng = Random(seed)  # noqa: S311 - deterministic sampling is required for reproducible reports
    sampled = rng.sample(papers, limit)
    return [
        _with_sample_reason(paper, f"固定种子随机抽样（seed={seed}）")
        for paper in sampled
    ]


def _with_sample_reason(paper: Paper, sampled_reason: str) -> Paper:
    """Mutate one paper in place with the selected sampling reason."""
    paper.sampled_reason = sampled_reason
    return paper
