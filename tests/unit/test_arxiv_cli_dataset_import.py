from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from paper_analysis.cli import arxiv
from paper_analysis.domain.paper import Paper
from paper_analysis.services.arxiv_dataset_import import ArxivDatasetImportResult


class ArxivCliDatasetImportTests(unittest.TestCase):
    def test_report_does_not_import_dataset_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifacts = _report_artifacts(root)
            args = _args("report", subscription_date="2026-05/05-26")

            with (
                patch("paper_analysis.cli.arxiv.ArxivPipeline") as pipeline_class,
                patch("paper_analysis.cli.arxiv.write_report", return_value=artifacts),
                patch("paper_analysis.cli.arxiv._write_default_review_artifacts", return_value=None),
                patch("paper_analysis.cli.arxiv._append_blue_team_review_to_report"),
                patch(
                    "paper_analysis.cli.arxiv._archive_arxiv_report_run",
                    return_value=None,
                ),
                patch("paper_analysis.cli.arxiv._write_dataset_import_artifacts") as import_mock,
            ):
                pipeline_class.return_value.run_with_details.return_value = _pipeline_result()

                exit_code = arxiv.handle_report(args)

        self.assertEqual(0, exit_code)
        import_mock.assert_not_called()

    def test_import_dataset_runs_manual_import(self) -> None:
        args = _args("import-dataset", subscription_date="2026-05/05-26", fetch_all=True)
        import_result = ArxivDatasetImportResult(
            payload_path=Path("payload.json"),
            summary_path=Path("summary.json"),
            stdout_path=Path("stdout.txt"),
            record_count=2,
            positive_count=1,
            negative_count=1,
            boundary_negative_count=0,
            import_status="ok",
        )
        report_payload = {
            "papers": [_paper_row("p1", "Recommended", sampled_reason="模型压缩")],
            "candidate_papers": [
                _paper_row("p1", "Recommended", sampled_reason="模型压缩"),
                _paper_row("p2", "Candidate"),
            ],
        }

        with (
            patch(
                "paper_analysis.cli.arxiv._load_dataset_import_report_payload",
                return_value=report_payload,
            ),
            patch("paper_analysis.cli.arxiv._validate_dataset_import_review_artifact"),
            patch(
                "paper_analysis.cli.arxiv._write_dataset_import_artifacts",
                return_value=import_result,
            ) as import_mock,
        ):
            exit_code = arxiv.handle_import_dataset(args)

        self.assertEqual(0, exit_code)
        import_mock.assert_called_once()
        _, kwargs = import_mock.call_args
        self.assertEqual("2026-05/05-26", kwargs["content_date"])
        self.assertEqual(["p1", "p2"], [paper.paper_id for paper in kwargs["candidate_papers"]])

    def test_import_dataset_fails_when_daily_report_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_dir = Path(temp_dir) / "missing"

            with self.assertRaisesRegex(arxiv.CliInputError, "找不到分日报告产物"):
                arxiv._load_dataset_import_report_payload(  # noqa: SLF001
                    content_date="2026-05/05-26",
                    report_dir=missing_dir,
                )

    def test_import_dataset_rejects_stale_blue_team_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            review_json = Path(temp_dir) / "result.json"
            review_json.write_text(
                '{"status": "completed", "content_date": "2026-05/05-25"}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(arxiv.CliInputError, "日期不匹配"):
                arxiv._validate_dataset_import_review_artifact(  # noqa: SLF001
                    content_date="2026-05/05-26",
                    review_json_path=review_json,
                )

    def test_archive_places_report_and_review_in_one_daily_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_dir = root / "report"
            review_dir = root / "review"
            daily_dir = root / "daily" / "2026-05" / "05-26"
            report_dir.mkdir()
            review_dir.mkdir()
            (report_dir / "summary.md").write_text("report", encoding="utf-8")
            (report_dir / "result.json").write_text("{}", encoding="utf-8")
            (report_dir / "result.csv").write_text("csv", encoding="utf-8")
            (report_dir / "stdout.txt").write_text("stdout", encoding="utf-8")
            (review_dir / "summary.md").write_text("review", encoding="utf-8")
            (review_dir / "result.json").write_text('{"content_date":"2026-05/05-26"}', encoding="utf-8")
            (review_dir / "stdout.txt").write_text("review stdout", encoding="utf-8")

            with patch("paper_analysis.cli.arxiv._dated_report_dir", return_value=daily_dir):
                result = arxiv._archive_arxiv_report_run(  # noqa: SLF001
                    content_date="2026-05/05-26",
                    report_dir=report_dir,
                    review_dir=review_dir,
                )

            self.assertEqual({"daily_dir": daily_dir}, result)
            self.assertEqual("report", (daily_dir / "summary.md").read_text(encoding="utf-8"))
            self.assertEqual("review", (daily_dir / "review-summary.md").read_text(encoding="utf-8"))
            self.assertTrue((daily_dir / "review-result.json").exists())
            self.assertTrue((daily_dir / "review-stdout.txt").exists())


def _args(
    action: str,
    *,
    subscription_date: str | None = None,
    fetch_all: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        arxiv_action=action,
        input=None,
        preferences=None,
        source_mode="fixture",
        subscription_date=subscription_date,
        category=[],
        max_results=10,
        fetch_all=fetch_all,
        deliver_subscription=False,
    )


def _pipeline_result() -> SimpleNamespace:
    recommended = _paper("p1", "Recommended", sampled_reason="模型压缩")
    candidate = _paper("p2", "Candidate")
    return SimpleNamespace(
        papers=[recommended],
        preferences=None,
        fetched_count=2,
        candidate_papers=[recommended, candidate],
    )


def _paper(paper_id: str, title: str, *, sampled_reason: str = "") -> Paper:
    return Paper(
        paper_id=paper_id,
        title=title,
        abstract="A paper about model inference efficiency.",
        source="arxiv",
        venue="arXiv",
        authors=["Ada"],
        tags=["cs.AI"],
        organization="",
        published_at="2026-05-26",
        sampled_reason=sampled_reason,
    )


def _report_artifacts(root: Path) -> dict[str, Path]:
    markdown = root / "summary.md"
    json_path = root / "result.json"
    csv_path = root / "result.csv"
    stdout = root / "stdout.txt"
    markdown.write_text("", encoding="utf-8")
    json_path.write_text(json.dumps({"papers": []}, ensure_ascii=False), encoding="utf-8")
    csv_path.write_text("", encoding="utf-8")
    stdout.write_text("", encoding="utf-8")
    return {
        "markdown": markdown,
        "json": json_path,
        "csv": csv_path,
        "stdout": stdout,
    }


def _paper_row(paper_id: str, title: str, *, sampled_reason: str = "") -> dict[str, object]:
    return {
        "paper_id": paper_id,
        "title": title,
        "abstract": "A paper about model inference efficiency.",
        "source": "arxiv",
        "venue": "arXiv",
        "authors": "Ada",
        "tags": "cs.AI",
        "organization": "",
        "published_at": "2026-05-26",
        "sampled_reason": sampled_reason,
        "reasons": [],
        "raw_payload": {
            "evaluation_prediction": {
                "primary_research_object": "LLM",
                "negative_tier": "positive" if sampled_reason else "negative",
                "preference_labels": [sampled_reason] if sampled_reason else [],
            }
        },
    }


if __name__ == "__main__":
    unittest.main()
