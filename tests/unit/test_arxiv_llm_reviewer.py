from __future__ import annotations

import json
import shutil
import unittest
from concurrent.futures import Future
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from paper_analysis.domain.paper import Paper
from paper_analysis.cli.common import CliInputError
from paper_analysis.services.llm_recommendation_reviewer import (
    DEFAULT_TARGET_PROFILE,
    LlmRecommendationReviewRequest,
)
from paper_analysis.services.llm_recommendation_reviewer import _build_system_prompt
from paper_analysis.services.llm_recommendation_reviewer import LlmRecommendationReviewer


ROOT_DIR = Path(__file__).resolve().parents[2]


class FakeOpenRouterClient:
    resolved_chat_model = "deepseek/deepseek-v4-pro"

    def __init__(self) -> None:
        self.calls = 0
        self.messages: list[list[dict[str, object]]] = []

    def submit(self, messages: list[dict[str, object]], *, stream: bool = False) -> Future[dict[str, object]]:
        self.calls += 1
        self.messages.append(messages)
        future: Future[dict[str, object]] = Future()
        content_text = "\n".join(str(message.get("content", "")) for message in messages)
        if "recommended_papers" in content_text:
            content = {
                "recommended_reviews": [
                    {
                        "paper_id": "p1",
                        "verdict": "false_positive",
                        "confidence": 0.9,
                        "reason": "只是应用综述，没有推理效率方法。",
                    }
                ],
                "missed_recommendations": [],
            }
        elif "omitted_candidate_papers" in content_text and '"paper_id": "p2"' in content_text:
            content = {
                "recommended_reviews": [],
                "missed_recommendations": [
                    {
                        "paper_id": "p2",
                        "category": "系统与调度优化",
                        "confidence": 0.8,
                        "reason": "明确优化 LLM serving 调度和吞吐。",
                    }
                ],
            }
        elif "first_pass_missed" in content_text and '"paper_id": "p2"' in content_text:
            content = {
                "verified_missed_recommendations": [
                    {
                        "paper_id": "p2",
                        "category": "系统与调度优化",
                        "confidence": 0.8,
                        "reason": "明确优化 LLM serving 调度和吞吐。",
                    }
                ]
            }
        else:
            content = {
                "recommended_reviews": [],
                "missed_recommendations": [],
                "verified_missed_recommendations": [],
            }
        future.set_result(
            {
                "success": True,
                "content": json.dumps(content, ensure_ascii=False),
                "usage": None,
            }
        )
        return future


class InvalidVerdictOpenRouterClient(FakeOpenRouterClient):
    def submit(self, messages: list[dict[str, object]], *, stream: bool = False) -> Future[dict[str, object]]:
        self.messages.append(messages)
        future: Future[dict[str, object]] = Future()
        future.set_result(
            {
                "success": True,
                "content": json.dumps(
                    {
                        "recommended_reviews": [
                            {
                                "paper_id": "p1",
                                "verdict": "reject",
                                "confidence": 0.9,
                                "reason": "invalid",
                            }
                        ],
                        "missed_recommendations": [],
                    },
                    ensure_ascii=False,
                ),
                "usage": None,
            }
        )
        return future


class InvalidCategoryOpenRouterClient(FakeOpenRouterClient):
    def submit(self, messages: list[dict[str, object]], *, stream: bool = False) -> Future[dict[str, object]]:
        self.calls += 1
        self.messages.append(messages)
        future: Future[dict[str, object]] = Future()
        content_text = "\n".join(str(message.get("content", "")) for message in messages)
        if "recommended_papers" in content_text:
            content = {
                "recommended_reviews": [
                    {
                        "paper_id": "p1",
                        "verdict": "keep",
                        "confidence": 0.9,
                        "reason": "valid",
                    }
                ],
                "missed_recommendations": [],
            }
        else:
            content = {
                "recommended_reviews": [],
                "missed_recommendations": [
                    {
                        "paper_id": "p2",
                        "category": "安全隐私",
                        "confidence": 0.8,
                        "reason": "invalid",
                    }
                ],
            }
        future.set_result(
            {
                "success": True,
                "content": json.dumps(content, ensure_ascii=False),
                "usage": None,
            }
        )
        return future


