from __future__ import annotations

import unittest

from paper_analysis.api.evaluation_predictor import EvaluationPredictor
from paper_analysis.api.evaluation_protocol import (
    EvaluationPaper,
    EvaluationPrediction,
    EvaluationProtocolError,
    aggregate_primary_research_object,
)


class EvaluationApiUnitTests(unittest.TestCase):
    def test_predictor_returns_single_positive_label_for_speculative_decoding(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-1",
            title="Speculative Decoding for Efficient LLM Inference",
            abstract="This speculative decoding method improves draft acceptance rate.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["speculative decoding"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["解码策略优化"], prediction.preference_labels)
        self.assertEqual("LLM", prediction.primary_research_object)

    def test_predictor_prioritizes_vlm_over_language_model_keywords(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-vlm-1",
            title="A Vision-Language Model for Image Reasoning with Language Model Distillation",
            abstract="This multimodal system aligns visual tokens with a language model backbone.",
            abstract_zh="这项多模态方法将视觉 token 与语言模型骨干对齐。",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["multimodal", "vision-language"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("多模态 / VLM", prediction.primary_research_object)

    def test_predictor_returns_diffusion_for_denoising_paper(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-diffusion-1",
            title="DiT Denoising for Text-to-Image Generation",
            abstract="We study diffusion denoising with a DiT backbone for text-to-image generation.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["diffusion", "DiT"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("Diffusion / 生成模型", prediction.primary_research_object)

    def test_predictor_does_not_match_dit_inside_traditional(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-llm-traditional",
            title="QJL: 1-Bit Quantized JL Transform for KV Cache Quantization with Zero Overhead",
            abstract="Serving LLMs requires substantial memory due to KV cache growth. However, traditional quantization methods face accuracy bottlenecks in long-context inference.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["large language model", "KV cache", "quantization"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("LLM", prediction.primary_research_object)

    def test_predictor_does_not_treat_context_denoising_as_diffusion(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-context-denoising",
            title="Context Denoising Training for Long-Context LLMs",
            abstract="We improve large language model inference with context denoising training and KV cache aware long-context optimization.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["LLM", "long-context", "KV cache"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("LLM", prediction.primary_research_object)

    def test_predictor_falls_back_to_general_ml_for_other_research_objects(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-structure-only",
            title="Retrieval-Augmented Ranking for Web Search",
            abstract="We study retrieval and ranking signals for production search systems.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["retrieval", "ranking"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("通用机器学习", prediction.primary_research_object)
        self.assertEqual("negative", prediction.negative_tier)
        self.assertEqual([], prediction.preference_labels)
        self.assertIn("五个偏好标签", prediction.notes)

    def test_research_object_aggregation_maps_public_labels_to_four_buckets(self) -> None:
        self.assertEqual("LLM", aggregate_primary_research_object("LLM"))
        self.assertEqual("VLM", aggregate_primary_research_object("多模态 / VLM"))
        self.assertEqual("Diffusion", aggregate_primary_research_object("Diffusion / 生成模型"))
        self.assertEqual("其他", aggregate_primary_research_object("评测 / Benchmark / 数据集"))

    def test_negative_prediction_clears_preference_labels(self) -> None:
        prediction = EvaluationPrediction(
            primary_research_object="评测 / Benchmark / 数据集",
            preference_labels=[],
            negative_tier="negative",
            evidence_spans={"negative": ["benchmark only"]},
            notes="negative",
        )

        self.assertEqual([], prediction.preference_labels)

    def test_positive_prediction_rejects_multiple_labels(self) -> None:
        with self.assertRaises(EvaluationProtocolError):
            EvaluationPrediction(
                primary_research_object="LLM",
                preference_labels=["解码策略优化", "系统与调度优化"],
                negative_tier="positive",
                evidence_spans={"general": ["bad"]},
            )

    def test_protocol_rejects_removed_structure_label(self) -> None:
        with self.assertRaises(EvaluationProtocolError):
            EvaluationPrediction(
                primary_research_object="LLM",
                preference_labels=["模型结构侧推理优化"],
                negative_tier="positive",
                evidence_spans={"模型结构侧推理优化": ["bad"]},
            )


if __name__ == "__main__":
    unittest.main()
