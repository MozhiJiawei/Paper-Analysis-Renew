"""CLI commands for the arXiv fetch and report workflow."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from paper_analysis.cli.common import CliInputError, emit_lines, emit_progress, print_cli_error
from paper_analysis.domain.delivery_run import SubscriptionDeliveryRequest
from paper_analysis.domain.email_delivery import EmailConfigError
from paper_analysis.domain.paper import Paper
from paper_analysis.services.arxiv_dataset_import import (
    ArxivDatasetImportResult,
    build_and_import_arxiv_dataset_samples,
)
from paper_analysis.services.arxiv_pipeline import ArxivPipeline
from paper_analysis.services.arxiv_subscription_delivery import deliver_subscription_run
from paper_analysis.services.llm_recommendation_reviewer import (
    LlmRecommendationReviewer,
    LlmRecommendationReviewRequest,
    LlmRecommendationReviewResult,
    write_review_failure_artifact,
)
from paper_analysis.services.report_writer import serialize_papers, write_report
from paper_analysis.shared.paths import ARTIFACTS_DIR

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

    try:
        result = ArxivPipeline().run_with_details(
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
) -> LlmRecommendationReviewResult | None:
    if not _should_write_default_review(args):
        return None
    try:
        return LlmRecommendationReviewer().review(
            LlmRecommendationReviewRequest(
                source_name="arXiv",
                content_date=args.subscription_date,
                report_dir=report_dir,
                output_dir=_review_output_dir(),
                candidate_papers=candidate_papers,
                progress=emit_progress,
            )
        )
    except CliInputError as exc:
        write_review_failure_artifact(
            source_name="arXiv",
            content_date=args.subscription_date,
            output_dir=_review_output_dir(),
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

    _append_blue_team_markdown(report_artifacts["markdown"], review_payload)
    _append_blue_team_stdout(report_artifacts["stdout"], review_payload)
    _merge_blue_team_json(report_artifacts["json"], review_payload)


def _append_blue_team_markdown(markdown_path: Path, review_payload: dict[str, object]) -> None:
    lines = ["", "## 蓝军审阅", ""]
    if review_payload.get("status") == "failed":
        lines.extend(
            [
                "- 状态：失败",
                f"- 失败原因：{review_payload.get('error', 'unknown error')}",
                "- 下一步：检查 OpenRouter 配置或模型响应后重新运行 arxiv report。",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"- 模型：{review_payload.get('model', '')}",
                f"- 误推荐：{review_payload.get('false_positive_count', 0)}",
                f"- 边界推荐：{review_payload.get('borderline_count', 0)}",
                f"- 漏推荐：{review_payload.get('missed_count', 0)}",
                "",
                "### 疑似误推荐",
                "",
                *_format_blue_team_items(
                    review_payload.get("false_positives"),
                    include_category=False,
                ),
                "",
                "### 边界推荐",
                "",
                *_format_blue_team_items(
                    review_payload.get("borderline_recommendations"),
                    include_category=False,
                ),
                "",
                "### 疑似漏推荐",
                "",
                *_format_blue_team_items(
                    review_payload.get("missed_recommendations"),
                    include_category=True,
                ),
                "",
                f"详细审阅产物：`{_review_output_dir() / 'summary.md'}`",
                "",
            ]
        )
    with markdown_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def _append_blue_team_stdout(stdout_path: Path, review_payload: dict[str, object]) -> None:
    if review_payload.get("status") == "failed":
        line = f"[WARN] 蓝军审阅失败：{review_payload.get('error', 'unknown error')}\n"
    else:
        line = (
            "[OK] 蓝军审阅："
            f"误推荐 {review_payload.get('false_positive_count', 0)}，"
            f"边界 {review_payload.get('borderline_count', 0)}，"
            f"漏推荐 {review_payload.get('missed_count', 0)}\n"
        )
    with stdout_path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _merge_blue_team_json(json_path: Path, review_payload: dict[str, object]) -> None:
    try:
        report_payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(report_payload, dict):
        return
    report_payload["blue_team_review"] = _compact_blue_team_payload(review_payload)
    json_path.write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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
