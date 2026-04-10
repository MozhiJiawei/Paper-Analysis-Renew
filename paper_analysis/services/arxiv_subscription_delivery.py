"""Delivery orchestration for arXiv subscription runs."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from paper_analysis.domain.delivery_run import (
    DeliveryExecutionResult,
    DeliveryPaperRecord,
    DeliveryRunSnapshot,
    DeliveryStepState,
    SubscriptionDeliveryRequest,
    utc_now_isoformat,
)
from paper_analysis.domain.email_delivery import (
    EmailConfigError,
    EmailMessagePayload,
    load_email_config_from_env,
)
from paper_analysis.services.arxiv_subscription_site_writer import publish_subscription_site
from paper_analysis.services.email_sender import send_email_message
from paper_analysis.services.report_writer import serialize_papers

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from paper_analysis.domain.email_delivery import EmailConfig, EmailSendResult

HISTORY_LIMIT = 30


def deliver_subscription_run(
    request: SubscriptionDeliveryRequest,
    load_email_config: Callable[[], EmailConfig] = load_email_config_from_env,
    send_email: Callable[..., EmailSendResult] = send_email_message,
) -> DeliveryExecutionResult:
    """Archive one run, send the email, and publish the subscription site."""
    run_id = _build_run_id(request.subscription_date)
    archive_dir = request.runs_root_dir / run_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = archive_dir / "run.json"
    _archive_report_artifacts(request.report_artifacts, archive_dir / "report")

    try:
        email_config = load_email_config()
    except EmailConfigError as exc:
        snapshot = _build_snapshot(
            request=request,
            recipient="",
            run_id=run_id,
            archive_dir=archive_dir,
        )
        snapshot.steps["email"] = _step_state("failed", str(exc), {"error_type": exc.error_type})
        snapshot.steps["site"] = _step_state("skipped", "邮件配置未就绪，未发布 latest 页面。")
        _write_snapshot(snapshot_path, snapshot)
        return DeliveryExecutionResult(
            status="failed",
            summary=str(exc),
            next_step="设置 SMTP_HOST、SMTP_PORT、SMTP_USERNAME、SMTP_PASSWORD、SMTP_FROM、SMTP_TO 后重试",
            snapshot_path=str(snapshot_path),
            run_id=run_id,
            email_status="failed",
            site_status="skipped",
        )

    snapshot = _build_snapshot(
        request=request,
        recipient=email_config.to_address,
        run_id=run_id,
        archive_dir=archive_dir,
    )
    text_body, html_body = _render_email_bodies(snapshot)
    (archive_dir / "email.txt").write_text(text_body, encoding="utf-8")
    (archive_dir / "email.html").write_text(html_body, encoding="utf-8")
    _write_snapshot(snapshot_path, snapshot)

    email_result = send_email(
        email_config,
        EmailMessagePayload(
            subject=_build_email_subject(snapshot),
            text_body=text_body,
            html_body=html_body,
            recipient=email_config.to_address,
            metadata={
                "Run-Id": snapshot.run_id,
                "Command": "arxiv.report.delivery",
                "Subscription-Date": snapshot.subscription_date,
            },
        ),
        eml_output_path=archive_dir / "message.eml",
    )
    (archive_dir / "email-result.json").write_text(
        json.dumps(
            {
                "status": email_result.status,
                "recipient": email_result.recipient,
                "sent_at": email_result.sent_at,
                "error_type": email_result.error_type,
                "error_summary": email_result.error_summary,
                "message_id": email_result.message_id,
                "eml_path": email_result.eml_path,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if email_result.status != "sent":
        snapshot.steps["email"] = _step_state(
            "failed",
            email_result.error_summary or "邮件发送失败。",
            {
                "recipient": email_result.recipient,
                "error_type": email_result.error_type,
                "eml_path": email_result.eml_path,
            },
        )
        snapshot.steps["site"] = _step_state("skipped", "邮件发送失败，按约定不推进 latest 页面。")
        _write_snapshot(snapshot_path, snapshot)
        return DeliveryExecutionResult(
            status="failed",
            summary=email_result.error_summary or "邮件发送失败",
            next_step="检查邮件配置、网络连通性与运行归档中的 email-result.json",
            snapshot_path=str(snapshot_path),
            run_id=run_id,
            email_status="failed",
            site_status="skipped",
        )

    snapshot.steps["email"] = _step_state(
        "sent",
        f"邮件已发送到 {email_result.recipient}。",
        {
            "recipient": email_result.recipient,
            "sent_at": email_result.sent_at,
            "message_id": email_result.message_id,
            "eml_path": email_result.eml_path,
        },
    )
    _write_snapshot(snapshot_path, snapshot)

    try:
        latest_page_path, index_page_path, history_path = publish_subscription_site(
            snapshot=snapshot,
            archive_dir=archive_dir,
            site_dir=request.site_dir,
            history_limit=HISTORY_LIMIT,
        )
    except (OSError, json.JSONDecodeError) as exc:
        snapshot.steps["site"] = _step_state("failed", f"订阅站点发布失败：{exc}")
        _write_snapshot(snapshot_path, snapshot)
        return DeliveryExecutionResult(
            status="failed",
            summary=f"订阅站点发布失败：{exc}",
            next_step="检查 subscriptions 站点目录权限、history.json 内容与运行归档中的 latest/index 页面快照",
            snapshot_path=str(snapshot_path),
            run_id=run_id,
            email_status="sent",
            site_status="failed",
        )

    snapshot.steps["site"] = _step_state(
        "published",
        "最新页与历史列表已发布。",
        {
            "latest_page_path": str(latest_page_path),
            "index_page_path": str(index_page_path),
            "history_path": str(history_path),
        },
    )
    _write_snapshot(snapshot_path, snapshot)
    return DeliveryExecutionResult(
        status="sent",
        summary=f"订阅投递完成，邮件已发送到 {email_result.recipient}。",
        snapshot_path=str(snapshot_path),
        run_id=run_id,
        email_status="sent",
        site_status="published",
        latest_page_path=str(latest_page_path),
        index_page_path=str(index_page_path),
    )


def _build_snapshot(
    *,
    request: SubscriptionDeliveryRequest,
    recipient: str,
    run_id: str,
    archive_dir: Path,
) -> DeliveryRunSnapshot:
    serialized_papers = serialize_papers(request.papers)
    delivery_papers = [
        DeliveryPaperRecord(
            paper_id=str(item.get("paper_id", "")),
            title=str(item.get("title", "")),
            abstract=str(item.get("abstract", "")),
            source=str(item.get("source", "")),
            venue=str(item.get("venue", "")),
            authors=str(item.get("authors", "")),
            organization=str(item.get("organization", "")),
            published_at=str(item.get("published_at", "")),
            tags=str(item.get("tags", "")),
            sampled_reason=str(item.get("sampled_reason", "")),
            reasons=_serialize_reasons(item.get("reasons", [])),
            pdf_url=str(item.get("pdf_url", "")),
            project_url=str(item.get("project_url", "")),
            code_url=str(item.get("code_url", "")),
            openreview_url=str(item.get("openreview_url", "")),
        )
        for item in serialized_papers
    ]
    return DeliveryRunSnapshot(
        run_id=run_id,
        source="arXiv",
        subscription_date=request.subscription_date,
        generated_at=utc_now_isoformat(),
        command_name=request.command_name,
        fetched_count=request.fetched_count,
        recommended_count=len(request.papers),
        recipient=recipient,
        archive_dir=str(archive_dir),
        latest_report_dir=str(request.latest_report_dir),
        site_dir=str(request.site_dir),
        papers=delivery_papers,
        steps={
            "report": _step_state("completed", "基础报告已生成并归档。"),
            "email": _step_state("pending", "等待发送邮件。"),
            "site": _step_state("pending", "等待发布 latest 页面与历史列表。"),
        },
    )


def _archive_report_artifacts(report_artifacts: dict[str, Path], archive_report_dir: Path) -> None:
    archive_report_dir.mkdir(parents=True, exist_ok=True)
    for artifact_path in report_artifacts.values():
        shutil.copyfile(artifact_path, archive_report_dir / artifact_path.name)


def _build_run_id(subscription_date: str) -> str:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
    safe_subscription_date = subscription_date.replace("/", "-")
    return f"{timestamp}-{safe_subscription_date}"


def _build_email_subject(snapshot: DeliveryRunSnapshot) -> str:
    return (
        f"arXiv 订阅报告 {snapshot.subscription_date} | "
        f"{snapshot.recommended_count} 篇推荐 / {snapshot.fetched_count} 篇抓取"
    )


def _render_email_bodies(snapshot: DeliveryRunSnapshot) -> tuple[str, str]:
    summary_lines = [
        f"订阅日期：{snapshot.subscription_date}",
        f"运行时间：{snapshot.generated_at}",
        f"抓取总数：{snapshot.fetched_count}",
        f"推荐命中：{snapshot.recommended_count}",
        "",
    ]
    if snapshot.papers:
        summary_lines.append("推理加速推荐列表：")
        for index, paper in enumerate(snapshot.papers, start=1):
            paper_lines = [
                f"{index}. {paper.title}",
                f"   子类：{paper.sampled_reason or '未分类'}",
                f"   作者：{paper.authors or '未知'}",
            ]
            if paper.organization:
                paper_lines.append(f"   组织：{paper.organization}")
            paper_lines.extend(
                [
                    f"   发表时间：{paper.published_at or '未知'}",
                    f"   摘要：{paper.abstract or '无'}",
                    f"   PDF：{paper.pdf_url or '无'}",
                ]
            )
            summary_lines.extend(paper_lines)
    else:
        summary_lines.append("今日无推荐论文，但任务已成功运行。")

    html_lines = [
        "<html><body>",
        "<h1>arXiv 订阅报告</h1>",
        f"<p>订阅日期：<strong>{snapshot.subscription_date}</strong></p>",
        f"<p>运行时间：{snapshot.generated_at}</p>",
        f"<p>抓取总数：{snapshot.fetched_count}；推荐命中：{snapshot.recommended_count}</p>",
    ]
    if snapshot.papers:
        html_lines.append("<ol>")
        html_lines.extend(
            [
                "<li>"
                f"<strong>{paper.title}</strong><br/>"
                f"子类：{paper.sampled_reason or '未分类'}<br/>"
                f"作者：{paper.authors or '未知'}<br/>"
                + (f"组织：{paper.organization}<br/>" if paper.organization else "")
                + f"发表时间：{paper.published_at or '未知'}<br/>"
                + f"摘要：{paper.abstract or '无'}<br/>"
                f"PDF：{paper.pdf_url or '无'}"
                "</li>"
                for paper in snapshot.papers
            ]
        )
        html_lines.append("</ol>")
    else:
        html_lines.append("<p>今日无推荐论文，但任务已成功运行。</p>")
    html_lines.append("</body></html>")
    return "\n".join(summary_lines).strip() + "\n", "\n".join(html_lines)


def _step_state(status: str, summary: str, details: dict[str, object] | None = None) -> DeliveryStepState:
    return DeliveryStepState(
        status=status,
        summary=summary,
        updated_at=utc_now_isoformat(),
        details={} if details is None else details,
    )


def _write_snapshot(snapshot_path: Path, snapshot: DeliveryRunSnapshot) -> None:
    snapshot_path.write_text(
        json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _serialize_reasons(raw_reasons: object) -> list[str]:
    if not isinstance(raw_reasons, list):
        return []
    return [str(reason) for reason in raw_reasons if isinstance(reason, str)]
