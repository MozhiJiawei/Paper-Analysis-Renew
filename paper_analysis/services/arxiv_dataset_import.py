"""Build and import dataset samples from daily arXiv recommendation runs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

from paper_analysis.cli.common import CliInputError
from paper_analysis.shared.paths import ARTIFACTS_DIR, ROOT_DIR
from paper_analysis.utils.openrouter_client import DEFAULT_CHAT_MODEL, OpenRouterClient

if TYPE_CHECKING:
    from pathlib import Path

    from paper_analysis.domain.paper import Paper


DATASET_REPO_DIR = ROOT_DIR / "third_party" / "paper_analysis_dataset"
DEFAULT_OUTPUT_DIR = ARTIFACTS_DIR / "datasets" / "arxiv" / "latest"
DEFAULT_LABELER_ID = "arxiv_daily_ds_v4"
VALID_PREFERENCE_LABELS = {
    "解码策略优化",
    "上下文与缓存优化",
    "系统与调度优化",
    "算子与内核优化",
    "模型压缩",
}
VALID_RESEARCH_OBJECT_LABELS = {
    "LLM",
    "多模态 / VLM",
    "Diffusion / 生成模型",
    "通用机器学习",
    "强化学习 / 序列决策",
    "检索 / 推荐 / 搜索",
    "计算机视觉",
    "语音 / 音频",
    "AI 系统 / 基础设施",
    "评测 / Benchmark / 数据集",
}
BOUNDARY_POOL_LIMIT = 160
BOUNDARY_SAMPLE_LIMIT = 80
YEAR_PREFIX_LENGTH = 4
BOUNDARY_KEYWORDS = (
    "inference",
    "serving",
    "latency",
    "throughput",
    "memory",
    "cache",
    "kv",
    "token",
    "decode",
    "decoding",
    "efficient",
    "efficiency",
    "compression",
    "quantization",
    "pruning",
    "distillation",
    "scheduling",
    "routing",
    "kernel",
    "compiler",
    "speedup",
)


class BoundarySamplerClient(Protocol):
    """Minimal chat client used by the boundary-negative sampler."""

    @property
    def resolved_chat_model(self) -> str:
        """Return the model name used for provenance."""
        ...

    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> ChatFuture:
        """Submit one chat request and return a Future-like object."""
        ...


class ChatFuture(Protocol):
    """Future-like chat response used by OpenRouter and tests."""

    def result(self) -> dict[str, object]:
        """Return a normalized chat response."""
        ...


class ArxivDatasetImportPayload(TypedDict):
    """Dataset-native payload accepted by the child repository importer."""

    source_batch: str
    records: list[dict[str, object]]
    annotations_ai: list[dict[str, object]]


@dataclass(slots=True)
class ArxivDatasetImportResult:
    """Artifacts and import status for one daily dataset import."""

    payload_path: Path
    summary_path: Path
    stdout_path: Path
    record_count: int
    positive_count: int
    negative_count: int
    boundary_negative_count: int
    import_status: str
    import_stdout: str = ""
    import_stderr: str = ""


@dataclass(slots=True)
class BoundaryNegative:
    """One ds-v4 selected boundary negative."""

    paper_id: str
    reason: str


@dataclass(slots=True)
class AnnotationInput:
    """Input bundle for one dataset AI annotation."""

    paper_id: str
    primary_research_object: str
    preference_label: str
    negative_tier: str
    evidence: list[str]
    notes: str


def build_and_import_arxiv_dataset_samples(  # noqa: PLR0913
    *,
    content_date: str,
    candidate_papers: list[Paper],
    recommended_papers: list[Paper],
    review_json_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    dataset_repo_dir: Path = DATASET_REPO_DIR,
    benchmark_root: Path | None = None,
    dry_run: bool = False,
    client: BoundarySamplerClient | None = None,
) -> ArxivDatasetImportResult:
    """Build a dataset-native payload and import it through the child repo API."""
    review_payload = _load_review_payload(review_json_path)
    boundary_client = client or OpenRouterClient(chat_model=DEFAULT_CHAT_MODEL)
    try:
        payload = build_arxiv_dataset_import_payload(
            content_date=content_date,
            candidate_papers=candidate_papers,
            recommended_papers=recommended_papers,
            review_payload=review_payload,
            client=boundary_client,
        )
    finally:
        if client is None:
            close = getattr(boundary_client, "close", None)
            if close is not None:
                close()
    output_dir.mkdir(parents=True, exist_ok=True)
    payload_path = output_dir / "import-payload.json"
    summary_path = output_dir / "summary.json"
    stdout_path = output_dir / "stdout.txt"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    import_status = "skipped"
    import_stdout = ""
    import_stderr = ""
    try:
        completed = _run_dataset_import(
            payload_path=payload_path,
            dataset_repo_dir=dataset_repo_dir,
            benchmark_root=benchmark_root,
            dry_run=dry_run,
        )
    except CliInputError as exc:
        import_status = "failed"
        import_stderr = str(exc)
    else:
        import_stdout = completed.stdout
        import_stderr = completed.stderr
        import_status = "ok" if completed.returncode == 0 else "failed"

    annotations = payload["annotations_ai"]
    records = payload["records"]
    positive_count = sum(1 for item in annotations if item.get("negative_tier") == "positive")
    negative_count = sum(1 for item in annotations if item.get("negative_tier") == "negative")
    boundary_negative_count = sum(
        1 for item in annotations if "boundary_negative" in str(item.get("notes", ""))
    )
    summary = {
        "ok": import_status == "ok",
        "content_date": content_date,
        "payload_path": str(payload_path),
        "record_count": len(records),
        "ai_positive_count": positive_count,
        "ai_negative_count": negative_count,
        "boundary_negative_count": boundary_negative_count,
        "import_status": import_status,
        "import_stdout": import_stdout,
        "import_stderr": import_stderr,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    stdout_path.write_text(_render_stdout(summary), encoding="utf-8")
    return ArxivDatasetImportResult(
        payload_path=payload_path,
        summary_path=summary_path,
        stdout_path=stdout_path,
        record_count=len(records),
        positive_count=positive_count,
        negative_count=negative_count,
        boundary_negative_count=boundary_negative_count,
        import_status=import_status,
        import_stdout=import_stdout,
        import_stderr=import_stderr,
    )


def build_arxiv_dataset_import_payload(
    *,
    content_date: str,
    candidate_papers: list[Paper],
    recommended_papers: list[Paper],
    review_payload: dict[str, Any],
    client: BoundarySamplerClient,
) -> ArxivDatasetImportPayload:
    """Convert one arXiv run into the dataset repo's normalized import payload."""
    candidate_by_id = {paper.paper_id: paper for paper in candidate_papers}
    recommended_reviews = _recommended_review_map(review_payload)
    missed = _missed_review_map(review_payload)

    records: dict[str, dict[str, object]] = {}
    annotations: dict[str, dict[str, object]] = {}

    for paper in recommended_papers:
        review = recommended_reviews.get(paper.paper_id, {})
        annotation = _annotation_for_recommended_paper(
            paper=paper,
            review=review,
            content_date=content_date,
        )
        records[paper.paper_id] = _record_for_paper(
            paper=paper,
            candidate_label=paper.sampled_reason,
            candidate_negative_tier="positive",
            notes=_notes(
                source="ai_recommendation",
                content_date=content_date,
                recommender_decision="positive",
                recommender_label=paper.sampled_reason,
                blue_team_decision=str(review.get("verdict", "not_reviewed") or "not_reviewed"),
                blue_team_label=str(review.get("category", "") or ""),
                blue_team_reason=str(review.get("reason", "") or ""),
            ),
        )
        annotations[paper.paper_id] = annotation

    for paper_id, review in missed.items():
        candidate_paper = candidate_by_id.get(paper_id)
        if candidate_paper is None:
            continue
        label = _valid_preference_label(str(review.get("category", "")))
        records[paper_id] = _record_for_paper(
            paper=candidate_paper,
            candidate_label=label,
            candidate_negative_tier="positive",
            notes=_notes(
                source="blue_team_missed",
                content_date=content_date,
                recommender_decision="negative",
                recommender_label="",
                blue_team_decision="missed_positive",
                blue_team_label=label,
                blue_team_reason=str(review.get("reason", "") or ""),
            ),
        )
        annotations[paper_id] = _annotation(
            AnnotationInput(
                paper_id=paper_id,
                primary_research_object=_paper_research_object(candidate_paper),
                preference_label=label,
                negative_tier="positive",
                evidence=_evidence_for_review(review, fallback=candidate_paper.title),
                notes=_notes(
                    source="blue_team_missed",
                    content_date=content_date,
                    recommender_decision="negative",
                    recommender_label="",
                    blue_team_decision="missed_positive",
                    blue_team_label=label,
                    blue_team_reason=str(review.get("reason", "") or ""),
                ),
            )
        )

    positive_count = sum(
        1 for annotation in annotations.values() if annotation["negative_tier"] == "positive"
    )
    negative_count = sum(
        1 for annotation in annotations.values() if annotation["negative_tier"] == "negative"
    )
    target_boundary_count = min(
        BOUNDARY_SAMPLE_LIMIT,
        max(0, positive_count - negative_count),
    )
    excluded_ids = set(records)
    boundary_negatives = sample_boundary_negatives(
        candidate_papers=[
            paper for paper in candidate_papers if paper.paper_id not in excluded_ids
        ],
        target_count=target_boundary_count,
        client=client,
    )
    for boundary in boundary_negatives:
        boundary_paper = candidate_by_id.get(boundary.paper_id)
        if boundary_paper is None or boundary_paper.paper_id in records:
            continue
        records[boundary_paper.paper_id] = _record_for_paper(
            paper=boundary_paper,
            candidate_label="",
            candidate_negative_tier="negative",
            notes=_notes(
                source="boundary_negative",
                content_date=content_date,
                recommender_decision="negative",
                recommender_label="",
                blue_team_decision="not_selected_for_review",
                blue_team_label="",
                blue_team_reason="",
                boundary_negative_reason=boundary.reason,
            ),
        )
        annotations[boundary_paper.paper_id] = _annotation(
            AnnotationInput(
                paper_id=boundary_paper.paper_id,
                primary_research_object=_paper_research_object(boundary_paper),
                preference_label="",
                negative_tier="negative",
                evidence=[boundary.reason or boundary_paper.title],
                notes=_notes(
                    source="boundary_negative",
                    content_date=content_date,
                    recommender_decision="negative",
                    recommender_label="",
                    blue_team_decision="not_selected_for_review",
                    blue_team_label="",
                    blue_team_reason="",
                    boundary_negative_reason=boundary.reason,
                ),
            )
        )

    return {
        "source_batch": f"arxiv_daily_review:{content_date}",
        "records": list(records.values()),
        "annotations_ai": list(annotations.values()),
    }


