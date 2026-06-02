"""Generic LLM review for recommendation quality artifacts."""

from __future__ import annotations

import json
import re
from concurrent.futures import as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from paper_analysis.cli.common import CliInputError
from paper_analysis.services.report_writer import serialize_papers
from paper_analysis.utils.openrouter_client import DEFAULT_CHAT_MODEL, OpenRouterClient

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from paper_analysis.domain.paper import Paper


DEFAULT_REVIEW_CATEGORIES = [
    "上下文与缓存优化",
    "模型压缩",
    "解码策略优化",
    "系统与调度优化",
    "算子与内核优化",
]
RECOMMENDED_VERDICTS = {"keep", "false_positive", "borderline"}
DEFAULT_REVIEW_CONCURRENCY = 10

DEFAULT_TARGET_PROFILE = """目标偏好是“模型后训练与推理阶段的效率优化”相关论文：
你是一个“大模型/生成模型/Agent 推理效率论文筛选器”。判为正例必须同时满足：
1. 研究对象是 LLM、VLM、video diffusion / video generation、VLA、LLM/Agent serving，或直接作用于这些模型推理路径的后训练效率方法；
2. 核心贡献直接改变推理阶段的执行路径、KV/context/cache、生成解码、模型压缩部署、算子内核、serving 调度，或 Agent runtime；
3. 摘要明确出现 latency、throughput、memory、cost、token/API calls、prefill/decode speed、GPU utilization、SLO 等效率目标或结果。
只要任一条件不满足，默认判为负例。

正例方向：
- 解码策略优化：收 LLM generation decoding 和 diffusion language/video generation 的推理期解码/denoising 加速，例如 speculative decoding、self-speculative decoding、draft model verification、parallel token/block decoding、long-context decoding serving、few-step / fewer-step generation。正例锚点：QuantSpec、MagicDec。
- 上下文与缓存优化：收 LLM/VLM/video diffusion/VLA 的 KV cache/context cache 压缩、驱逐、复用、稀疏化、补偿或长上下文/长视频推理缓存优化。正例锚点：SmallKV、Inference-Time Hyper-Scaling with KV Cache Compression。
- 模型压缩：收 LLM/VLM/video diffusion/VLA 推理部署中的后训练量化、剪枝、蒸馏、token merging、极低比特压缩，并且必须指向推理内存/速度/部署收益。正例锚点：ParetoQ。
- 算子与内核优化：只收服务于目标模型推理的 attention/operator/kernel/compiler/runtime 优化；如果论文主任务是工业仿真、科学计算、视觉任务本身，默认不是正例。
- 系统与调度优化：只收 LLM serving 或 Agent serving 的 batch/prefill/decode scheduling、placement、resource orchestration、CPU-GPU orchestration、multi-model/multi-tenant serving、session-aware model routing/KV reuse。正例锚点：Prepacking、Fiddler、MuxServe、AgServe。

硬排除：
- 泛化 test-time reasoning/search/scaling、pass@K、Best-of-N、debate、judge/reward、采样预算准确率权衡，不等于解码优化；除非摘要明确优化 LLM token generation decode path 或 serving latency/cost。
- 垂直场景 agent 应用、安全线束、地理定位、程序规范合成、游戏/机器人/金融/医学 agent、agent benchmark/evaluation，不等于 Agent serving/runtime 优化。
- 通用 RAG、文档检索、reranking、搜索增强、知识图谱应用，不等于上下文/缓存优化；除非核心是 LLM runtime 的上下文选择/压缩/缓存复用。
- 非 LLM/Agent 的一般视觉、3D、工业仿真、科学计算、产品预测默认负例；但 video diffusion / video generation / VLA 的明确推理加速、KV/cache、token pruning/merging、蒸馏、低延迟 rollout、算子内核或服务优化算正例。
- 纯扩散采样质量改进、纯视觉生成效果改进、纯机器人任务成功率改进默认负例；除非摘要明确给出推理步数、延迟、吞吐、显存、FLOPs 或 deployment/serving 收益。
- 预训练、训练数据、训练算法、纯 fine-tuning、纯 benchmark/evaluation、纯应用、纯安全/隐私/医学/能源/网络场景默认负例。
- “新模型结构天然更快/更便宜”“能力更强所以成本下降”“训练更高效”默认负例。

Few-shot 正例：
- QuantSpec: self-speculative decoding + hierarchical quantized KV cache，提升 long-context LLM decoding speed/memory -> 解码策略优化 / 上下文与缓存优化。
- MagicDec: speculative decoding for long-context generation serving，突破 latency-throughput tradeoff，2.51x speedup -> 解码策略优化 / 系统与调度优化。
- SmallKV: small-model assisted KV cache compression for efficient LLM inference，1.75-2.56x throughput -> 上下文与缓存优化。
- ParetoQ: extremely low-bit LLM quantization，降低模型内存并具备 speedup 潜力 -> 模型压缩。
- Prepacking/Fiddler/MuxServe/AgServe: LLM/Agent serving 的 prefilling、CPU-GPU orchestration、multi-LLM multiplexing、session-aware routing/KV reuse -> 系统与调度优化。

Few-shot 负例：
- Uncertainty-Aware Budget Allocation / CPPO / Collaborative Parallel Thinking: test-time reasoning 或 pass@K/search 预算优化，提升准确率但不改变 LLM decoding runtime -> 负例。
- FinHarness / Agentic Separation Logic / Agents that Matter: 垂直 agent 安全、程序规范、归因评估或 agent 应用优化，不是 Agent serving/runtime 核心部件 -> 负例。
- LogDx-CI: benchmark/evaluation of log reduction tools，不是一个可直接采用的推理优化方法 -> 负例。
- SoftCap / Discrete Diffusion stochastic sampling: 只改变随机采样或质量-步数权衡、缺少明确推理部署收益时为负例；但 video diffusion / VLA 的明确低延迟、KV/cache、token pruning/merging、蒸馏、few-step rollout 加速为正例。
- Industrial crash dynamics low-rank attention: 工业仿真 surrogate/operator learning，不是目标 LLM/Agent 推理优化 -> 负例。

标签归类优先级：LLM speculative/draft/parallel generation decoding 或 diffusion language/video generation denoising/decoding 加速 -> 解码策略优化；LLM/VLM/video diffusion/VLA KV/cache/context compression/reuse -> 上下文与缓存优化；LLM/VLM/video diffusion/VLA quant/pruning/distillation/token merging -> 模型压缩；LLM serving / Agent serving routing/scheduling/resource orchestration -> 系统与调度优化；目标模型 inference kernel/operator/compiler -> 算子与内核优化。"""


