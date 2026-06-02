"""CLI commands for the arXiv fetch and report workflow."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from paper_analysis.api.evaluation_predictor import EvaluationPredictor
from paper_analysis.cli.common import CliInputError, emit_lines, emit_progress, print_cli_error
from paper_analysis.domain.delivery_run import SubscriptionDeliveryRequest
from paper_analysis.domain.email_delivery import EmailConfigError
from paper_analysis.domain.paper import Paper
from paper_analysis.services.arxiv_dataset_import import (
    ArxivDatasetImportResult,
    build_and_import_arxiv_dataset_samples,
)
from paper_analysis.services.arxiv_pipeline import ArxivPipeline
from paper_analysis.services.arxiv_recommender import ArxivRecommender
from paper_analysis.services.arxiv_subscription_delivery import deliver_subscription_run
from paper_analysis.services.llm_recommendation_reviewer import (
    LlmRecommendationReviewer,
    LlmRecommendationReviewRequest,
    LlmRecommendationReviewResult,
    write_review_failure_artifact,
)
from paper_analysis.services.report_writer import serialize_papers, write_report
from paper_analysis.shared.paths import ARTIFACTS_DIR
from paper_analysis.sources.arxiv.affiliation_enricher import (
    enrich_selected_arxiv_papers_with_affiliations,
)

if TYPE_CHECKING:
    import argparse

    from paper_analysis.domain.preference import PreferenceProfile


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the arXiv CLI namespace and its stable subcommands."""
    parser = subparsers.add_parser("arxiv", help="arXiv 日更与订阅筛选工作流")
    arxiv_subparsers = parser.add_subparsers(dest="arxiv_action", required=True)

    filter_parser = arxiv_subparsers.add_parser(
        "daily-filter",
        help="从样例数据或订阅 API 拉取 arXiv 论文，并输出过滤后的结果",
    )
    _add_common_arguments(filter_parser)
    filter_parser.set_defaults(handler=handle_daily_filter)

    report_parser = arxiv_subparsers.add_parser(
        "report",
        help="执行 arXiv 拉取、过滤并写出 Markdown/JSON/CSV/stdout 报告",
    )
    _add_common_arguments(report_parser)
    report_parser.add_argument(
        "--deliver-subscription",
        action="store_true",
        help="在生成基础报告后继续执行订阅投递闭环（邮件 + HTML 站点 + 归档）",
    )
    report_parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="订阅邮件全量报告每次推进的候选论文批大小，默认 100",
    )
    report_parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="清除该订阅日期的未完成分批进度后重新开始",
    )
    report_parser.set_defaults(handler=handle_report)

    import_dataset_parser = arxiv_subparsers.add_parser(
        "import-dataset",
        help="手动把某天 arXiv 报告样本导入评测数据集",
    )
    import_dataset_parser.add_argument(
        "--subscription-date",
        help="要导入的分日报告日期，格式 YYYY-MM/MM-DD",
    )
    import_dataset_parser.set_defaults(
        handler=handle_import_dataset,
        source_mode="subscription-email",
        input=None,
        preferences=None,
        category=[],
        max_results=10,
        fetch_all=False,
        deliver_subscription=False,
        batch_size=100,
        reset_progress=False,
    )


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", type=Path, help="样例论文 JSON 路径")
    parser.add_argument("--preferences", type=Path, help="偏好配置 JSON 路径")
    parser.add_argument(
        "--source-mode",
        choices=["fixture", "subscription-api", "subscription-email"],
        default="fixture",
        help="输入来源；提供 --subscription-date 时默认 subscription-email，否则默认 fixture",
    )
    parser.add_argument(
        "--subscription-date",
        help="订阅日期，格式 YYYY-MM/MM-DD，仅 subscription-api/subscription-email 模式必填",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="限定 arXiv 分类，可重复传入；未传时使用默认分类集合",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="订阅 API 最多拉取多少篇论文",
    )
    parser.add_argument(
        "--fetch-all",
        action="store_true",
        help="按当前分类集合全量拉取该订阅日期的结果，不受 --max-results 截断",
    )


def handle_daily_filter(args: argparse.Namespace) -> int:
    """Run the arXiv fetch flow and print a compact terminal summary."""
    _normalize_source_mode(args)
    try:
        papers, _preferences = _run_pipeline(args)
    except CliInputError as exc:
        return print_cli_error(
            scope="arxiv.daily-filter",
            message=str(exc),
            next_step="检查 --input/--preferences，或在订阅模式下补充 --subscription-date",
        )

    if not papers:
        emit_lines("[OK] 本次 arXiv 拉取没有返回论文。")
        return 0

    emit_lines(f"[OK] arXiv 拉取完成，共 {len(papers)} 篇：")
    for index, paper in enumerate(papers, start=1):
        emit_lines(f"{index}. {paper.title} | {paper.venue} | {paper.published_at}")
    return 0


