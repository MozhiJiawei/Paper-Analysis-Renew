"""Shared paper ranking helper used by filtering pipelines."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paper_analysis.domain.paper import Paper
    from paper_analysis.domain.preference import PreferenceProfile


def rank_papers(candidates: list[Paper], preferences: PreferenceProfile) -> list[Paper]:
    """Score papers with a shared preference model."""
    ranked: list[Paper] = []
    preferred_topics = {topic.lower() for topic in preferences.preferred_topics}
    preferred_subtopics = {topic.lower() for topic in preferences.preferred_subtopics}
    preferred_organizations = {
        organization.lower() for organization in preferences.preferred_organizations
    }
    excluded_topics = {topic.lower() for topic in preferences.excluded_topics}

    for paper in candidates:
        lowered_tags = {tag.lower() for tag in paper.tags}
        score = 0.0
        reasons: list[str] = []

        for tag in lowered_tags:
            if tag in excluded_topics:
                score -= 3.0
                reasons.append(f"命中排除主题：{tag}")
            if tag in preferred_topics:
                score += 3.0
                reasons.append(f"命中偏好主题：{tag}")
            if tag in preferred_subtopics:
                score += 2.0
                reasons.append(f"命中偏好子类：{tag}")

        if paper.organization.lower() in preferred_organizations:
            score += 2.5
            reasons.append(f"来自偏好机构：{paper.organization}")

        if "benchmark" in lowered_tags or "evaluation" in lowered_tags:
            score += 0.5
            reasons.append("包含可验证评测信号")

        if score >= preferences.min_score:
            paper.score = round(score, 2)
            paper.reasons = reasons
            ranked.append(paper)

    ranked.sort(key=lambda item: (-item.score, item.title))
    return ranked[: preferences.limit]
