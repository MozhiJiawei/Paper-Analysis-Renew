from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from paper_analysis.domain.paper import Paper
from paper_analysis.services.arxiv_dataset_import import (
    _count_boundary_negative_annotations,
    build_and_import_arxiv_dataset_samples,
    build_arxiv_dataset_import_payload,
)


class ArxivDatasetImportTests(unittest.TestCase):
    def test_payload_keeps_recommender_and_blue_team_decisions_together(self) -> None:
        recommended = _paper(
            "2605.00001",
            "Speculative Decoding for LLM Serving",
            sampled_reason="解码策略优化",
            reasons=["推理加速子类：解码策略优化"],
        )
        false_positive = _paper(
            "2605.00002",
            "Training Data Scheduling for LLMs",
            sampled_reason="系统与调度优化",
            reasons=["推理加速子类：系统与调度优化"],
        )
        missed = _paper("2605.00003", "KV Cache Compression for Agents")
        boundary = _paper("2605.00004", "Efficient Training Benchmark")

        payload = build_arxiv_dataset_import_payload(
            content_date="2026-05/05-25",
            candidate_papers=[recommended, false_positive, missed, boundary],
            recommended_papers=[recommended, false_positive],
            review_payload={
                "recommended_reviews": [
                    {
                        "paper_id": "2605.00001",
                        "verdict": "keep",
                        "confidence": 0.9,
                        "reason": "明确是推理加速。",
                    },
                    {
                        "paper_id": "2605.00002",
                        "verdict": "false_positive",
                        "confidence": 0.95,
                        "reason": "训练调度，不是推理服务。",
                    },
                ],
                "missed_recommendations": [
                    {
                        "paper_id": "2605.00003",
                        "category": "上下文与缓存优化",
                        "confidence": 0.9,
                        "reason": "漏掉了 KV cache 优化。",
                    }
                ],
            },
            client=FakeBoundaryClient(
                {
                    "boundary_negatives": [
                        {
                            "paper_id": "2605.00004",
                            "reason": "有 efficient 但核心是训练 benchmark。",
                        }
                    ]
                }
            ),
        )

        records = {record["paper_id"]: record for record in payload["records"]}
        annotations = {
            annotation["paper_id"]: annotation for annotation in payload["annotations_ai"]
        }

        false_positive_notes = str(records["2605.00002"]["notes"])
        missed_notes = str(records["2605.00003"]["notes"])
        boundary_notes = str(records["2605.00004"]["notes"])

        self.assertIn("AI 推荐算法结论：推荐为正样本", false_positive_notes)
        self.assertIn("蓝军审阅结论：误推荐，应作为负样本", false_positive_notes)
        self.assertEqual("negative", annotations["2605.00002"]["negative_tier"])
        self.assertIn("AI 推荐算法结论：未推荐", missed_notes)
        self.assertIn("蓝军审阅结论：漏推荐，应作为正样本", missed_notes)
        self.assertEqual(["上下文与缓存优化"], annotations["2605.00003"]["preference_labels"])
        self.assertIn("导入来源：ds-v4 边界负例抽样", boundary_notes)
        self.assertEqual("negative", annotations["2605.00004"]["negative_tier"])
        self.assertEqual(
            1,
            _count_boundary_negative_annotations(list(annotations.values())),
        )

    def test_boundary_negative_count_balances_positive_and_negative_labels(self) -> None:
        positive = _paper("p-positive", "LLM Inference Acceleration", sampled_reason="模型压缩")
        false_positive = _paper(
            "p-false",
            "LLM Training Optimization",
            sampled_reason="系统与调度优化",
        )
        boundary_one = _paper("p-boundary-1", "Efficient Dataset for Training")
        boundary_two = _paper("p-boundary-2", "Routing Benchmark for Agents")

        payload = build_arxiv_dataset_import_payload(
            content_date="2026-05/05-25",
            candidate_papers=[positive, false_positive, boundary_one, boundary_two],
            recommended_papers=[positive, false_positive],
            review_payload={
                "recommended_reviews": [
                    {"paper_id": "p-positive", "verdict": "keep", "reason": "保留"},
                    {"paper_id": "p-false", "verdict": "false_positive", "reason": "误推荐"},
                ],
                "missed_recommendations": [],
            },
            client=FakeBoundaryClient(
                {
                    "boundary_negatives": [
                        {"paper_id": "p-boundary-1", "reason": "边界负例"},
                        {"paper_id": "p-boundary-2", "reason": "多余负例"},
                    ]
                }
            ),
        )

        annotations = payload["annotations_ai"]
        positives = [item for item in annotations if item["negative_tier"] == "positive"]
        negatives = [item for item in annotations if item["negative_tier"] == "negative"]

        self.assertEqual(1, len(positives))
        self.assertEqual(1, len(negatives))
        self.assertNotIn("p-boundary-1", {item["paper_id"] for item in annotations})

    def test_boundary_sampler_failure_does_not_block_positive_payload(self) -> None:
        positive = _paper("p-positive", "LLM Inference Acceleration", sampled_reason="模型压缩")
        missed = _paper("p-missed", "Agent Routing Optimization")
        payload = build_arxiv_dataset_import_payload(
            content_date="2026-05/05-26",
            candidate_papers=[positive, missed, _paper("p-boundary", "Training Benchmark")],
            recommended_papers=[positive],
            review_payload={
                "recommended_reviews": [
                    {"paper_id": "p-positive", "verdict": "keep", "reason": "保留"},
                ],
                "missed_recommendations": [
                    {
                        "paper_id": "p-missed",
                        "category": "系统与调度优化",
                        "reason": "Agent 路由优化。",
                    }
                ],
            },
            client=FailingBoundaryClient(),
        )

        annotations = {item["paper_id"]: item for item in payload["annotations_ai"]}

        self.assertIn("boundary_sampling_error", payload)
        self.assertEqual("positive", annotations["p-positive"]["negative_tier"])
        self.assertEqual("positive", annotations["p-missed"]["negative_tier"])
        self.assertNotIn("p-boundary", annotations)

    def test_build_and_import_writes_payload_through_dataset_api(self) -> None:
        recommended = _paper("p-import-positive", "LLM Inference", sampled_reason="模型压缩")
        false_positive = _paper(
            "p-import-negative",
            "LLM Training Schedule",
            sampled_reason="系统与调度优化",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review_json = root / "review.json"
            benchmark_root = root / "benchmark"
            output_dir = root / "out"
            review_json.write_text(
                json.dumps(
                    {
                        "recommended_reviews": [
                            {"paper_id": "p-import-positive", "verdict": "keep"},
                            {
                                "paper_id": "p-import-negative",
                                "verdict": "false_positive",
                                "reason": "训练调度。",
                            },
                        ],
                        "missed_recommendations": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = build_and_import_arxiv_dataset_samples(
                content_date="2026-05/05-25",
                candidate_papers=[recommended, false_positive],
                recommended_papers=[recommended, false_positive],
                review_json_path=review_json,
                output_dir=output_dir,
                benchmark_root=benchmark_root,
                client=FakeBoundaryClient({"boundary_negatives": []}),
            )

            records_path = benchmark_root / "records.jsonl"
            annotations_path = benchmark_root / "annotations-ai.jsonl"

            self.assertEqual("ok", result.import_status)
            self.assertTrue(result.payload_path.exists())
            self.assertIn("p-import-positive", records_path.read_text(encoding="utf-8"))
            self.assertIn(
                "p-import-negative",
                annotations_path.read_text(encoding="utf-8"),
            )

    def test_build_and_import_closes_owned_openrouter_client(self) -> None:
        recommended = _paper("p-close-positive", "LLM Inference", sampled_reason="模型压缩")
        fake_client = CloseTrackingBoundaryClient({"boundary_negatives": []})
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review_json = root / "review.json"
            output_dir = root / "out"
            dataset_repo = root / "dataset"
            (dataset_repo / "paper_analysis_dataset").mkdir(parents=True)
            review_json.write_text(
                json.dumps(
                    {
                        "recommended_reviews": [
                            {"paper_id": "p-close-positive", "verdict": "keep"}
                        ],
                        "missed_recommendations": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch(
                    "paper_analysis.services.arxiv_dataset_import.OpenRouterClient",
                    return_value=fake_client,
                ),
                patch(
                    "paper_analysis.services.arxiv_dataset_import._run_dataset_import",
                    return_value=subprocess.CompletedProcess(
                        args=[],
                        returncode=0,
                        stdout="[OK] imported",
                        stderr="",
                    ),
                ),
            ):
                build_and_import_arxiv_dataset_samples(
                    content_date="2026-05/05-25",
                    candidate_papers=[recommended],
                    recommended_papers=[recommended],
                    review_json_path=review_json,
                    output_dir=output_dir,
                    dataset_repo_dir=dataset_repo,
                )

        self.assertTrue(fake_client.closed)


@dataclass(slots=True)
class FakeFuture:
    payload: dict[str, object]

    def result(self) -> dict[str, object]:
        return {"success": True, "content": json.dumps(self.payload, ensure_ascii=False)}


@dataclass(slots=True)
class FakeBoundaryClient:
    payload: dict[str, object]
    resolved_chat_model: str = "deepseek/deepseek-v4-pro"

    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> FakeFuture:
        return FakeFuture(self.payload)


class FailingBoundaryClient:
    resolved_chat_model = "fake-failing-boundary"

    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> FailingFuture:
        _ = (messages, stream)
        return FailingFuture()


class FailingFuture:
    def result(self) -> dict[str, object]:
        return {"success": False, "error": "temporary ds-v4 parse failure"}


@dataclass(slots=True)
class CloseTrackingBoundaryClient(FakeBoundaryClient):
    closed: bool = False

    def close(self) -> None:
        self.closed = True


def _paper(
    paper_id: str,
    title: str,
    *,
    sampled_reason: str = "",
    reasons: list[str] | None = None,
) -> Paper:
    return Paper(
        paper_id=paper_id,
        title=title,
        abstract=(
            "This paper studies efficient inference, cache, scheduling, or benchmark "
            "behavior for large models."
        ),
        source="arxiv",
        venue="arXiv",
        authors=["Alice"],
        tags=["cs.AI"],
        organization="",
        published_at="2026-05-25",
        sampled_reason=sampled_reason,
        reasons=reasons or [],
        pdf_url=f"https://arxiv.org/pdf/{paper_id}",
        raw_payload={
            "evaluation_prediction": {
                "primary_research_object": "LLM",
                "negative_tier": "positive" if sampled_reason else "negative",
                "preference_labels": [sampled_reason] if sampled_reason else [],
            }
        },
    )


if __name__ == "__main__":
    unittest.main()