@dataclass(slots=True)
class LlmRecommendationReviewRequest:
    """Inputs needed to review one recommendation report run."""

    source_name: str
    content_date: str
    report_dir: Path
    output_dir: Path
    candidate_papers: list[Paper]
    target_profile: str = DEFAULT_TARGET_PROFILE
    categories: list[str] | None = None
    candidate_batch_size: int = 10
    review_concurrency: int = DEFAULT_REVIEW_CONCURRENCY
    model: str = DEFAULT_CHAT_MODEL
    resume_dir: Path | None = None
    progress: Callable[[str], None] | None = None


@dataclass(slots=True)
class LlmRecommendationReviewResult:
    """Paths and compact counts for a completed recommendation review."""

    json_path: Path
    markdown_path: Path
    stdout_path: Path
    analyzed_count: int
    recommended_count: int
    false_positive_count: int
    borderline_count: int
    missed_count: int


class LlmRecommendationReviewer:
    """Review recommendation output with OpenRouter chat completions."""

    def __init__(self, client: OpenRouterClient | None = None) -> None:
        """Store an optional client for tests or custom OpenRouter settings."""
        self.client = client

    def review(self, request: LlmRecommendationReviewRequest) -> LlmRecommendationReviewResult:
        """Run an LLM quality review and write JSON/Markdown/stdout artifacts."""
        if request.candidate_batch_size <= 0:
            raise CliInputError("candidate_batch_size 必须大于 0")
        if request.review_concurrency <= 0:
            raise CliInputError("review_concurrency 必须大于 0")
        if not request.candidate_papers:
            raise CliInputError("大模型审阅需要候选论文全集")

        report_payload = _load_report_payload(request.report_dir / "result.json")
        recommended_rows = _read_recommended_rows(report_payload)
        recommended_ids = {str(row.get("paper_id", "")) for row in recommended_rows}
        candidate_rows = serialize_papers(request.candidate_papers)
        omitted_rows = [
            row for row in candidate_rows if str(row.get("paper_id", "")) not in recommended_ids
        ]

        client = self.client or OpenRouterClient(
            chat_model=request.model,
            concurrency=request.review_concurrency,
        )
        try:
            return self._review_with_client(
                request=request,
                client=client,
                report_payload=report_payload,
                candidate_rows=candidate_rows,
                recommended_rows=recommended_rows,
                omitted_rows=omitted_rows,
            )
        finally:
            if self.client is None:
                close = getattr(client, "close", None)
                if close is not None:
                    close()

    def _review_with_client(  # noqa: PLR0913
        self,
        *,
        request: LlmRecommendationReviewRequest,
        client: OpenRouterClient,
        report_payload: dict[str, Any],
        candidate_rows: list[dict[str, Any]],
        recommended_rows: list[dict[str, Any]],
        omitted_rows: list[dict[str, Any]],
    ) -> LlmRecommendationReviewResult:
        """Run the review using a resolved client."""
        _emit_progress(
            request.progress,
            "[blue-team] start "
            f"model={client.resolved_chat_model}, "
            f"candidates={len(candidate_rows)}, "
            f"recommended={len(recommended_rows)}, omitted={len(omitted_rows)}",
        )
        category_values = request.categories or DEFAULT_REVIEW_CATEGORIES
        system_prompt = _build_system_prompt(request.target_profile)
        schema_description = _build_schema_description(category_values)
        _emit_progress(
            request.progress,
            f"[blue-team] reviewing recommended papers independently count={len(recommended_rows)}...",
        )
        false_positive_payload = self._review_recommended(
            client=client,
            system_prompt=system_prompt,
            schema_description=schema_description,
            progress=request.progress,
            recommended_rows=recommended_rows,
        )
        _validate_recommended_payload(
            false_positive_payload,
            expected_ids={str(row.get("paper_id", "")) for row in recommended_rows},
        )
        _emit_progress(request.progress, "[blue-team] recommended review done")
        missed_payloads = self._review_omitted_batches(
            client=client,
            system_prompt=system_prompt,
            schema_description=schema_description,
            omitted_rows=omitted_rows,
            batch_size=request.candidate_batch_size,
            resume_dir=request.resume_dir,
            progress=request.progress,
        )
        _validate_omitted_payloads(
            missed_payloads,
            omitted_ids={str(row.get("paper_id", "")) for row in omitted_rows},
            categories=set(category_values),
        )
        first_pass_missed = _merge_missed_payloads(missed_payloads)
        _emit_progress(
            request.progress,
            f"[blue-team] verifying first-pass missed count={len(first_pass_missed)}...",
        )
        missed_verification_payload = self._verify_missed(
            client=client,
            system_prompt=system_prompt,
            missed_items=first_pass_missed,
            candidate_rows=candidate_rows,
            category_values=category_values,
        )
        _validate_verified_missed_payload(
            missed_verification_payload,
            first_pass_ids={str(item.get("paper_id", "")) for item in first_pass_missed},
            categories=set(category_values),
        )
        payload = _build_review_payload(
            request=request,
            report_payload=report_payload,
            candidate_rows=candidate_rows,
            recommended_rows=recommended_rows,
            false_positive_payload=false_positive_payload,
            missed_payloads=missed_payloads,
            missed_verification_payload=missed_verification_payload,
            model=client.resolved_chat_model,
        )
        result = _write_review_artifacts(request.output_dir, payload)
        _emit_progress(
            request.progress,
            "[blue-team] done "
            f"false_positive={result.false_positive_count} "
            f"borderline={result.borderline_count} missed={result.missed_count}",
        )
        return result

    def _review_recommended(
        self,
        *,
        client: OpenRouterClient,
        system_prompt: str,
        schema_description: str,
        progress: Callable[[str], None] | None,
        recommended_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payloads = _call_json_many(
            client,
            [
                (
                    str(row.get("paper_id", "")),
                    _build_recommended_messages(
                        system_prompt=system_prompt,
                        schema_description=schema_description,
                        row=row,
                    ),
                )
                for row in recommended_rows
            ],
        )
        reviews: list[dict[str, Any]] = []
        for row in recommended_rows:
            paper_id = str(row.get("paper_id", ""))
            payload = payloads[paper_id]
            row_reviews = _list_dicts(payload.get("recommended_reviews"))
            if len(row_reviews) != 1:
                raise CliInputError(f"OpenRouter 推荐逐篇审阅返回数量非法：{paper_id}")
            returned_id = str(row_reviews[0].get("paper_id", ""))
            if returned_id != paper_id:
                raise CliInputError(
                    f"OpenRouter 推荐逐篇审阅 paper_id 不匹配：期望 {paper_id}，实际 {returned_id}"
                )
            reviews.append(row_reviews[0])
            _emit_progress(progress, f"[blue-team] recommended paper reviewed {paper_id}")
        return {
            "recommended_reviews": reviews,
            "missed_recommendations": [],
            "per_paper_reviews": payloads,
        }

    def _review_omitted_batches(  # noqa: PLR0913
        self,
        *,
        client: OpenRouterClient,
        system_prompt: str,
        schema_description: str,
        omitted_rows: list[dict[str, Any]],
        batch_size: int,
        resume_dir: Path | None,
        progress: Callable[[str], None] | None,
    ) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        batches = _chunk_rows(omitted_rows, batch_size)
        total_batches = len(batches)
        batch_dir = resume_dir / "omitted-batches" if resume_dir else None
        if batch_dir:
            batch_dir.mkdir(parents=True, exist_ok=True)
        for batch_index, batch in enumerate(batches, start=1):
            batch_path = batch_dir / f"batch-{batch_index:06d}.json" if batch_dir else None
            if batch_path and batch_path.exists():
                try:
                    payload = json.loads(batch_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    batch_path.unlink()
                else:
                    if isinstance(payload, dict):
                        payloads.append(payload)
                        missed_count = len(_list_dicts(payload.get("missed_recommendations")))
                        _emit_progress(
                            progress,
                            "[blue-team] omitted batch "
                            f"{batch_index}/{total_batches} resumed, "
                            f"first_pass_missed={missed_count}",
                        )
                        continue
            _emit_progress(
                progress,
                "[blue-team] reviewing omitted batch "
                f"{batch_index}/{total_batches}, size={len(batch)}...",
            )
            payload = _call_json(
                client,
                [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": "\n".join(
                            [
                                f"请审阅第 {batch_index} 批“未推荐”候选论文。",
                                "只返回明显应该推荐的漏推荐；如果没有漏推荐，missed_recommendations 返回空数组。",
                                "不要返回已推荐审阅，recommended_reviews 返回空数组。",
                                "每批最多挑 2 篇；宁可漏掉边界样本，也不要扩大正例口径。",
                                "只返回高置信论文：必须同时满足 target_profile 中的 3 条正例必要条件。",
                                "优先按 few-shot 正例锚点找同类论文：QuantSpec/MagicDec、SmallKV、ParetoQ、Prepacking/Fiddler/MuxServe/AgServe。",
                                "遇到 few-shot 负例同类模式必须排除：泛化 test-time reasoning/pass@K/debate/judge、垂直 agent 应用、安全/benchmark、一般视觉/工业仿真。",
                                "video diffusion / video generation / VLA 若明确优化推理延迟、吞吐、显存、FLOPs、KV/cache、token pruning/merging 或 few-step rollout，可以返回。",
                                "如果只能说“可泛化”“有加速潜力”“提升效率”但摘要没有明确目标模型推理路径和效率指标，不要返回。",
                                schema_description,
                                json.dumps(
                                    {"omitted_candidate_papers": _compact_rows(batch)},
                                    ensure_ascii=False,
                                ),
                            ]
                        ),
                    },
                ],
            )
            payload["batch_index"] = batch_index
            payload["batch_size"] = len(batch)
            if batch_path:
                batch_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            payloads.append(payload)
            missed_count = len(_list_dicts(payload.get("missed_recommendations")))
            _emit_progress(
                progress,
                "[blue-team] omitted batch "
                f"{batch_index}/{total_batches} done, first_pass_missed={missed_count}",
            )
        return payloads

    def _verify_missed(
        self,
        *,
        client: OpenRouterClient,
        system_prompt: str,
        missed_items: list[dict[str, Any]],
        candidate_rows: list[dict[str, Any]],
        category_values: list[str],
    ) -> dict[str, Any]:
        if not missed_items:
            return {"verified_missed_recommendations": [], "_raw_content": "", "_usage": None}
        row_by_id = {str(row.get("paper_id", "")): row for row in candidate_rows}
        requests: list[tuple[str, list[dict[str, Any]]]] = []
        for item in missed_items:
            paper_id = str(item.get("paper_id", ""))
            row = row_by_id.get(paper_id)
            if row is None:
                continue
            compact_row = _compact_rows([row])[0]
            compact_row["first_pass_category"] = item.get("category", "")
            compact_row["first_pass_reason"] = item.get("reason", "")
            compact_row["first_pass_confidence"] = item.get("confidence", "")
            requests.append(
                (
                    paper_id,
                    _build_missed_verification_messages(
                        system_prompt=system_prompt,
                        category_values=category_values,
                        candidate=compact_row,
                    ),
                )
            )
        payloads = _call_json_many(client, requests)
        verified: list[dict[str, Any]] = []
        for paper_id, _messages in requests:
            items = _list_dicts(payloads[paper_id].get("verified_missed_recommendations"))
            if len(items) > 1:
                raise CliInputError(f"OpenRouter 漏推荐逐篇二审返回数量非法：{paper_id}")
            if items and str(items[0].get("paper_id", "")) != paper_id:
                raise CliInputError(
                    "OpenRouter 漏推荐逐篇二审 paper_id 不匹配："
                    f"期望 {paper_id}，实际 {items[0].get('paper_id', '')}"
                )
            verified.extend(items)
        return {
            "verified_missed_recommendations": verified,
            "_raw_content": "",
            "_usage": None,
            "per_paper_verifications": payloads,
        }


