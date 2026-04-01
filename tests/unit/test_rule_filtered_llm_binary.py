from __future__ import annotations

import json
import unittest

from paper_analysis.api.evaluation_protocol import EvaluationPaper, EvaluationPrediction
from paper_analysis.evaluation.routes.rule_filtered_llm_binary import (
    DoubaoBinaryJudge,
    RuleFilteredLlmBinaryRoute,
    _parse_prediction_payload,
)
from paper_analysis.utils.doubao_client import DoubaoClient


def _sample_positive_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-positive",
        title="Speculative Decoding with Adaptive KV Cache for LLM Serving",
        abstract="We improve LLM serving latency with speculative decoding and KV cache management.",
        authors=["Alice"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["llm", "speculative decoding", "kv cache"],
    )


def _sample_negative_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-negative",
        title="A Survey of Bird Species Recognition in Wetlands",
        abstract="We benchmark image classification models for wetland bird species recognition.",
        authors=["Bob"],
        venue="CVPR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["bird recognition", "survey"],
    )


def _sample_substring_negative_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-substring-negative",
        title="Recovering Neural Codes with Information Preservation",
        abstract="We study representation recovery and preservation objectives in generic neural coding tasks.",
        authors=["Dave"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["representation", "preservation"],
    )


def _sample_ambiguous_candidate_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-ambiguous",
        title="Improving Large Language Model Test-Time Reasoning with Better Search",
        abstract="We study LLM reasoning and search strategies for harder tasks, focusing on answer quality rather than explicit systems optimization.",
        authors=["Eve"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["llm", "reasoning", "search"],
    )


def _sample_judge_negative_candidate_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-judge-negative",
        title="Large Language Model Search for Hard Reasoning Tasks",
        abstract="We study search-based reasoning strategies for large language models, focusing on answer quality and not systems efficiency.",
        authors=["Uma"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["llm", "reasoning", "search"],
    )


def _sample_fairness_sparsity_negative_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-fairness-negative",
        title="Toward Unifying Group Fairness Evaluation from a Sparsity Perspective",
        abstract="We study fairness evaluation through sparsity analysis for group fairness assessment.",
        authors=["Ivy"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["fairness", "evaluation", "sparsity"],
    )


def _sample_strong_positive_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-strong-positive",
        title="SmallKV: KV Cache Compression for Efficient LLM Inference",
        abstract="We compress the KV cache to reduce memory and improve latency for large language model serving.",
        authors=["Frank"],
        venue="NeurIPS 2025",
        year=2025,
        source="conference",
        source_path="tests.json",
        keywords=["llm", "kv cache", "compression", "latency"],
    )


def _sample_diffusion_positive_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-diffusion-positive",
        title="PersonalQ: Select, Quantize, and Serve Personalized Diffusion Models for Efficient Inference",
        abstract="We quantize and serve diffusion models for efficient inference with better memory efficiency.",
        authors=["Grace"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["diffusion", "quantization", "efficient inference", "serving"],
    )


def _sample_layer_pruning_positive_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-layer-pruning-positive",
        title="Reassessing Layer Pruning in LLMs: New Insights and Methods",
        abstract="We revisit layer pruning for efficient LLM inference and memory reduction.",
        authors=["Heidi"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["llm", "layer pruning", "efficient inference"],
    )


def _sample_system_runtime_positive_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-system-runtime-positive",
        title="A Runtime Scheduler for Multi-Tenant LLM Serving",
        abstract="We design a scheduler and routing strategy for multi-tenant LLM serving.",
        authors=["Jack"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["llm", "scheduler", "serving", "routing"],
    )


def _sample_positive_bias_judge_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-positive-bias-judge",
        title="Adaptive Architectures Under Tight Budgets",
        abstract="We study layer reconfiguration and hybrid architecture choices under tight compute budgets.",
        authors=["Luna"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["layer reconfiguration", "hybrid architecture"],
    )


def _sample_kernel_positive_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-kernel-positive",
        title="FlashDecoding Kernel Fusion for Faster LLM Inference",
        abstract="We propose a fused attention kernel with Tensor Core optimization for faster LLM decoding.",
        authors=["Mina"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["llm", "flash decoding", "kernel fusion", "tensor core"],
    )


def _sample_structure_positive_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-structure-positive",
        title="Dynamic Depth Routing for Efficient Mixture-of-Experts Inference",
        abstract="We adapt depth and expert selection at inference time to reduce latency for large language models.",
        authors=["Nora"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["llm", "dynamic depth", "mixture-of-experts", "expert selection"],
    )