def handle_report(args: argparse.Namespace) -> int:
    """Run the arXiv report flow and write report artifacts."""
    _normalize_source_mode(args)
    delivery_error = _validate_subscription_delivery_args(args)
    if delivery_error is not None:
        return delivery_error
    if _should_run_resumable_report(args):
        return _handle_resumable_report(args)

    try:
        result = ArxivPipeline(
            recommender=ArxivRecommender(
                predictor=EvaluationPredictor(llm_hard_case_review=True)
            )
        ).run_with_details(
            args.input,
            args.preferences,
            source_mode=args.source_mode,
            subscription_date=args.subscription_date,
            categories=args.category,
            max_results=args.max_results,
            fetch_all=args.fetch_all,
            progress=emit_progress,
        )
    except CliInputError as exc:
        return print_cli_error(
            scope="arxiv.report",
            message=str(exc),
            next_step="检查报告输入文件，或在订阅模式下补充有效的订阅参数",
        )

    report_dir = ARTIFACTS_DIR / "e2e" / "arxiv" / "latest"
    artifacts = write_report(
        report_dir=report_dir,
        source_name="arXiv",
        papers=result.papers,
        command_name=_build_command_name(args),
        analysis_count=result.fetched_count,
    )
    _attach_candidate_papers_to_report(
        report_json_path=artifacts["json"],
        candidate_papers=result.candidate_papers,
    )
    _attach_recommendation_layers_to_report(
        report_artifacts=artifacts,
        candidate_papers=result.candidate_papers,
    )
    _snapshot_red_team_report(report_dir)
    review_result = _write_default_review_artifacts(
        args=args,
        report_dir=report_dir,
        candidate_papers=result.candidate_papers,
    )
    if _should_write_default_review(args):
        _append_blue_team_review_to_report(
            report_artifacts=artifacts,
            review_json_path=_review_output_dir() / "result.json",
        )
    archive_paths = _archive_arxiv_report_run(
        content_date=args.subscription_date,
        report_dir=report_dir,
        review_dir=_review_output_dir(),
    )
    if not args.deliver_subscription:
        lines = [f"[OK] arXiv 报告已生成：{artifacts['markdown']}"]
        if review_result:
            lines.append(f"[OK] 大模型审阅已生成：{review_result.markdown_path}")
        if archive_paths:
            lines.append(f"[OK] 分日报告归档：{archive_paths['daily_dir']}")
        emit_lines(*lines)
        return 0

    try:
        delivery_result = deliver_subscription_run(
            SubscriptionDeliveryRequest(
                papers=result.papers,
                fetched_count=result.fetched_count,
                subscription_date=args.subscription_date,
                command_name=_build_command_name(args),
                latest_report_dir=report_dir,
                report_artifacts=artifacts,
                runs_root_dir=ARTIFACTS_DIR / "subscriptions" / "arxiv" / "runs",
                site_dir=ARTIFACTS_DIR / "subscriptions" / "arxiv" / "site",
            ),
        )
    except EmailConfigError as exc:
        return print_cli_error(
            scope="arxiv.report",
            message=str(exc),
            next_step="设置 SMTP 环境变量或用户私有邮件配置后重试",
        )

    if delivery_result.status != "sent":
        return print_cli_error(
            scope="arxiv.report",
            message=delivery_result.summary or "订阅投递失败",
            next_step=delivery_result.next_step or f"检查 {delivery_result.snapshot_path}",
        )

    emit_lines(
        f"[OK] arXiv 报告已生成：{artifacts['markdown']}",
        *([f"[OK] 大模型审阅已生成：{review_result.markdown_path}"] if review_result else []),
        *(
            [
                f"[OK] 分日报告归档：{archive_paths['daily_dir']}",
            ]
            if archive_paths
            else []
        ),
        f"[OK] 订阅投递完成，run_id={delivery_result.run_id}",
        f"snapshot: {delivery_result.snapshot_path}",
        f"latest_page: {delivery_result.latest_page_path}",
        f"history_page: {delivery_result.index_page_path}",
    )
    return 0


def _should_run_resumable_report(args: argparse.Namespace) -> bool:
    return (
        args.source_mode == "subscription-email"
        and bool(args.subscription_date)
        and bool(args.fetch_all)
    )


def _handle_resumable_report(args: argparse.Namespace) -> int:
    try:
        return _run_resumable_report(args)
    except CliInputError as exc:
        return print_cli_error(
            scope="arxiv.report",
            message=str(exc),
            next_step="继续运行同一条 arxiv report 命令，或确认后追加 --reset-progress 重开批次",
        )