def _build_recommended_messages(
    *,
    system_prompt: str,
    schema_description: str,
    row: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "\n".join(
                [
                    "请独立审阅这一篇“已推荐”论文，判断是否误推荐或边界较弱。",
                    "只允许根据这一篇论文的标题、摘要、标签和推荐理由判断；不要与其他论文比较。",
                    "recommended_reviews 必须且只能返回这一篇论文一项，verdict 只能是 keep / false_positive / borderline。",
                    "整体口径从严：没有明确推理阶段、服务阶段、缓存、算子、模型压缩、解码策略或 Agent 系统调度效率贡献，就不要 keep。",
                    "非 LLM 的 video diffusion / video generation / VLA 推理加速、KV/cache、token pruning/merging、蒸馏或低延迟 rollout 算正例。",
                    "对预训练、训练数据、纯训练算法、新模型结构本身更快、纯应用场景、纯 benchmark/综述论文默认 false_positive。",
                    "Agent 系统的模型路由、工具调用、记忆/RAG状态、ReAct/多步推理预算优化可以 keep，归为系统与调度优化；LLM 投机推理、并行解码、测试时采样/搜索预算优化可以 keep，归为解码策略优化。",
                    schema_description,
                    json.dumps(
                        {"recommended_papers": _compact_rows([row])},
                        ensure_ascii=False,
                    ),
                ]
            ),
        },
    ]