class CloseTrackingOpenRouterClient(FakeOpenRouterClient):
    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    def close(self) -> None:
        self.closed = True


class LlmRecommendationReviewerTests(unittest.TestCase):
    def test_system_prompt_preserves_human_agent_and_decoding_preferences(self) -> None:
        prompt = _build_system_prompt(DEFAULT_TARGET_PROFILE)

        self.assertIn("大模型/生成模型/Agent 推理效率论文筛选器", prompt)
        self.assertIn("必须同时满足", prompt)
        self.assertIn("研究对象是 LLM、VLM、video diffusion / video generation、VLA", prompt)
        self.assertIn("video diffusion / video generation / VLA 的明确推理加速", prompt)
        self.assertIn("低延迟 rollout", prompt)
        self.assertIn("系统与调度优化", prompt)
        self.assertIn("speculative decoding", prompt)
        self.assertIn("draft model verification", prompt)
        self.assertIn("解码策略优化", prompt)
        self.assertIn("新模型结构天然更快", prompt)
        self.assertIn("QuantSpec", prompt)
        self.assertIn("MagicDec", prompt)
        self.assertIn("SmallKV", prompt)
        self.assertIn("ParetoQ", prompt)
        self.assertIn("Prepacking/Fiddler/MuxServe/AgServe", prompt)
        self.assertIn("泛化 test-time reasoning/search", prompt)
        self.assertIn("FinHarness / Agentic Separation Logic / Agents that Matter", prompt)
        self.assertIn("LogDx-CI", prompt)
        self.assertIn("纯扩散采样质量改进", prompt)
        self.assertIn("Industrial crash dynamics low-rank attention", prompt)

    def test_review_writes_false_positive_and_missed_artifacts(self) -> None:
        report_dir = ROOT_DIR / "artifacts" / "test-output" / "arxiv-llm-review-report"
        output_dir = ROOT_DIR / "artifacts" / "test-output" / "arxiv-llm-review-output"
        for path in [report_dir, output_dir]:
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True)

        (report_dir / "result.json").write_text(
            json.dumps(
                {
                    "source": "arXiv",
                    "analysis": {"analysis_count": 2, "recommended_count": 1},
                    "papers": [
                        {
                            "paper_id": "p1",
                            "title": "Energy Forecasting with LLM Agents",
                            "abstract": "A domain application survey.",
                            "sampled_reason": "系统与调度优化",
                            "reasons": ["推理加速子类：系统与调度优化"],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        candidates = [
            Paper(
                paper_id="p1",
                title="Energy Forecasting with LLM Agents",
                abstract="A domain application survey.",
                source="arxiv",
                venue="arXiv",
                authors=["Ada"],
                tags=["cs.CL"],
                organization="",
                published_at="2026-05-24",
            ),
            Paper(
                paper_id="p2",
                title="LLM Serving Scheduler",
                abstract="We improve LLM serving throughput and latency with a scheduler.",
                source="arxiv",
                venue="arXiv",
                authors=["Bob"],
                tags=["cs.DC"],
                organization="",
                published_at="2026-05-24",
            ),
        ]

        with patch(
            "paper_analysis.services.llm_recommendation_reviewer.serialize_papers",
            wraps=lambda papers: [
                {
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "abstract": paper.abstract,
                    "source": paper.source,
                    "venue": paper.venue,
                    "authors": " | ".join(paper.authors),
                    "tags": " | ".join(paper.tags),
                    "organization": paper.organization,
                    "published_at": paper.published_at,
                    "score": paper.score,
                    "reasons": paper.reasons,
                    "pdf_url": paper.pdf_url,
                    "sampled_reason": paper.sampled_reason,
                }
                for paper in papers
            ],
        ):
            result = LlmRecommendationReviewer(client=cast(Any, FakeOpenRouterClient())).review(
                LlmRecommendationReviewRequest(
                    source_name="arXiv",
                    content_date="2026-05/05-24",
                    report_dir=report_dir,
                    output_dir=output_dir,
                    candidate_batch_size=1,
                    candidate_papers=candidates,
                )
            )

        self.assertTrue(result.json_path.exists())
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(1, payload["false_positive_count"])
        self.assertEqual(1, payload["missed_count"])
        self.assertEqual("Energy Forecasting with LLM Agents", payload["false_positives"][0]["title"])
        self.assertEqual("LLM Serving Scheduler", payload["missed_recommendations"][0]["title"])
        self.assertIn("误推荐 1", result.stdout_path.read_text(encoding="utf-8"))

    def test_recommended_and_missed_verification_use_independent_contexts(self) -> None:
        report_dir, output_dir = _write_report_dirs("independent-context")
        candidates = [
            _paper("p1", "Recommended", "A recommended paper."),
            _paper("p2", "Omitted 1", "An omitted paper."),
            _paper("p3", "Omitted 2", "Another omitted paper."),
        ]
        client = FakeOpenRouterClient()

        LlmRecommendationReviewer(client=cast(Any, client)).review(
            LlmRecommendationReviewRequest(
                source_name="arXiv",
                content_date="2026-05/05-24",
                report_dir=report_dir,
                output_dir=output_dir,
                candidate_batch_size=10,
                candidate_papers=candidates,
            )
        )

        recommended_prompts = [
            "\n".join(str(message.get("content", "")) for message in messages)
            for messages in client.messages
            if "recommended_papers" in "\n".join(str(message.get("content", "")) for message in messages)
        ]
        verification_prompts = [
            "\n".join(str(message.get("content", "")) for message in messages)
            for messages in client.messages
            if "first_pass_missed" in "\n".join(str(message.get("content", "")) for message in messages)
        ]

        self.assertEqual(1, len(recommended_prompts))
        self.assertIn('"paper_id": "p1"', recommended_prompts[0])
        self.assertNotIn('"paper_id": "p2"', recommended_prompts[0])
        self.assertEqual(1, len(verification_prompts))
        self.assertIn('"paper_id": "p2"', verification_prompts[0])
        self.assertNotIn('"paper_id": "p3"', verification_prompts[0])

    def test_review_emits_batch_progress(self) -> None:
        report_dir = ROOT_DIR / "artifacts" / "test-output" / "arxiv-llm-review-progress-report"
        output_dir = ROOT_DIR / "artifacts" / "test-output" / "arxiv-llm-review-progress-output"
        for path in [report_dir, output_dir]:
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True)

        (report_dir / "result.json").write_text(
            json.dumps(
                {
                    "source": "arXiv",
                    "analysis": {"analysis_count": 3, "recommended_count": 1},
                    "papers": [
                        {
                            "paper_id": "p1",
                            "title": "Recommended",
                            "abstract": "A recommended paper.",
                            "sampled_reason": "系统与调度优化",
                            "reasons": ["推理加速子类：系统与调度优化"],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        candidates = [
            _paper("p1", "Recommended", "A recommended paper."),
            _paper("p2", "Omitted 1", "An omitted paper."),
            _paper("p3", "Omitted 2", "Another omitted paper."),
        ]
        progress_lines: list[str] = []

        LlmRecommendationReviewer(client=cast(Any, FakeOpenRouterClient())).review(
            LlmRecommendationReviewRequest(
                source_name="arXiv",
                content_date="2026-05/05-24",
                report_dir=report_dir,
                output_dir=output_dir,
                candidate_batch_size=1,
                candidate_papers=candidates,
                progress=progress_lines.append,
            )
        )

        self.assertIn("[blue-team] reviewing recommended papers independently count=1...", progress_lines)
        self.assertIn("[blue-team] recommended paper reviewed p1", progress_lines)
        self.assertIn("[blue-team] reviewing omitted batch 1/2, size=1...", progress_lines)
        self.assertIn("[blue-team] reviewing omitted batch 2/2, size=1...", progress_lines)
        self.assertTrue(any(line.startswith("[blue-team] done ") for line in progress_lines))

    def test_review_closes_owned_openrouter_client(self) -> None:
        report_dir, output_dir = _write_report_dirs("owned-client-close")
        candidates = [
            _paper("p1", "Recommended", "A recommended paper."),
            _paper("p2", "Omitted", "An omitted paper."),
        ]
        fake_client = CloseTrackingOpenRouterClient()

        with patch(
            "paper_analysis.services.llm_recommendation_reviewer.OpenRouterClient",
            return_value=fake_client,
        ):
            LlmRecommendationReviewer().review(
                LlmRecommendationReviewRequest(
                    source_name="arXiv",
                    content_date="2026-05/05-24",
                    report_dir=report_dir,
                    output_dir=output_dir,
                    candidate_batch_size=1,
                    candidate_papers=candidates,
                )
            )

        self.assertTrue(fake_client.closed)

    def test_review_rejects_invalid_recommended_verdict(self) -> None:
        report_dir, output_dir = _write_report_dirs("invalid-verdict")
        candidates = [_paper("p1", "Recommended", "A recommended paper.")]

        with self.assertRaisesRegex(CliInputError, "verdict 非法"):
            LlmRecommendationReviewer(client=cast(Any, InvalidVerdictOpenRouterClient())).review(
                LlmRecommendationReviewRequest(
                    source_name="arXiv",
                    content_date="2026-05/05-24",
                    report_dir=report_dir,
                    output_dir=output_dir,
                    candidate_papers=candidates,
                )
            )

    def test_review_rejects_invalid_missed_category(self) -> None:
        report_dir, output_dir = _write_report_dirs("invalid-category")
        candidates = [
            _paper("p1", "Recommended", "A recommended paper."),
            _paper("p2", "Omitted", "An omitted paper."),
        ]

        with self.assertRaisesRegex(CliInputError, "category 非法"):
            LlmRecommendationReviewer(client=cast(Any, InvalidCategoryOpenRouterClient())).review(
                LlmRecommendationReviewRequest(
                    source_name="arXiv",
                    content_date="2026-05/05-24",
                    report_dir=report_dir,
                    output_dir=output_dir,
                    candidate_papers=candidates,
                )
            )


if __name__ == "__main__":
    unittest.main()


def _paper(paper_id: str, title: str, abstract: str) -> Paper:
    return Paper(
        paper_id=paper_id,
        title=title,
        abstract=abstract,
        source="arxiv",
        venue="arXiv",
        authors=["Ada"],
        tags=["cs.CL"],
        organization="",
        published_at="2026-05-24",
    )


def _write_report_dirs(suffix: str) -> tuple[Path, Path]:
    report_dir = ROOT_DIR / "artifacts" / "test-output" / f"arxiv-llm-review-{suffix}-report"
    output_dir = ROOT_DIR / "artifacts" / "test-output" / f"arxiv-llm-review-{suffix}-output"
    for path in [report_dir, output_dir]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
    (report_dir / "result.json").write_text(
        json.dumps(
            {
                "source": "arXiv",
                "analysis": {"analysis_count": 1, "recommended_count": 1},
                "papers": [
                    {
                        "paper_id": "p1",
                        "title": "Recommended",
                        "abstract": "A recommended paper.",
                        "sampled_reason": "系统与调度优化",
                        "reasons": ["推理加速子类：系统与调度优化"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return report_dir, output_dir