def _sample_weak_kernel_positive_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-weak-kernel-positive",
        title="Triton Kernels for Flash Attention",
        abstract="We optimize attention with a Triton kernel and fused operator design.",
        authors=["Owen"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["triton", "flash attention", "fused operator"],
    )


def _sample_generic_efficiency_positive_paper() -> EvaluationPaper:
    return EvaluationPaper(
        paper_id="paper-generic-efficiency-positive",
        title="Accelerating Long-Context Large Language Model Inference",
        abstract="We improve inference efficiency and memory usage for large language models in long-context settings.",
        authors=["Pia"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=["large language model", "inference efficiency", "memory"],
    )


class _ReadyJudge:
    def is_available(self) -> bool:
        return True

    def judge(
        self,
        paper: EvaluationPaper,
        *,
        candidate_labels: list[str],
        matched_keywords: list[str],
    ) -> EvaluationPrediction:
        return EvaluationPrediction(
            primary_research_object="LLM",
            preference_labels=[candidate_labels[0] if candidate_labels else "解码策略优化"],
            negative_tier="positive",
            evidence_spans={
                "general": [paper.title],
                candidate_labels[0] if candidate_labels else "解码策略优化": matched_keywords[:2]
                or [paper.title],
            },
            notes="fake judge positive",
        )


class _UnavailableJudge:
    def is_available(self) -> bool:
        return False

    def judge(
        self,
        paper: EvaluationPaper,
        *,
        candidate_labels: list[str],
        matched_keywords: list[str],
    ) -> EvaluationPrediction:
        raise AssertionError("judge should not be called when unavailable")


class _ExplodingJudge:
    def is_available(self) -> bool:
        return True

    def judge(
        self,
        paper: EvaluationPaper,
        *,
        candidate_labels: list[str],
        matched_keywords: list[str],
    ) -> EvaluationPrediction:
        raise RuntimeError("llm unavailable")


class _NegativeJudge:
    def is_available(self) -> bool:
        return True

    def judge(
        self,
        paper: EvaluationPaper,
        *,
        candidate_labels: list[str],
        matched_keywords: list[str],
    ) -> EvaluationPrediction:
        return EvaluationPrediction(
            primary_research_object="LLM",
            preference_labels=[],
            negative_tier="negative",
            evidence_spans={"negative": [paper.title]},
            notes="fallback negative",
        )


class RuleFilteredLlmBinaryRouteUnitTests(unittest.TestCase):
    def test_doubao_judge_parses_json_payload(self) -> None:
        client = DoubaoClient(
            runner=lambda messages: {
                "success": True,
                "content": json.dumps(
                    {
                        "negative_tier": "positive",
                        "primary_research_object": "LLM",
                        "preference_label": "解码策略优化",
                        "evidence": ["speculative decoding improves latency"],
                        "notes": "fake doubao response",
                    },
                    ensure_ascii=False,
                ),
            }
        )
        judge = DoubaoBinaryJudge(client=client)

        prediction = judge.judge(
            _sample_positive_paper(),
            candidate_labels=["解码策略优化"],
            matched_keywords=["speculative decoding"],
        )

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["解码策略优化"], prediction.preference_labels)

    def test_parse_prediction_payload_accepts_preference_labels_array(self) -> None:
        prediction = _parse_prediction_payload(
            '{"negative_tier":"positive","primary_research_object":"LLM",'
            '"preference_labels":["模型压缩"],'
            '"evidence":["quantization reduces memory"],'
            '"notes":"ok"}',
            paper=_sample_positive_paper(),
            candidate_labels=[],
        )

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["模型压缩"], prediction.preference_labels)

    def test_parse_prediction_payload_accepts_event_stream_agent_message(self) -> None:
        prediction = _parse_prediction_payload(
            '\n'.join(
                [
                    '{"type":"event","item":{"type":"thinking","text":"...ignored..."}}',
                    '{"type":"event","item":{"type":"agent_message","text":"{\\"negative_tier\\":\\"positive\\",\\"primary_research_object\\":\\"LLM\\",\\"preference_label\\":\\"解码策略优化\\",\\"evidence\\":[\\"speculative decoding\\"],\\"notes\\":\\"ok\\"}"}}',
                ]
            ),
            paper=_sample_positive_paper(),
            candidate_labels=["解码策略优化"],
        )

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["解码策略优化"], prediction.preference_labels)

    def test_prepare_requires_available_judge(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_UnavailableJudge())

        with self.assertRaisesRegex(Exception, "不可用"):
            route.prepare()

    def test_route_short_circuits_obvious_negative_without_calling_judge(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ReadyJudge())
        route.prepare()

        prediction = route.predict_many([_sample_negative_paper()])[0].prediction

        self.assertEqual("negative", prediction.negative_tier)
        self.assertEqual([], prediction.preference_labels)
        self.assertTrue(
            "规则预过滤未命中" in prediction.notes or "规则预过滤命中负向主题" in prediction.notes
        )

    def test_route_does_not_trigger_false_positive_on_substring_match(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ReadyJudge())
        route.prepare()

        prediction = route.predict_many([_sample_substring_negative_paper()])[0].prediction

        self.assertEqual("negative", prediction.negative_tier)

    def test_route_negative_guard_blocks_fairness_sparsity_false_positive(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ReadyJudge())
        route.prepare()

        prediction = route.predict_many([_sample_fairness_sparsity_negative_paper()])[0].prediction

        self.assertEqual("negative", prediction.negative_tier)
        self.assertIn("负向主题", prediction.notes)

    def test_route_calls_judge_for_candidate_paper(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ReadyJudge())
        route.prepare()

        prediction = route.predict_many([_sample_ambiguous_candidate_paper()])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(1, len(prediction.preference_labels))

    def test_route_directly_returns_positive_for_strong_inference_optimization_paper(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ExplodingJudge())
        route.prepare()

        prediction = route.predict_many([_sample_strong_positive_paper()])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["上下文与缓存优化"], prediction.preference_labels)
        self.assertIn("规则直判命中高置信", prediction.notes)

    def test_route_directly_returns_positive_for_diffusion_inference_optimization(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ExplodingJudge())
        route.prepare()

        prediction = route.predict_many([_sample_diffusion_positive_paper()])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["模型压缩"], prediction.preference_labels)

    def test_route_directly_returns_positive_for_layer_pruning_llm_paper(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ExplodingJudge())
        route.prepare()

        prediction = route.predict_many([_sample_layer_pruning_positive_paper()])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["模型压缩"], prediction.preference_labels)

    def test_route_directly_returns_positive_for_system_runtime_paper(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ExplodingJudge())
        route.prepare()

        prediction = route.predict_many([_sample_system_runtime_positive_paper()])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["系统与调度优化"], prediction.preference_labels)

    def test_route_directly_returns_positive_for_kernel_optimization_paper(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ExplodingJudge())
        route.prepare()

        prediction = route.predict_many([_sample_kernel_positive_paper()])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["算子与内核优化"], prediction.preference_labels)

    def test_route_directly_returns_positive_for_structure_optimization_paper(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ExplodingJudge())
        route.prepare()

        prediction = route.predict_many([_sample_structure_positive_paper()])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["模型结构侧推理优化"], prediction.preference_labels)

    def test_route_directly_returns_positive_for_weak_kernel_optimization_paper(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ExplodingJudge())
        route.prepare()

        prediction = route.predict_many([_sample_weak_kernel_positive_paper()])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["算子与内核优化"], prediction.preference_labels)

    def test_route_uses_efficiency_fallback_for_generic_foundation_model_positive(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ExplodingJudge())
        route.prepare()

        prediction = route.predict_many([_sample_generic_efficiency_positive_paper()])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)
        self.assertTrue(prediction.preference_labels)

    def test_route_falls_back_to_negative_when_judge_errors(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ExplodingJudge())
        route.prepare()

        prediction = route.predict_many([_sample_judge_negative_candidate_paper()])[0].prediction

        self.assertEqual("negative", prediction.negative_tier)
        self.assertIn("LLM 裁决失败", prediction.notes)

    def test_route_keeps_structure_candidate_positive_when_judge_returns_negative(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_NegativeJudge())
        route.prepare()

        prediction = route.predict_many([_sample_positive_bias_judge_paper()])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["模型结构侧推理优化"], prediction.preference_labels)
        self.assertIn("规则直判命中高置信", prediction.notes)

    def test_route_keeps_structure_candidate_positive_when_judge_errors(self) -> None:
        route = RuleFilteredLlmBinaryRoute(judge=_ExplodingJudge())
        route.prepare()

        prediction = route.predict_many([_sample_positive_bias_judge_paper()])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["模型结构侧推理优化"], prediction.preference_labels)
        self.assertIn("规则直判命中高置信", prediction.notes)

if __name__ == "__main__":
    unittest.main()