def _build_missed_verification_messages(
    *,
    system_prompt: str,
    category_values: list[str],
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "\n".join(
                [
                    "下面是第一轮认为可能漏推荐的一篇论文，请做独立严格二审。",
                    "只允许根据这一篇论文和第一轮理由判断；不要与其他论文比较。",
                    "二审默认应该驳回；只有证据非常明确时才保留。",
                    "保留前逐条检查 target_profile 中的 3 条正例必要条件；任一不满足就返回空数组。",
                    "正例应像 QuantSpec/MagicDec、SmallKV、ParetoQ、Prepacking/Fiddler/MuxServe/AgServe。",
                    "如果像 UAB/CPPO/CPT、FinHarness/Spec-Agent/Agents that Matter、LogDx-CI、纯质量改进型 SoftCap/Discrete Diffusion、工业仿真 low-rank attention，则返回空数组。",
                    "video diffusion / video generation / VLA 若明确优化推理延迟、吞吐、显存、FLOPs、KV/cache、token pruning/merging 或 few-step rollout，可以保留。",
                    "不要被第一轮理由中的“可泛化、效率、成本、Agent、解码、上下文”等词带偏；必须看摘要核心贡献是否落在目标模型推理路径。",
                    "返回 JSON：verified_missed_recommendations 数组；保留则返回一项，剔除则返回空数组。每项包含 paper_id、category、confidence、reason。",
                    f"category 只能从这些值中选择：{', '.join(category_values)}。",
                    "不要为了凑数保留边界项。",
                    json.dumps({"first_pass_missed": [candidate]}, ensure_ascii=False),
                ]
            ),
        },
    ]