def sample_boundary_negatives(
    *,
    candidate_papers: list[Paper],
    target_count: int,
    client: BoundarySamplerClient,
) -> list[BoundaryNegative]:
    """Ask ds-v4 to select diverse near-boundary negative examples."""
    if target_count <= 0 or not candidate_papers:
        return []
    pool = _boundary_candidate_pool(candidate_papers)
    if not pool:
        return []
    response = client.submit(
        [
            {
                "role": "system",
                "content": (
                    "你是论文筛选数据集的边界负例抽样器。目标偏好是模型后训练与推理阶段的效率优化。"
                    "从候选中挑选接近边界但应标为 negative 的论文，保证主题多样性。"
                    "不要选择明显正例；不要选择已推荐或蓝军已覆盖的论文。"
                    '只返回 JSON：{"boundary_negatives":[{"paper_id":"...","reason":"..."}]}'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "target_count": target_count,
                        "selection_policy": [
                            "边界负例应包含容易被关键词误召回的训练优化、纯应用、benchmark、通用系统或领域任务。",
                            "样本应覆盖不同 arXiv 领域和不同误触发词。",
                            "如果候选里没有足够边界负例，可以少选。",
                        ],
                        "candidate_papers": [_compact_paper(paper) for paper in pool],
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    ).result()
    if not response.get("success"):
        raise CliInputError(f"ds-v4 边界负例抽样失败：{response.get('error') or 'unknown error'}")
    payload = _parse_json_object(str(response.get("content", "") or ""))
    allowed_ids = {paper.paper_id for paper in pool}
    selected: list[BoundaryNegative] = []
    seen: set[str] = set()
    for item in payload.get("boundary_negatives", []):
        if not isinstance(item, dict):
            continue
        paper_id = str(item.get("paper_id", "")).strip()
        if paper_id not in allowed_ids or paper_id in seen:
            continue
        seen.add(paper_id)
        selected.append(
            BoundaryNegative(
                paper_id=paper_id,
                reason=str(item.get("reason", "")).strip(),
            )
        )
        if len(selected) >= target_count:
            break
    return selected


def _load_review_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliInputError(f"蓝军审阅 JSON 无法解析：{path}") from exc
    if not isinstance(payload, dict):
        raise CliInputError(f"蓝军审阅 JSON 顶层不是对象：{path}")
    return payload


def _recommended_review_map(review_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    reviews = review_payload.get("recommended_reviews")
    if isinstance(reviews, list):
        return {
            str(item.get("paper_id", "")): dict(item)
            for item in reviews
            if isinstance(item, dict) and str(item.get("paper_id", "")).strip()
        }
    result: dict[str, dict[str, Any]] = {}
    for verdict, field_name in (
        ("false_positive", "false_positives"),
        ("borderline", "borderline_recommendations"),
    ):
        items = review_payload.get(field_name)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            paper_id = str(item.get("paper_id", "")).strip()
            if paper_id:
                result[paper_id] = {**item, "verdict": verdict}
    return result


def _missed_review_map(review_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = review_payload.get("missed_recommendations")
    if not isinstance(items, list):
        return {}
    return {
        str(item.get("paper_id", "")): dict(item)
        for item in items
        if isinstance(item, dict) and str(item.get("paper_id", "")).strip()
    }


def _annotation_for_recommended_paper(
    *,
    paper: Paper,
    review: dict[str, Any],
    content_date: str,
) -> dict[str, object]:
    verdict = str(review.get("verdict", "keep") or "keep")
    if verdict == "false_positive":
        return _annotation(
            AnnotationInput(
                paper_id=paper.paper_id,
                primary_research_object=_paper_research_object(paper),
                preference_label="",
                negative_tier="negative",
                evidence=_evidence_for_review(review, fallback=paper.title),
                notes=_notes(
                    source="ai_recommendation_blue_team_false_positive",
                    content_date=content_date,
                    recommender_decision="positive",
                    recommender_label=paper.sampled_reason,
                    blue_team_decision="false_positive",
                    blue_team_label="",
                    blue_team_reason=str(review.get("reason", "") or ""),
                ),
            )
        )
    return _annotation(
        AnnotationInput(
            paper_id=paper.paper_id,
            primary_research_object=_paper_research_object(paper),
            preference_label=_valid_preference_label(paper.sampled_reason),
            negative_tier="positive",
            evidence=_paper_evidence(paper),
            notes=_notes(
                source="ai_recommendation",
                content_date=content_date,
                recommender_decision="positive",
                recommender_label=paper.sampled_reason,
                blue_team_decision=verdict,
                blue_team_label=str(review.get("category", "") or ""),
                blue_team_reason=str(review.get("reason", "") or ""),
            ),
        )
    )


def _record_for_paper(
    *,
    paper: Paper,
    candidate_label: str,
    candidate_negative_tier: str,
    notes: str,
) -> dict[str, object]:
    label = _valid_preference_label(candidate_label)
    return {
        "paper_id": paper.paper_id,
        "title": paper.title,
        "abstract": paper.abstract,
        "authors": paper.authors,
        "venue": paper.venue or "arXiv",
        "year": paper.year or _extract_year(paper.published_at),
        "source": paper.source or "arxiv",
        "source_path": paper.source_path or paper.pdf_url or f"arxiv:{paper.paper_id}",
        "primary_research_object": _paper_research_object(paper),
        "candidate_preference_labels": [label] if candidate_negative_tier == "positive" and label else [],
        "candidate_negative_tier": candidate_negative_tier,
        "keywords": [*paper.tags, *paper.keywords],
        "notes": _join_notes(notes, f"dataset_imported_at={datetime.now(UTC).isoformat()}"),
    }


def _annotation(annotation: AnnotationInput) -> dict[str, object]:
    label = _valid_preference_label(annotation.preference_label)
    return {
        "paper_id": annotation.paper_id,
        "labeler_id": DEFAULT_LABELER_ID,
        "primary_research_object": annotation.primary_research_object,
        "preference_labels": (
            [label] if annotation.negative_tier == "positive" and label else []
        ),
        "negative_tier": annotation.negative_tier,
        "evidence_spans": {
            (
                label if annotation.negative_tier == "positive" and label else "negative"
            ): annotation.evidence[:2] or [annotation.paper_id]
        },
        "notes": annotation.notes,
        "review_status": "pending",
    }


def _paper_research_object(paper: Paper) -> str:
    prediction = paper.raw_payload.get("evaluation_prediction")
    if isinstance(prediction, dict):
        value = str(prediction.get("primary_research_object", "")).strip()
        if value in VALID_RESEARCH_OBJECT_LABELS:
            return value
    return "通用机器学习"


def _valid_preference_label(value: str) -> str:
    label = value.strip()
    return label if label in VALID_PREFERENCE_LABELS else ""


def _paper_evidence(paper: Paper) -> list[str]:
    evidence = [reason for reason in paper.reasons if reason.strip()]
    if evidence:
        return evidence[:2]
    return [paper.abstract[:240] if paper.abstract else paper.title]


def _evidence_for_review(review: dict[str, Any], *, fallback: str) -> list[str]:
    reason = str(review.get("reason", "")).strip()
    return [reason or fallback]


def _boundary_candidate_pool(candidate_papers: list[Paper]) -> list[Paper]:
    scored = sorted(
        ((-_boundary_score(paper), paper.title, paper) for paper in candidate_papers),
        key=lambda item: (item[0], item[1]),
    )
    return [paper for _score, _title, paper in scored[:BOUNDARY_POOL_LIMIT]]


def _boundary_score(paper: Paper) -> int:
    text = " ".join([paper.title, paper.abstract, " ".join(paper.tags), " ".join(paper.keywords)]).lower()
    score = sum(1 for keyword in BOUNDARY_KEYWORDS if keyword in text)
    if any(keyword in text for keyword in ("benchmark", "dataset", "survey", "training", "fine-tuning")):
        score += 2
    return score


def _compact_paper(paper: Paper) -> dict[str, object]:
    return {
        "paper_id": paper.paper_id,
        "title": paper.title,
        "abstract": paper.abstract[:1200],
        "tags": paper.tags,
        "published_at": paper.published_at,
    }


def _parse_json_object(content: str) -> dict[str, Any]:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise CliInputError(f"ds-v4 边界负例抽样响应不是 JSON：{content[:300]}")
    try:
        payload = json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise CliInputError(f"ds-v4 边界负例抽样响应 JSON 非法：{content[:300]}") from exc
    if not isinstance(payload, dict):
        raise CliInputError("ds-v4 边界负例抽样响应顶层不是对象")
    return payload


def _run_dataset_import(
    *,
    payload_path: Path,
    dataset_repo_dir: Path,
    benchmark_root: Path | None,
    dry_run: bool,
) -> subprocess.CompletedProcess[str]:
    if not (dataset_repo_dir / "paper_analysis_dataset").exists():
        raise CliInputError(f"找不到数据集子仓 API：{dataset_repo_dir}")
    command = [
        sys.executable,
        "-m",
        "paper_analysis_dataset.tools.import_paper_filter_samples",
        "--input-json",
        str(payload_path),
    ]
    if benchmark_root is not None:
        command.extend(["--benchmark-root", str(benchmark_root)])
    if dry_run:
        command.append("--dry-run")
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(  # noqa: S603
        command,
        cwd=dataset_repo_dir,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _notes(**items: str) -> str:
    source = items.get("source", "")
    content_date = items.get("content_date", "")
    recommender_decision = items.get("recommender_decision", "")
    recommender_label = items.get("recommender_label", "")
    blue_team_decision = items.get("blue_team_decision", "")
    blue_team_label = items.get("blue_team_label", "")
    blue_team_reason = items.get("blue_team_reason", "")
    boundary_negative_reason = items.get("boundary_negative_reason", "")

    lines = [
        f"导入来源：{_source_label(source)}",
        f"内容日期：{content_date}",
        "AI 推荐算法结论："
        + _recommender_label(recommender_decision, recommender_label),
        "蓝军审阅结论："
        + _blue_team_label(blue_team_decision, blue_team_label),
    ]
    if blue_team_reason:
        lines.append(f"蓝军理由：{_escape_note(blue_team_reason)}")
    if boundary_negative_reason:
        lines.append(f"ds-v4 边界负例理由：{_escape_note(boundary_negative_reason)}")
    return "\n".join(lines)


def _join_notes(*items: str) -> str:
    return "\n".join(item for item in items if item)


def _escape_note(value: str) -> str:
    return str(value).replace("\n", " ").strip()


def _source_label(source: str) -> str:
    return {
        "ai_recommendation": "AI 推荐结果",
        "ai_recommendation_blue_team_false_positive": "AI 推荐结果 + 蓝军误推荐校验",
        "blue_team_missed": "蓝军漏推荐校验",
        "boundary_negative": "ds-v4 边界负例抽样",
    }.get(source, source or "未知")


def _recommender_label(decision: str, preference_label: str) -> str:
    if decision == "positive":
        return f"推荐为正样本；标签：{preference_label or '未给出'}"
    if decision == "negative":
        return "未推荐，判定为负样本或未命中偏好"
    return decision or "未知"


def _blue_team_label(decision: str, preference_label: str) -> str:
    labels = {
        "keep": "保留推荐，认可为正样本",
        "false_positive": "误推荐，应作为负样本",
        "borderline": "边界推荐，需要人工重点复核",
        "not_selected_for_review": "未进入蓝军逐篇审阅；由 ds-v4 作为边界负例补样",
        "not_reviewed": "未被蓝军标为误推荐或边界项",
    }
    if decision == "missed_positive":
        return f"漏推荐，应作为正样本；标签：{preference_label or '未给出'}"
    return labels.get(decision, decision or "未知")


def _extract_year(published_at: str) -> int:
    if (
        len(published_at) >= YEAR_PREFIX_LENGTH
        and published_at[:YEAR_PREFIX_LENGTH].isdigit()
    ):
        return int(published_at[:YEAR_PREFIX_LENGTH])
    return 1970


def _render_stdout(summary: dict[str, object]) -> str:
    if summary["import_status"] == "ok":
        return (
            "[OK] arXiv 数据集样本导入完成："
            f"records={summary['record_count']} "
            f"positive={summary['ai_positive_count']} "
            f"negative={summary['ai_negative_count']} "
            f"boundary_negative={summary['boundary_negative_count']}\n"
        )
    return (
        "[WARN] arXiv 数据集样本导入未完成："
        f"status={summary['import_status']} "
        f"stderr={summary['import_stderr']}\n"
    )
