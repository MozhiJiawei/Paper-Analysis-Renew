from __future__ import annotations

import unittest
from pathlib import Path

from paper_analysis.services.conference_sampler import sample_papers
from paper_analysis.sources.conference.paperlists_parser import (
    filter_accepted_records,
    load_raw_records,
    normalize_records,
)


ROOT_DIR = Path(__file__).resolve().parents[2]


class PaperlistsParserTests(unittest.TestCase):
    def test_filter_and_normalize_records(self) -> None:
        source_path = ROOT_DIR / "tests" / "fixtures" / "paperlists_repo" / "iclr" / "iclr2025.json"
        raw_records = load_raw_records(source_path, "ICLR", 2025)

        accepted = filter_accepted_records(raw_records)
        papers = normalize_records(accepted)

        self.assertEqual(2, len(papers))
        self.assertEqual("iclr-001", papers[0].paper_id)
        self.assertEqual("ICLR 2025", papers[0].venue)
        self.assertEqual("Spotlight", papers[0].acceptance_status)
        self.assertEqual(["Alice", "Bob"], papers[0].authors)
        self.assertIn("agents", papers[0].keywords)
        self.assertEqual("OpenAI", papers[0].organization)

    def test_sampler_is_stable_with_seed(self) -> None:
        source_path = ROOT_DIR / "tests" / "fixtures" / "paperlists_repo" / "iclr" / "iclr2025.json"
        raw_records = load_raw_records(source_path, "ICLR", 2025)
        papers = normalize_records(filter_accepted_records(raw_records))

        sampled_once = sample_papers(papers, limit=1, seed=7)
        sampled_twice = sample_papers(papers, limit=1, seed=7)

        self.assertEqual(sampled_once[0].paper_id, sampled_twice[0].paper_id)
        self.assertIn("seed=7", sampled_once[0].sampled_reason)


if __name__ == "__main__":
    unittest.main()