def write_review_failure_artifact(
    *,
    source_name: str,
    content_date: str,
    output_dir: Path,
    message: str,
) -> None:
    """Write stable failure artifacts without failing the primary report flow."""
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = "\n".join(
        [
            f"# {source_name} 大模型推荐审阅",
            "",
            f"- 内容日期：{content_date}",
            "- 状态：失败",
            f"- 失败原因：{message}",
            "- 下一步：检查 OpenRouter 配置或模型响应后重新运行报告流程。",
            "",
        ]
    )
    (output_dir / "summary.md").write_text(summary, encoding="utf-8")
    (output_dir / "stdout.txt").write_text(
        f"[FAIL] {source_name} 大模型审阅失败：{message}\n",
        encoding="utf-8",
    )
    (output_dir / "result.json").write_text(
        json.dumps(
            {
                "source": f"{source_name} LLM review",
                "content_date": content_date,
                "status": "failed",
                "error": message,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _build_system_prompt(target_profile: str) -> str:
    return f"""你是论文推荐质量审阅员。
{target_profile}

你要挑战现有推荐器：
1. 已推荐论文中，找误推荐或边界很弱的论文。
2. 未推荐候选中，只挑“明显应该推荐”的漏推荐。
宁可少报，不要泛泛扩大范围。"""


def _emit_progress(progress: Callable[[str], None] | None, line: str) -> None:
    if progress:
        progress(line)


def _validate_recommended_payload(payload: dict[str, Any], *, expected_ids: set[str]) -> None:
    reviews = _list_dicts(payload.get("recommended_reviews"))
    actual_ids = {str(item.get("paper_id", "")) for item in reviews}
    missing_ids = expected_ids - actual_ids
    unknown_ids = actual_ids - expected_ids
    if missing_ids:
        raise CliInputError("OpenRouter 推荐审阅缺少 paper_id：" + ", ".join(sorted(missing_ids)))
    if unknown_ids:
        raise CliInputError("OpenRouter 推荐审阅返回未知 paper_id：" + ", ".join(sorted(unknown_ids)))
    invalid_verdicts = sorted(
        {
            str(item.get("verdict", ""))
            for item in reviews
            if str(item.get("verdict", "")) not in RECOMMENDED_VERDICTS
        }
    )
    if invalid_verdicts:
        raise CliInputError("OpenRouter 推荐审阅 verdict 非法：" + ", ".join(invalid_verdicts))


def _validate_omitted_payloads(
    payloads: list[dict[str, Any]],
    *,
    omitted_ids: set[str],
    categories: set[str],
) -> None:
    for payload in payloads:
        if _list_dicts(payload.get("recommended_reviews")):
            raise CliInputError("OpenRouter 未推荐候选审阅不应返回 recommended_reviews")
        _validate_missed_items(
            payload.get("missed_recommendations"),
            allowed_ids=omitted_ids,
            categories=categories,
            field_name="missed_recommendations",
        )


def _validate_verified_missed_payload(
    payload: dict[str, Any],
    *,
    first_pass_ids: set[str],
    categories: set[str],
) -> None:
    _validate_missed_items(
        payload.get("verified_missed_recommendations"),
        allowed_ids=first_pass_ids,
        categories=categories,
        field_name="verified_missed_recommendations",
    )


def _validate_missed_items(
    value: object,
    *,
    allowed_ids: set[str],
    categories: set[str],
    field_name: str,
) -> None:
    items = _list_dicts(value)
    unknown_ids = sorted(
        {
            str(item.get("paper_id", ""))
            for item in items
            if str(item.get("paper_id", "")) not in allowed_ids
        }
    )
    if unknown_ids:
        raise CliInputError(f"OpenRouter {field_name} 返回未知 paper_id：" + ", ".join(unknown_ids))
    invalid_categories = sorted(
        {
            str(item.get("category", ""))
            for item in items
            if str(item.get("category", "")) not in categories
        }
    )
    if invalid_categories:
        raise CliInputError(
            f"OpenRouter {field_name} category 非法：" + ", ".join(invalid_categories)
        )


def _build_schema_description(categories: list[str]) -> str:
    category_schema = "|".join(categories)
    return f"""
Return strict JSON only. Do not wrap it in Markdown.
Schema:
{{
  "recommended_reviews": [
    {{
      "paper_id": "string",
      "verdict": "keep|false_positive|borderline",
      "confidence": 0.0,
      "reason": "short Chinese reason"
    }}
  ],
  "missed_recommendations": [
    {{
      "paper_id": "string",
      "category": "{category_schema}",
      "confidence": 0.0,
      "reason": "short Chinese reason"
    }}
  ]
}}
"""


def _load_report_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CliInputError(f"找不到报告 JSON：{path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliInputError(f"报告 JSON 无法解析：{path}") from exc
    if not isinstance(payload, dict):
        raise CliInputError(f"报告 JSON 顶层不是对象：{path}")
    return payload


def _read_recommended_rows(report_payload: dict[str, Any]) -> list[dict[str, Any]]:
    papers = report_payload.get("papers")
    if not isinstance(papers, list):
        raise CliInputError("报告 JSON 缺少 papers 数组")
    return [dict(row) for row in papers if isinstance(row, dict)]


def _call_json(client: OpenRouterClient, messages: list[dict[str, Any]]) -> dict[str, Any]:
    response = client.submit(messages).result()
    if not response.get("success"):
        raise CliInputError(f"OpenRouter 审阅失败：{response.get('error') or 'unknown error'}")
    content = str(response.get("content", "") or "").strip()
    try:
        parsed = json.loads(_extract_json_object(content))
    except json.JSONDecodeError as exc:
        raise CliInputError(f"OpenRouter 审阅响应不是合法 JSON：{content[:500]}") from exc
    if not isinstance(parsed, dict):
        raise CliInputError("OpenRouter 审阅响应顶层不是 JSON object")
    parsed["_raw_content"] = content
    parsed["_usage"] = response.get("usage")
    return parsed


def _call_json_many(
    client: OpenRouterClient,
    requests: list[tuple[str, list[dict[str, Any]]]],
) -> dict[str, dict[str, Any]]:
    if not requests:
        return {}
    seen: set[str] = set()
    duplicate_keys: set[str] = set()
    for key, _messages in requests:
        if key in seen:
            duplicate_keys.add(key)
        seen.add(key)
    if duplicate_keys:
        raise CliInputError("OpenRouter 并发审阅请求 key 重复：" + ", ".join(sorted(duplicate_keys)))

    futures = {
        client.submit(messages): key
        for key, messages in requests
    }
    payloads: dict[str, dict[str, Any]] = {}
    for future in as_completed(futures):
        key = futures[future]
        response = future.result()
        if not response.get("success"):
            raise CliInputError(
                f"OpenRouter 审阅失败({key})：{response.get('error') or 'unknown error'}"
            )
        content = str(response.get("content", "") or "").strip()
        try:
            parsed = json.loads(_extract_json_object(content))
        except json.JSONDecodeError as exc:
            raise CliInputError(f"OpenRouter 审阅响应不是合法 JSON({key})：{content[:500]}") from exc
        if not isinstance(parsed, dict):
            raise CliInputError(f"OpenRouter 审阅响应顶层不是 JSON object({key})")
        parsed["_raw_content"] = content
        parsed["_usage"] = response.get("usage")
        payloads[key] = parsed
    return payloads


def _extract_json_object(content: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end < start:
        return content
    return content[start : end + 1]


def _compact_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "paper_id": row.get("paper_id", ""),
            "title": row.get("title", ""),
            "abstract": row.get("abstract", ""),
            "authors": row.get("authors", ""),
            "tags": row.get("tags") or row.get("keywords", ""),
            "published_at": row.get("published_at", ""),
            "current_category": row.get("sampled_reason", ""),
            "current_reasons": row.get("reasons", []),
            "pdf_url": row.get("pdf_url", ""),
        }
        for row in rows
    ]


def _chunk_rows(rows: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [rows[index : index + batch_size] for index in range(0, len(rows), batch_size)]


def _build_review_payload(  # noqa: PLR0913
    *,
    request: LlmRecommendationReviewRequest,
    report_payload: dict[str, Any],
    candidate_rows: list[dict[str, Any]],
    recommended_rows: list[dict[str, Any]],
    false_positive_payload: dict[str, Any],
    missed_payloads: list[dict[str, Any]],
    missed_verification_payload: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    recommended_reviews = _list_dicts(false_positive_payload.get("recommended_reviews"))
    missed = _list_dicts(missed_verification_payload.get("verified_missed_recommendations"))
    false_positives = [
        item for item in recommended_reviews if item.get("verdict") == "false_positive"
    ]
    borderline = [item for item in recommended_reviews if item.get("verdict") == "borderline"]
    title_by_id = {
        str(row.get("paper_id", "")): str(row.get("title", ""))
        for row in [*candidate_rows, *recommended_rows]
    }
    _attach_titles(false_positives, title_by_id)
    _attach_titles(borderline, title_by_id)
    _attach_titles(missed, title_by_id)
    return {
        "source": f"{request.source_name} LLM review",
        "generated_at": datetime.now(UTC).isoformat(),
        "model": model,
        "content_date": request.content_date,
        "report_dir": str(request.report_dir),
        "candidate_count": len(candidate_rows),
        "recommended_count": len(recommended_rows),
        "omitted_count": len(candidate_rows) - len(recommended_rows),
        "false_positive_count": len(false_positives),
        "borderline_count": len(borderline),
        "missed_count": len(missed),
        "report_analysis": report_payload.get("analysis", {}),
        "false_positives": false_positives,
        "borderline_recommendations": borderline,
        "missed_recommendations": missed,
        "recommended_reviews": recommended_reviews,
        "raw_model_payloads": {
            "recommended_review": false_positive_payload,
            "omitted_reviews": missed_payloads,
            "missed_verification": missed_verification_payload,
        },
    }


def _merge_missed_payloads(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in payloads:
        for item in _list_dicts(payload.get("missed_recommendations")):
            paper_id = str(item.get("paper_id", ""))
            if not paper_id or paper_id in seen:
                continue
            seen.add(paper_id)
            merged.append(item)
    return merged


def _attach_titles(items: list[dict[str, Any]], title_by_id: dict[str, str]) -> None:
    for item in items:
        paper_id = str(item.get("paper_id", ""))
        if paper_id and not item.get("title"):
            item["title"] = title_by_id.get(paper_id, "")


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _write_review_artifacts(
    output_dir: Path,
    payload: dict[str, Any],
) -> LlmRecommendationReviewResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "result.json"
    markdown_path = output_dir / "summary.md"
    stdout_path = output_dir / "stdout.txt"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(payload), encoding="utf-8")
    stdout_path.write_text(_render_stdout(payload), encoding="utf-8")
    return LlmRecommendationReviewResult(
        json_path=json_path,
        markdown_path=markdown_path,
        stdout_path=stdout_path,
        analyzed_count=int(payload["candidate_count"]),
        recommended_count=int(payload["recommended_count"]),
        false_positive_count=int(payload["false_positive_count"]),
        borderline_count=int(payload["borderline_count"]),
        missed_count=int(payload["missed_count"]),
    )


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 大模型推荐审阅",
        "",
        f"- 内容日期：{payload['content_date']}",
        f"- 模型：{payload['model']}",
        f"- 候选论文：{payload['candidate_count']}",
        f"- 原推荐论文：{payload['recommended_count']}",
        f"- 误推荐：{payload['false_positive_count']}",
        f"- 边界推荐：{payload['borderline_count']}",
        f"- 漏推荐：{payload['missed_count']}",
        "",
        "## 误推荐",
        "",
        *_render_review_items(payload.get("false_positives"), include_category=False),
        "",
        "## 边界推荐",
        "",
        *_render_review_items(payload.get("borderline_recommendations"), include_category=False),
        "",
        "## 漏推荐",
        "",
        *_render_review_items(payload.get("missed_recommendations"), include_category=True),
        "",
    ]
    return "\n".join(lines)


def _render_review_items(value: object, *, include_category: bool) -> list[str]:
    items = _list_dicts(value)
    if not items:
        return ["- 无"]
    lines: list[str] = []
    for item in items:
        title = item.get("title") or item.get("paper_id", "")
        paper_id = item.get("paper_id", "")
        confidence = item.get("confidence", "")
        reason = item.get("reason", "")
        category = f" | {item.get('category', '')}" if include_category and item.get("category") else ""
        lines.append(f"- `{paper_id}` {title}{category} | confidence={confidence}：{reason}")
    return lines


def _render_stdout(payload: dict[str, Any]) -> str:
    return (
        "[OK] 大模型推荐审阅完成："
        f"误推荐 {payload['false_positive_count']}，"
        f"边界推荐 {payload['borderline_count']}，"
        f"漏推荐 {payload['missed_count']}\n"
    )