def _run_resumable_report(args: argparse.Namespace) -> int:
    batch_size = _validated_report_batch_size(args)
    content_date = str(args.subscription_date or "")
    daily_dir = _dated_report_dir(content_date)
    work_dir = daily_dir / "work"
    state_path = daily_dir / "workflow-state.json"
    if args.reset_progress and daily_dir.exists():
        shutil.rmtree(daily_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    pipeline = ArxivPipeline(
        recommender=ArxivRecommender(
            predictor=EvaluationPredictor(llm_hard_case_review=True)
        )
    )
    candidate_papers = pipeline._load_records(  # noqa: SLF001
        papers_path=args.input,
        source_mode=args.source_mode,
        subscription_date=args.subscription_date,
        categories=args.category,
        max_results=args.max_results,
        fetch_all=args.fetch_all,
        progress=emit_progress,
    )
    candidate_ids = [paper.paper_id for paper in candidate_papers]
    state = _load_workflow_state(state_path)
    if state:
        _validate_workflow_state(
            state=state,
            content_date=content_date,
            candidate_ids=candidate_ids,
            batch_size=batch_size,
        )
        final_summary_path = daily_dir / "final-summary.md"
        if state.get("status") == "final_complete" and final_summary_path.exists():
            emit_lines(
                f"[OK] arXiv 最终报告已存在：{final_summary_path}",
                "next: GitHub Issue 发布脚本可以读取 final-* 产物",
            )
            return 0
    else:
        state = _new_workflow_state(
            content_date=content_date,
            candidate_ids=candidate_ids,
            batch_size=batch_size,
        )
        _write_workflow_state(state_path, state)

    processed_count = int(state.get("processed_count", 0))
    total_count = len(candidate_papers)
    if processed_count < total_count:
        end_index = min(processed_count + batch_size, total_count)
        batch_papers = candidate_papers[processed_count:end_index]
        emit_progress(
            "[arxiv] resumable recommendation batch "
            f"{processed_count + 1}-{end_index}/{total_count}"
        )
        batch_result = ArxivRecommender(
            predictor=EvaluationPredictor(llm_hard_case_review=True)
        ).recommend(batch_papers, limit=None, progress=emit_progress)
        enrichment_results = enrich_selected_arxiv_papers_with_affiliations(batch_result.papers)
        _emit_affiliation_enrichment_summary(enrichment_results)
        _write_recommendation_batch(
            work_dir=work_dir,
            batch_index=(processed_count // batch_size) + 1,
            start_index=processed_count,
            end_index=end_index,
            candidate_papers=batch_papers,
            recommended_papers=batch_result.papers,
        )
        state["processed_count"] = end_index
        state["status"] = (
            "recommendation_complete"
            if end_index >= total_count
            else "recommendation_in_progress"
        )
        _write_workflow_state(state_path, state)
        if end_index < total_count:
            _emit_resumable_incomplete(
                content_date=content_date,
                processed_count=end_index,
                total_count=total_count,
                state_path=state_path,
            )
            return 0

    candidate_papers = _load_workflow_candidate_papers(work_dir)
    recommended_papers = _load_workflow_recommended_papers(work_dir)
    report_artifacts = write_report(
        report_dir=work_dir,
        source_name="arXiv",
        papers=recommended_papers,
        command_name=_build_command_name(args),
        analysis_count=total_count,
    )
    _attach_candidate_papers_to_report(
        report_json_path=report_artifacts["json"],
        candidate_papers=candidate_papers,
    )
    _attach_recommendation_layers_to_report(
        report_artifacts=report_artifacts,
        candidate_papers=candidate_papers,
    )
    _snapshot_red_team_report(work_dir)

    review_dir = daily_dir / "review"
    review_result = _write_default_review_artifacts(
        args=args,
        report_dir=work_dir,
        candidate_papers=candidate_papers,
        output_dir=review_dir,
        resume_dir=daily_dir / "review-progress",
    )
    if _should_write_default_review(args) and review_result is None:
        state["status"] = "review_failed"
        state["review_artifact"] = str(review_dir / "summary.md")
        _write_workflow_state(state_path, state)
        raise CliInputError(
            f"蓝军审阅未成功完成，最终报告未生成；请检查 {review_dir / 'summary.md'} 后续跑"
        )
    if _should_write_default_review(args):
        _append_blue_team_review_to_report(
            report_artifacts=report_artifacts,
            review_json_path=review_dir / "result.json",
        )
    _publish_final_report(
        daily_dir=daily_dir,
        work_dir=work_dir,
        review_dir=review_dir,
    )
    state["status"] = "final_complete"
    state["final_report"] = str(daily_dir / "final-summary.md")
    _write_workflow_state(state_path, state)

    lines = [
        f"[OK] arXiv 最终报告已生成：{daily_dir / 'final-summary.md'}",
        f"[OK] latest 已同步：{ARTIFACTS_DIR / 'e2e' / 'arxiv' / 'latest' / 'summary.md'}",
    ]
    if review_result:
        lines.append(f"[OK] 大模型审阅已生成：{review_result.markdown_path}")
    emit_lines(*lines)
    return 0


def handle_import_dataset(args: argparse.Namespace) -> int:
    """Manually import one arXiv report run into the dataset repository."""
    _normalize_source_mode(args)
    if args.source_mode != "subscription-email" or not args.subscription_date:
        return print_cli_error(
            scope="arxiv.import-dataset",
            message="数据集导入只支持 Gmail subscription-email 日期报告",
            next_step="使用 `arxiv import-dataset --subscription-date YYYY-MM/MM-DD`",
        )
    try:
        report_dir = _dated_report_dir(args.subscription_date)
        report_payload = _load_dataset_import_report_payload(
            content_date=args.subscription_date,
            report_dir=report_dir,
        )
        recommended_papers = _papers_from_report_rows(_report_rows(report_payload, "papers"))
        candidate_papers = _papers_from_report_rows(_report_rows(report_payload, "candidate_papers"))
        review_json_path = _dated_review_json_path(args.subscription_date)
        _validate_dataset_import_review_artifact(
            content_date=args.subscription_date,
            review_json_path=review_json_path,
        )
        dataset_import_result = _write_dataset_import_artifacts(
            content_date=args.subscription_date,
            candidate_papers=candidate_papers,
            recommended_papers=recommended_papers,
            review_json_path=review_json_path,
        )
    except CliInputError as exc:
        return print_cli_error(
            scope="arxiv.import-dataset",
            message=str(exc),
            next_step=(
                f"先运行 `arxiv report --subscription-date {args.subscription_date} --fetch-all` "
                "生成分日报告和蓝军审阅，再手动执行 import-dataset"
            ),
        )
    emit_lines(_format_dataset_import_line(dataset_import_result))
    return 0 if dataset_import_result.import_status == "ok" else 1


def _attach_candidate_papers_to_report(
    *,
    report_json_path: Path,
    candidate_papers: list[Paper],
) -> None:
    try:
        payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliInputError(f"报告 JSON 无法解析，不能归档候选全集：{report_json_path}") from exc
    if not isinstance(payload, dict):
        raise CliInputError(f"报告 JSON 顶层不是对象：{report_json_path}")
    payload["candidate_papers"] = serialize_papers(candidate_papers)
    report_json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _attach_recommendation_layers_to_report(
    *,
    report_artifacts: dict[str, Path],
    candidate_papers: list[Paper],
) -> None:
    summary = _build_recommendation_layer_summary(candidate_papers)
    _append_recommendation_layer_markdown(report_artifacts["markdown"], summary)
    _append_recommendation_layer_stdout(report_artifacts["stdout"], summary)
    _merge_recommendation_layer_json(
        report_artifacts["json"],
        summary=summary,
        candidate_papers=candidate_papers,
    )


def _build_recommendation_layer_summary(candidate_papers: list[Paper]) -> dict[str, object]:
    analyzed_count = len(candidate_papers)
    broad_candidates = [
        paper for paper in candidate_papers if _prediction_tier(paper) in {"broad_positive", "strict_positive"}
    ]
    strict_candidates = [
        paper for paper in candidate_papers if _prediction_tier(paper) == "strict_positive"
    ]
    broad_only_candidates = [
        paper for paper in candidate_papers if _prediction_tier(paper) == "broad_positive"
    ]
    return {
        "selection_policy": (
            "日报推荐只采用 strict_positive；broad_positive 仅作为高召回候选，"
            "用于人工抽检、数据集沉淀和后续误差分析。"
        ),
        "analyzed_count": analyzed_count,
        "broad_positive_count": len(broad_candidates),
        "strict_positive_count": len(strict_candidates),
        "broad_only_count": len(broad_only_candidates),
        "broad_positive_rate": _format_rate(len(broad_candidates), analyzed_count),
        "strict_positive_rate": _format_rate(len(strict_candidates), analyzed_count),
        "broad_only_rate": _format_rate(len(broad_only_candidates), analyzed_count),
        "broad_by_label": _count_prediction_labels(broad_candidates, field_name="broad_preference_labels"),
        "strict_by_label": _count_prediction_labels(strict_candidates, field_name="preference_labels"),
    }


def _append_recommendation_layer_markdown(
    markdown_path: Path,
    summary: dict[str, object],
) -> None:
    lines = [
        "",
        "## 分层推荐口径",
        "",
        f"- 选择策略：{summary['selection_policy']}",
        f"- 分析候选：{summary['analyzed_count']}",
        (
            "- broad 高召回候选："
            f"{summary['broad_positive_count']}（{summary['broad_positive_rate']}）"
        ),
        (
            "- strict 日报推荐："
            f"{summary['strict_positive_count']}（{summary['strict_positive_rate']}）"
        ),
        f"- broad-only 待抽检：{summary['broad_only_count']}（{summary['broad_only_rate']}）",
        "",
        "### broad 子类分布",
        "",
        *_format_distribution_lines(summary["broad_by_label"]),
        "",
        "### strict 子类分布",
        "",
        *_format_distribution_lines(summary["strict_by_label"]),
        "",
    ]
    with markdown_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def _append_recommendation_layer_stdout(
    stdout_path: Path,
    summary: dict[str, object],
) -> None:
    line = (
        "[OK] 分层推荐："
        f"broad={summary['broad_positive_count']}，"
        f"strict={summary['strict_positive_count']}，"
        f"broad_only={summary['broad_only_count']}\n"
    )
    with stdout_path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _merge_recommendation_layer_json(
    json_path: Path,
    *,
    summary: dict[str, object],
    candidate_papers: list[Paper],
) -> None:
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict):
        return
    payload["recommendation_layers"] = summary
    payload["broad_candidate_papers"] = serialize_papers(
        [
            paper
            for paper in candidate_papers
            if _prediction_tier(paper) in {"broad_positive", "strict_positive"}
        ]
    )
    payload["broad_only_candidate_papers"] = serialize_papers(
        [paper for paper in candidate_papers if _prediction_tier(paper) == "broad_positive"]
    )
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _prediction_tier(paper: Paper) -> str:
    prediction = paper.raw_payload.get("evaluation_prediction")
    if not isinstance(prediction, dict):
        return "negative"
    tier = str(prediction.get("recommendation_tier", "") or "").strip()
    if tier:
        return tier
    if prediction.get("negative_tier") == "positive":
        return "strict_positive"
    if prediction.get("broad_negative_tier") == "positive":
        return "broad_positive"
    return "negative"


def _count_prediction_labels(papers: list[Paper], *, field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for paper in papers:
        prediction = paper.raw_payload.get("evaluation_prediction")
        if not isinstance(prediction, dict):
            continue
        labels = prediction.get(field_name)
        if not isinstance(labels, list):
            continue
        for raw_label in labels:
            label = str(raw_label).strip()
            if label:
                counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _format_rate(count: int, total: int) -> str:
    return f"{count / total:.1%}" if total else "0.0%"


def _format_distribution_lines(distribution: object) -> list[str]:
    if not isinstance(distribution, dict) or not distribution:
        return ["- 无"]
    return [f"- {key}：{value}" for key, value in distribution.items()]


def _archive_arxiv_report_run(
    *,
    content_date: str | None,
    report_dir: Path,
    review_dir: Path,
) -> dict[str, Path] | None:
    if not content_date:
        return None
    dated_report_dir = _dated_report_dir(content_date)
    _copy_artifact_dir(report_dir, dated_report_dir)
    if review_dir.exists():
        _copy_review_artifacts_into_daily_dir(review_dir, dated_report_dir)
    return {"daily_dir": dated_report_dir}


def _copy_artifact_dir(source_dir: Path, target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)


def _copy_review_artifacts_into_daily_dir(review_dir: Path, daily_dir: Path) -> None:
    review_files = {
        "summary.md": "review-summary.md",
        "result.json": "review-result.json",
        "stdout.txt": "review-stdout.txt",
    }
    for source_name, target_name in review_files.items():
        source_path = review_dir / source_name
        if source_path.exists():
            shutil.copyfile(source_path, daily_dir / target_name)


def _snapshot_red_team_report(report_dir: Path) -> None:
    files = {
        "summary.md": "red-team-summary.md",
        "result.json": "red-team-result.json",
        "stdout.txt": "red-team-stdout.txt",
        "result.csv": "red-team-result.csv",
    }
    for source_name, target_name in files.items():
        source_path = report_dir / source_name
        if source_path.exists():
            shutil.copyfile(source_path, report_dir / target_name)


def _validated_report_batch_size(args: argparse.Namespace) -> int:
    value = int(getattr(args, "batch_size", 100) or 100)
    if value <= 0:
        raise CliInputError("--batch-size 必须大于 0")
    return value


def _load_workflow_state(state_path: Path) -> dict[str, object]:
    if not state_path.exists():
        return {}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliInputError(f"分批状态文件无法解析：{state_path}") from exc
    if not isinstance(payload, dict):
        raise CliInputError(f"分批状态文件顶层不是对象：{state_path}")
    return payload


def _new_workflow_state(
    *,
    content_date: str,
    candidate_ids: list[str],
    batch_size: int,
) -> dict[str, object]:
    return {
        "status": "recommendation_in_progress",
        "content_date": content_date,
        "batch_size": batch_size,
        "total_count": len(candidate_ids),
        "processed_count": 0,
        "candidate_ids": candidate_ids,
    }


def _validate_workflow_state(
    *,
    state: dict[str, object],
    content_date: str,
    candidate_ids: list[str],
    batch_size: int,
) -> None:
    if str(state.get("content_date", "") or "") != content_date:
        raise CliInputError("分批状态日期与本次订阅日期不匹配")
    if int(state.get("batch_size", 0) or 0) != batch_size:
        raise CliInputError(
            "分批大小与已有进度不一致；请使用相同 --batch-size，"
            "或确认后追加 --reset-progress"
        )
    previous_ids = state.get("candidate_ids")
    if not isinstance(previous_ids, list) or [str(item) for item in previous_ids] != candidate_ids:
        raise CliInputError(
            "候选论文集合已变化；为避免游标错位，请确认后追加 --reset-progress 重跑"
        )


def _write_workflow_state(state_path: Path, state: dict[str, object]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_recommendation_batch(
    *,
    work_dir: Path,
    batch_index: int,
    start_index: int,
    end_index: int,
    candidate_papers: list[Paper],
    recommended_papers: list[Paper],
) -> None:
    batch_dir = work_dir / "recommendation-batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_path = batch_dir / f"batch-{batch_index:06d}.json"
    batch_path.write_text(
        json.dumps(
            {
                "batch_index": batch_index,
                "start_index": start_index,
                "end_index": end_index,
                "candidate_count": len(candidate_papers),
                "recommended_count": len(recommended_papers),
                "candidate_papers": serialize_papers(candidate_papers),
                "recommended_papers": serialize_papers(recommended_papers),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _load_workflow_candidate_papers(work_dir: Path) -> list[Paper]:
    rows: list[dict[str, object]] = []
    for payload in _load_recommendation_batch_payloads(work_dir):
        rows.extend(_list_dicts(payload.get("candidate_papers")))
    return _papers_from_report_rows(rows)


def _load_workflow_recommended_papers(work_dir: Path) -> list[Paper]:
    rows: list[dict[str, object]] = []
    for payload in _load_recommendation_batch_payloads(work_dir):
        rows.extend(_list_dicts(payload.get("recommended_papers")))
    papers = _papers_from_report_rows(rows)
    papers.sort(key=lambda item: (item.sampled_reason, item.title))
    return papers


def _load_recommendation_batch_payloads(work_dir: Path) -> list[dict[str, object]]:
    batch_dir = work_dir / "recommendation-batches"
    if not batch_dir.exists():
        raise CliInputError(f"找不到推荐批次目录：{batch_dir}")
    payloads: list[dict[str, object]] = []
    for batch_path in sorted(batch_dir.glob("batch-*.json")):
        try:
            payload = json.loads(batch_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CliInputError(f"推荐批次 JSON 无法解析：{batch_path}") from exc
        if not isinstance(payload, dict):
            raise CliInputError(f"推荐批次 JSON 顶层不是对象：{batch_path}")
        payloads.append(payload)
    if not payloads:
        raise CliInputError(f"推荐批次目录为空：{batch_dir}")
    return payloads


def _emit_resumable_incomplete(
    *,
    content_date: str,
    processed_count: int,
    total_count: int,
    state_path: Path,
) -> None:
    emit_lines(
        "[INCOMPLETE] arXiv 分批报告尚未完成",
        f"subscription_date: {content_date}",
        f"progress: {processed_count}/{total_count}",
        f"cursor: {state_path}",
        "next: 继续运行同一条 `py -m paper_analysis.cli.main arxiv report "
        f"--subscription-date {content_date} --fetch-all`",
        "final: 最终报告尚未生成，GitHub Issue 发布脚本应提醒续跑",
    )


def _emit_affiliation_enrichment_summary(results: list[object]) -> None:
    statuses = Counter(str(getattr(result, "status", "unknown")) for result in results)
    if not statuses:
        return
    summary = "，".join(f"{status}={count}" for status, count in sorted(statuses.items()))
    emit_progress(f"[arxiv] affiliation enrichment summary: {summary}")


def _publish_final_report(
    *,
    daily_dir: Path,
    work_dir: Path,
    review_dir: Path,
) -> None:
    required_work_files = {
        "summary.md": "final-summary.md",
        "result.json": "final-result.json",
        "result.csv": "final-result.csv",
        "stdout.txt": "final-stdout.txt",
        "red-team-summary.md": "red-team-summary.md",
        "red-team-result.json": "red-team-result.json",
        "red-team-result.csv": "red-team-result.csv",
        "red-team-stdout.txt": "red-team-stdout.txt",
    }
    for source_name, target_name in required_work_files.items():
        source_path = work_dir / source_name
        if not source_path.exists():
            raise CliInputError(f"最终报告门禁失败，缺少产物：{source_path}")
        shutil.copyfile(source_path, daily_dir / target_name)
    _copy_review_artifacts_into_daily_dir(review_dir, daily_dir)

    latest_dir = ARTIFACTS_DIR / "e2e" / "arxiv" / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    latest_dir.mkdir(parents=True, exist_ok=True)
    latest_files = {
        "final-summary.md": "summary.md",
        "final-result.json": "result.json",
        "final-result.csv": "result.csv",
        "final-stdout.txt": "stdout.txt",
        "red-team-summary.md": "red-team-summary.md",
        "red-team-result.json": "red-team-result.json",
        "red-team-result.csv": "red-team-result.csv",
        "red-team-stdout.txt": "red-team-stdout.txt",
        "review-summary.md": "review-summary.md",
        "review-result.json": "review-result.json",
        "review-stdout.txt": "review-stdout.txt",
    }
    for source_name, target_name in latest_files.items():
        source_path = daily_dir / source_name
        if source_path.exists():
            shutil.copyfile(source_path, latest_dir / target_name)


def _dated_report_dir(content_date: str) -> Path:
    month, day = _split_content_date(content_date)
    return ARTIFACTS_DIR / "e2e" / "arxiv" / "daily" / month / day


def _dated_review_json_path(content_date: str) -> Path:
    return _dated_report_dir(content_date) / "review-result.json"


def _split_content_date(content_date: str) -> tuple[str, str]:
    if "/" not in content_date:
        raise CliInputError(f"非法订阅日期：{content_date}。期望格式为 YYYY-MM/MM-DD")
    month, day = content_date.split("/", maxsplit=1)
    if not month or not day:
        raise CliInputError(f"非法订阅日期：{content_date}。期望格式为 YYYY-MM/MM-DD")
    return month, day


def _load_dataset_import_report_payload(
    *,
    content_date: str,
    report_dir: Path,
) -> dict[str, object]:
    report_json_path = report_dir / "result.json"
    if not report_json_path.exists():
        raise CliInputError(
            f"找不到分日报告产物：{report_json_path}。"
            f"请先运行 `arxiv report --subscription-date {content_date} --fetch-all`"
        )
    try:
        payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliInputError(f"分日报告 JSON 无法解析：{report_json_path}") from exc
    if not isinstance(payload, dict):
        raise CliInputError(f"分日报告 JSON 顶层不是对象：{report_json_path}")
    return payload


def _report_rows(payload: dict[str, object], field_name: str) -> list[dict[str, object]]:
    value = payload.get(field_name)
    if not isinstance(value, list) or not value:
        raise CliInputError(
            f"分日报告缺少 `{field_name}`。请先重跑 `arxiv report --subscription-date ... --fetch-all`。"
        )
    rows = [dict(item) for item in value if isinstance(item, dict)]
    if len(rows) != len(value):
        raise CliInputError(f"分日报告 `{field_name}` 包含非对象项，不能入库。")
    return rows


def _papers_from_report_rows(rows: list[dict[str, object]]) -> list[Paper]:
    return [_paper_from_report_row(row) for row in rows]


def _paper_from_report_row(row: dict[str, object]) -> Paper:
    year_value = _optional_int(row.get("year"))
    score_value = _float_value(row.get("score"))
    reasons_value = row.get("reasons")
    raw_payload_value = row.get("raw_payload")
    return Paper(
        paper_id=str(row.get("paper_id", "") or ""),
        title=str(row.get("title", "") or ""),
        abstract=str(row.get("abstract", "") or ""),
        source=str(row.get("source", "") or "arxiv"),
        venue=str(row.get("venue", "") or "arXiv"),
        authors=_split_serialized_list(row.get("authors")),
        tags=_split_serialized_list(row.get("tags")),
        organization=str(row.get("organization", "") or ""),
        published_at=str(row.get("published_at", "") or ""),
        year=year_value,
        acceptance_status=str(row.get("acceptance_status", "") or ""),
        primary_area=str(row.get("primary_area", "") or ""),
        topic=str(row.get("topic", "") or ""),
        keywords=_split_serialized_list(row.get("keywords")),
        pdf_url=str(row.get("pdf_url", "") or ""),
        project_url=str(row.get("project_url", "") or ""),
        code_url=str(row.get("code_url", "") or ""),
        openreview_url=str(row.get("openreview_url", "") or ""),
        sampled_reason=str(row.get("sampled_reason", "") or ""),
        score=score_value,
        reasons=[str(item) for item in reasons_value if isinstance(item, str)]
        if isinstance(reasons_value, list)
        else [],
        raw_payload=dict(raw_payload_value) if isinstance(raw_payload_value, dict) else {},
        source_path=str(row.get("source_path", "") or ""),
    )


def _split_serialized_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split("|") if item.strip()]


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _float_value(value: object) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def _write_dataset_import_artifacts(
    *,
    content_date: str,
    candidate_papers: list[Paper],
    recommended_papers: list[Paper],
    review_json_path: Path,
) -> ArxivDatasetImportResult:
    return build_and_import_arxiv_dataset_samples(
        content_date=content_date,
        candidate_papers=candidate_papers,
        recommended_papers=recommended_papers,
        review_json_path=review_json_path,
    )


def _validate_dataset_import_review_artifact(*, content_date: str, review_json_path: Path) -> None:
    if not review_json_path.exists():
        raise CliInputError(f"找不到蓝军审阅结果：{review_json_path}")
    try:
        review_payload = json.loads(review_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliInputError(f"蓝军审阅结果不是合法 JSON：{review_json_path}") from exc
    if not isinstance(review_payload, dict):
        raise CliInputError(f"蓝军审阅结果顶层不是对象：{review_json_path}")
    if review_payload.get("status") == "failed":
        raise CliInputError(f"蓝军审阅失败，不能入库：{review_payload.get('error', '')}")
    review_date = str(review_payload.get("content_date", "") or "")
    if review_date != content_date:
        raise CliInputError(
            f"蓝军审阅日期不匹配：期望 {content_date}，实际 {review_date or 'unknown'}"
        )


def _format_dataset_import_line(result: ArxivDatasetImportResult) -> str:
    if result.import_status == "ok":
        return (
            "[OK] 数据集导入完成："
            f"records={result.record_count}, "
            f"positive={result.positive_count}, "
            f"negative={result.negative_count}, "
            f"payload={result.payload_path}"
        )
    return (
        "[WARN] 数据集导入未完成："
        f"status={result.import_status}, artifact={result.summary_path}"
    )


def _write_default_review_artifacts(
    *,
    args: argparse.Namespace,
    report_dir: Path,
    candidate_papers: list[Paper],
    output_dir: Path | None = None,
    resume_dir: Path | None = None,
) -> LlmRecommendationReviewResult | None:
    if not _should_write_default_review(args):
        return None
    review_output_dir = output_dir or _review_output_dir()
    try:
        return LlmRecommendationReviewer().review(
            LlmRecommendationReviewRequest(
                source_name="arXiv",
                content_date=args.subscription_date,
                report_dir=report_dir,
                output_dir=review_output_dir,
                candidate_papers=candidate_papers,
                candidate_batch_size=_validated_report_batch_size(args),
                resume_dir=resume_dir,
                progress=emit_progress,
            )
        )
    except CliInputError as exc:
        write_review_failure_artifact(
            source_name="arXiv",
            content_date=args.subscription_date,
            output_dir=review_output_dir,
            message=str(exc),
        )
        return None


def _should_write_default_review(args: argparse.Namespace) -> bool:
    return args.source_mode == "subscription-email" and bool(args.subscription_date)


def _review_output_dir() -> Path:
    return ARTIFACTS_DIR / "reviews" / "arxiv" / "latest"


def _append_blue_team_review_to_report(
    *,
    report_artifacts: dict[str, Path],
    review_json_path: Path,
) -> None:
    if not review_json_path.exists():
        return
    try:
        review_payload = json.loads(review_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(review_payload, dict):
        return

    red_json_path = report_artifacts["json"].with_name("red-team-result.json")
    try:
        red_report_payload = json.loads(red_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(red_report_payload, dict):
        return

    sections = _build_merged_recommendation_sections(red_report_payload, review_payload)
    report_artifacts["markdown"].write_text(
        _render_merged_report_markdown(
            red_report_payload=red_report_payload,
            review_payload=review_payload,
            sections=sections,
        ),
        encoding="utf-8",
    )
    report_artifacts["stdout"].write_text(
        _render_merged_report_stdout(red_report_payload, review_payload, sections),
        encoding="utf-8",
    )
    merged_payload = dict(red_report_payload)
    merged_payload["report_kind"] = "merged_red_blue"
    merged_payload["red_team_report_artifact"] = str(red_json_path)
    merged_payload["blue_team_review"] = _compact_blue_team_payload(review_payload)
    merged_payload["blue_team_review_artifact"] = str(review_json_path)
    merged_payload["merged_recommendation_sections"] = sections
    report_artifacts["json"].write_text(
        json.dumps(merged_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_merged_recommendation_sections(
    red_report_payload: dict[str, object],
    review_payload: dict[str, object],
) -> dict[str, list[dict[str, object]]]:
    red_rows = _list_dicts(red_report_payload.get("papers"))
    red_by_id = {str(row.get("paper_id", "")): row for row in red_rows}
    candidate_rows = _list_dicts(red_report_payload.get("candidate_papers"))
    candidate_by_id = {str(row.get("paper_id", "")): row for row in candidate_rows}
    borderline = _list_dicts(review_payload.get("borderline_recommendations"))
    borderline_ids = {str(item.get("paper_id", "")) for item in borderline}
    false_positive = _list_dicts(review_payload.get("false_positives"))
    false_positive_ids = {str(item.get("paper_id", "")) for item in false_positive}

    shared_recommendations = [
        _merged_red_blue_item(row, review_payload)
        for row in red_rows
        if str(row.get("paper_id", "")) not in borderline_ids
        and str(row.get("paper_id", "")) not in false_positive_ids
    ]
    red_borderline = [
        _merged_red_blue_item(red_by_id.get(str(item.get("paper_id", "")), {}), review_payload)
        for item in borderline
    ]
    missed = [
        _merged_missed_item(
            item,
            candidate_by_id.get(str(item.get("paper_id", "")), {}),
        )
        for item in _list_dicts(review_payload.get("missed_recommendations"))
    ]
    return {
        "blue_and_red_recommendations": shared_recommendations,
        "red_recommendations_blue_borderline": red_borderline,
        "blue_missed_recommendations": missed,
    }


def _merged_red_blue_item(
    red_row: dict[str, object],
    review_payload: dict[str, object],
) -> dict[str, object]:
    paper_id = str(red_row.get("paper_id", ""))
    review_item = _review_item_by_id(review_payload, paper_id)
    return {
        "paper_id": paper_id,
        "title": red_row.get("title", ""),
        "abstract": red_row.get("abstract", ""),
        "authors": red_row.get("authors", ""),
        "tags": red_row.get("tags", ""),
        "category": red_row.get("sampled_reason", ""),
        "red_reason": _compact_red_reason(red_row),
        "blue_verdict": review_item.get("verdict", "keep") if review_item else "keep",
        "blue_reason": review_item.get("reason", "") if review_item else "",
        "confidence": review_item.get("confidence", "") if review_item else "",
        "pdf_url": red_row.get("pdf_url", ""),
    }


def _merged_missed_item(
    item: dict[str, object],
    candidate_row: dict[str, object],
) -> dict[str, object]:
    return {
        "paper_id": item.get("paper_id", ""),
        "title": item.get("title", ""),
        "abstract": candidate_row.get("abstract", ""),
        "authors": candidate_row.get("authors", ""),
        "tags": candidate_row.get("tags", ""),
        "category": item.get("category", ""),
        "blue_reason": item.get("reason", ""),
        "confidence": item.get("confidence", ""),
        "pdf_url": candidate_row.get("pdf_url", ""),
    }


def _review_item_by_id(
    review_payload: dict[str, object],
    paper_id: str,
) -> dict[str, object]:
    for item in _list_dicts(review_payload.get("recommended_reviews")):
        if str(item.get("paper_id", "")) == paper_id:
            return item
    return {}


def _compact_red_reason(row: dict[str, object]) -> str:
    reasons = row.get("reasons")
    if not isinstance(reasons, list):
        return ""
    compact = [
        str(reason).strip()
        for reason in reasons
        if str(reason).strip()
        and not str(reason).startswith("基于标题、摘要与关键词宽召回主标签为")
    ]
    return "；".join(compact[:2])


def _render_merged_report_markdown(
    *,
    red_report_payload: dict[str, object],
    review_payload: dict[str, object],
    sections: dict[str, list[dict[str, object]]],
) -> str:
    if review_payload.get("status") == "failed":
        return _render_failed_merged_markdown(red_report_payload, review_payload)
    lines = [
        "# arXiv 融合推荐报告",
        "",
        f"- 内容日期：{review_payload.get('content_date', '')}",
        f"- 红军推荐：{len(_list_dicts(red_report_payload.get('papers')))}",
        f"- 蓝军模型：{review_payload.get('model', '')}",
        f"- 蓝军误推荐：{review_payload.get('false_positive_count', 0)}",
        f"- 蓝军存疑：{review_payload.get('borderline_count', 0)}",
        f"- 蓝军漏推荐：{review_payload.get('missed_count', 0)}",
        "",
        "## 1. 蓝军推荐 + 红军推荐",
        "",
        *_render_merged_items(sections["blue_and_red_recommendations"], include_blue_reason=True),
        "",
        "## 2. 红军推荐 + 蓝军存疑",
        "",
        *_render_merged_items(
            sections["red_recommendations_blue_borderline"],
            include_blue_reason=True,
        ),
        "",
        "## 3. 蓝军漏推荐",
        "",
        *_render_missed_items(sections["blue_missed_recommendations"]),
        "",
        "## 独立报告",
        "",
        "- 红军主报告：`red-team-summary.md`",
        "- 蓝军审阅报告：`review-summary.md`",
        "",
    ]
    return "\n".join(lines)


def _render_failed_merged_markdown(
    red_report_payload: dict[str, object],
    review_payload: dict[str, object],
) -> str:
    lines = [
        "# arXiv 融合推荐报告",
        "",
        "- 状态：蓝军审阅失败，融合报告仅保留红军推荐摘要。",
        f"- 失败原因：{review_payload.get('error', 'unknown error')}",
        f"- 红军推荐：{len(_list_dicts(red_report_payload.get('papers')))}",
        "",
        "## 独立报告",
        "",
        "- 红军主报告：`red-team-summary.md`",
        "- 蓝军审阅报告：`review-summary.md`",
        "",
    ]
    return "\n".join(lines)


def _render_merged_items(
    items: list[dict[str, object]],
    *,
    include_blue_reason: bool,
) -> list[str]:
    if not items:
        return ["- 无"]
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        lines.append(f"### {index}. {item.get('title', '')}")
        lines.append(f"- 论文 ID：`{item.get('paper_id', '')}`")
        if item.get("authors"):
            lines.append(f"- 作者：{item.get('authors', '')}")
        if item.get("tags"):
            lines.append(f"- 主题标签：{item.get('tags', '')}")
        lines.append(f"- 推荐类别：{item.get('category', '') or '未分类'}")
        if item.get("abstract"):
            lines.append(f"- 摘要：{item.get('abstract', '')}")
        if item.get("red_reason"):
            lines.append(f"- 红军推荐依据：{item.get('red_reason')}")
        if include_blue_reason and item.get("blue_reason"):
            lines.append(
                f"- 蓝军意见：{item.get('blue_reason')}"
                f"（confidence={item.get('confidence', '')}）"
            )
        if item.get("pdf_url"):
            lines.append(f"- 链接：PDF: {item.get('pdf_url', '')}")
        lines.append("")
    return lines


def _render_missed_items(items: list[dict[str, object]]) -> list[str]:
    if not items:
        return ["- 无"]
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        lines.append(f"### {index}. {item.get('title', '')}")
        lines.append(f"- 论文 ID：`{item.get('paper_id', '')}`")
        if item.get("authors"):
            lines.append(f"- 作者：{item.get('authors', '')}")
        if item.get("tags"):
            lines.append(f"- 主题标签：{item.get('tags', '')}")
        lines.append(f"- 推荐类别：{item.get('category', '') or '未分类'}")
        if item.get("abstract"):
            lines.append(f"- 摘要：{item.get('abstract', '')}")
        lines.append(
            f"- 蓝军漏推荐依据：{item.get('blue_reason', '')}"
            f"（confidence={item.get('confidence', '')}）"
        )
        if item.get("pdf_url"):
            lines.append(f"- 链接：PDF: {item.get('pdf_url', '')}")
        lines.append("")
    return lines


def _render_merged_report_stdout(
    red_report_payload: dict[str, object],
    review_payload: dict[str, object],
    sections: dict[str, list[dict[str, object]]],
) -> str:
    if review_payload.get("status") == "failed":
        return (
            "[WARN] 蓝军审阅失败，融合报告仅保留红军推荐摘要："
            f"{review_payload.get('error', 'unknown error')}\n"
        )
    return (
        "[OK] 融合推荐报告："
        f"双方推荐 {len(sections['blue_and_red_recommendations'])}，"
        f"红军推荐蓝军存疑 {len(sections['red_recommendations_blue_borderline'])}，"
        f"蓝军漏推荐 {len(sections['blue_missed_recommendations'])}，"
        f"红军原推荐 {len(_list_dicts(red_report_payload.get('papers')))}\n"
    )


def _list_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _compact_blue_team_payload(review_payload: dict[str, object]) -> dict[str, object]:
    if review_payload.get("status") == "failed":
        return {
            "status": "failed",
            "error": review_payload.get("error", ""),
            "artifact": str(_review_output_dir() / "summary.md"),
        }
    return {
        "status": "completed",
        "model": review_payload.get("model", ""),
        "content_date": review_payload.get("content_date", ""),
        "false_positive_count": review_payload.get("false_positive_count", 0),
        "borderline_count": review_payload.get("borderline_count", 0),
        "missed_count": review_payload.get("missed_count", 0),
        "false_positives": review_payload.get("false_positives", []),
        "borderline_recommendations": review_payload.get("borderline_recommendations", []),
        "missed_recommendations": review_payload.get("missed_recommendations", []),
        "artifact": str(_review_output_dir() / "summary.md"),
    }


def _format_blue_team_items(value: object, *, include_category: bool) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["- 无"]
    lines: list[str] = []
    for raw_item in value[:10]:
        if not isinstance(raw_item, dict):
            continue
        paper_id = raw_item.get("paper_id", "")
        title = raw_item.get("title") or paper_id
        confidence = raw_item.get("confidence", "")
        reason = raw_item.get("reason", "")
        category = (
            f" | {raw_item.get('category', '')}"
            if include_category and raw_item.get("category")
            else ""
        )
        lines.append(f"- `{paper_id}` {title}{category} | confidence={confidence}：{reason}")
    return lines or ["- 无"]


def _run_pipeline(args: argparse.Namespace) -> tuple[list[Paper], PreferenceProfile]:
    try:
        return ArxivPipeline().run(
            args.input,
            args.preferences,
            source_mode=args.source_mode,
            subscription_date=args.subscription_date,
            categories=args.category,
            max_results=args.max_results,
            fetch_all=args.fetch_all,
        )
    except ValueError as exc:
        raise CliInputError(str(exc)) from exc


def _validate_subscription_delivery_args(args: argparse.Namespace) -> int | None:
    if not args.deliver_subscription:
        return None
    if args.source_mode not in {"subscription-api", "subscription-email"}:
        return print_cli_error(
            scope="arxiv.report",
            message="订阅投递模式只支持 --source-mode subscription-api 或 subscription-email",
            next_step="补充 --source-mode subscription-api 或 subscription-email 后重试",
        )
    if not args.subscription_date:
        return print_cli_error(
            scope="arxiv.report",
            message="订阅投递模式必须提供 --subscription-date",
            next_step="为 deliver-subscription 模式补充有效的 --subscription-date",
        )
    return None


def _build_command_name(args: argparse.Namespace) -> str:
    if args.source_mode not in {"subscription-api", "subscription-email"}:
        if getattr(args, "deliver_subscription", False):
            return "arxiv report --deliver-subscription"
        return "arxiv report"

    parts = [
        f"arxiv {args.arxiv_action}",
        f"--source-mode {args.source_mode}",
        f"--subscription-date {args.subscription_date}",
    ]
    if args.fetch_all:
        parts.append("--fetch-all")
    else:
        parts.append(f"--max-results {args.max_results}")
    parts.extend(f"--category {category}" for category in args.category)
    if getattr(args, "deliver_subscription", False):
        parts.append("--deliver-subscription")
    return " ".join(parts)


def _normalize_source_mode(args: argparse.Namespace) -> None:
    if args.source_mode == "fixture" and args.subscription_date:
        args.source_mode = "subscription-email"
