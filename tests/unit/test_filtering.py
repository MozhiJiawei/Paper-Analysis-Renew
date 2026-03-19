from __future__ import annotations

import unittest

from paper_analysis.cli.quality import build_subprocess_env
from paper_analysis.domain.filtering import rank_papers
from paper_analysis.domain.paper import Paper
from paper_analysis.domain.preference import PreferenceProfile


class FilteringTests(unittest.TestCase):
    def test_rank_papers_prefers_topic_and_organization(self) -> None:
        papers = [
            Paper(
                paper_id="p1",
                title="Graph Planning with Agents",
                abstract="...",
                source="conference",
                venue="NeurIPS 2025",
                authors=["A"],
                tags=["agents", "planning", "benchmark"],
                organization="OpenAI",
                published_at="2025-12-01",
            ),
            Paper(
                paper_id="p2",
                title="Unrelated Vision Paper",
                abstract="...",
                source="conference",
                venue="CVPR 2025",
                authors=["B"],
                tags=["vision"],
                organization="Unknown Lab",
                published_at="2025-11-10",
            ),
        ]
        preferences = PreferenceProfile(
            preferred_topics=["agents"],
            preferred_subtopics=["planning"],
            preferred_organizations=["OpenAI"],
            limit=3,
        )

        ranked = rank_papers(papers, preferences)

        self.assertEqual(1, len(ranked))
        self.assertEqual("p1", ranked[0].paper_id)
        self.assertGreater(ranked[0].score, 0.0)

    def test_build_subprocess_env_forces_utf8(self) -> None:
        env = build_subprocess_env()
        self.assertEqual("1", env["PYTHONUTF8"])
        self.assertEqual("utf-8", env["PYTHONIOENCODING"])


if __name__ == "__main__":
    unittest.main()
