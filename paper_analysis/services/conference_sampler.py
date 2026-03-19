from __future__ import annotations

from random import Random

from paper_analysis.domain.paper import Paper


def sample_papers(papers: list[Paper], limit: int = 10, seed: int = 42) -> list[Paper]:
    if len(papers) <= limit:
        return [
            _with_sample_reason(paper, "候选不足 10 篇，返回全部已录用论文")
            for paper in papers
        ]

    rng = Random(seed)
    sampled = rng.sample(papers, limit)
    return [
        _with_sample_reason(paper, f"固定种子随机抽样（seed={seed}）")
        for paper in sampled
    ]


def _with_sample_reason(paper: Paper, sampled_reason: str) -> Paper:
    paper.sampled_reason = sampled_reason
    return paper
