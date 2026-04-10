from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from paper_analysis.domain.email_delivery import (
    EmailConfig,
    EmailConfigError,
    EmailSendResult,
)
from paper_analysis.domain.delivery_run import SubscriptionDeliveryRequest
from paper_analysis.domain.paper import Paper
from paper_analysis.services.arxiv_subscription_delivery import deliver_subscription_run
from paper_analysis.services.report_writer import write_report


ROOT_DIR = Path(__file__).resolve().parents[2]


class ArxivSubscriptionDeliveryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_root = ROOT_DIR / "artifacts" / "test-output" / "subscription-delivery"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.latest_report_dir = self.test_root / "e2e" / "arxiv" / "latest"
        self.runs_root_dir = self.test_root / "subscriptions" / "arxiv" / "runs"
        self.site_dir = self.test_root / "subscriptions" / "arxiv" / "site"

    def test_delivery_success_publishes_email_and_site(self) -> None:
        """验证订阅投递成功时会归档运行快照、发送邮件并发布 latest/history 页面。"""

        artifacts = write_report(
            report_dir=self.latest_report_dir,
            source_name="arXiv",
            papers=[self._paper("p-1", "First"), self._paper("p-2", "Second")],
            command_name="arxiv report --deliver-subscription",
        )

        result = deliver_subscription_run(
            SubscriptionDeliveryRequest(
                papers=[self._paper("p-1", "First"), self._paper("p-2", "Second")],
                fetched_count=5,
                subscription_date="2026-04/04-10",
                command_name="arxiv report --deliver-subscription",
                latest_report_dir=self.latest_report_dir,
                report_artifacts=artifacts,
                runs_root_dir=self.runs_root_dir,
                site_dir=self.site_dir,
            ),
            load_email_config=lambda: EmailConfig(
                host="smtp.qq.com",
                port=587,
                username="sender@qq.com",
                password="auth-code",  # noqa: S106 - test fixture
                from_address="sender@qq.com",
                to_address="receiver@example.com",
            ),
            send_email=self._successful_send,
        )

        self.assertEqual("sent", result.status)
        self.assertTrue(Path(result.snapshot_path).exists())
        self.assertTrue(Path(result.latest_page_path).exists())
        self.assertTrue(Path(result.index_page_path).exists())

        snapshot = json.loads(Path(result.snapshot_path).read_text(encoding="utf-8"))
        self.assertEqual(5, snapshot["fetched_count"])
        self.assertEqual(2, snapshot["recommended_count"])
        self.assertEqual("sent", snapshot["steps"]["email"]["status"])
        self.assertEqual("published", snapshot["steps"]["site"]["status"])

        latest_html = Path(result.latest_page_path).read_text(encoding="utf-8")
        index_html = Path(result.index_page_path).read_text(encoding="utf-8")
        self.assertIn("First", latest_html)
        self.assertIn("解码策略优化", latest_html)
        self.assertIn("摘要：abstract", latest_html)
        self.assertNotIn("原因：", latest_html)
        self.assertIn("订阅最新报告", latest_html)
        self.assertIn("history", (self.site_dir / "history.json").name)
        self.assertIn("receiver@example.com", snapshot["recipient"])
        self.assertIn("订阅历史列表", index_html)
        email_text = (Path(result.snapshot_path).parent / "email.txt").read_text(encoding="utf-8")
        self.assertIn("子类：解码策略优化", email_text)
        self.assertIn("组织：OpenAI", email_text)
        self.assertIn("摘要：abstract", email_text)

    def test_delivery_still_renders_no_hits_email_and_site(self) -> None:
        """验证 0 命中时仍然生成邮件快照并发布声明“今日无推荐论文”的页面。"""

        artifacts = write_report(
            report_dir=self.latest_report_dir,
            source_name="arXiv",
            papers=[],
            command_name="arxiv report --deliver-subscription",
        )

        result = deliver_subscription_run(
            SubscriptionDeliveryRequest(
                papers=[],
                fetched_count=4,
                subscription_date="2026-04/04-10",
                command_name="arxiv report --deliver-subscription",
                latest_report_dir=self.latest_report_dir,
                report_artifacts=artifacts,
                runs_root_dir=self.runs_root_dir,
                site_dir=self.site_dir,
            ),
            load_email_config=lambda: EmailConfig(
                host="smtp.qq.com",
                port=587,
                username="sender@qq.com",
                password="auth-code",  # noqa: S106 - test fixture
                from_address="sender@qq.com",
                to_address="receiver@example.com",
            ),
            send_email=self._successful_send,
        )

        self.assertEqual("sent", result.status)
        latest_html = Path(result.latest_page_path).read_text(encoding="utf-8")
        email_text = (Path(result.snapshot_path).parent / "email.txt").read_text(encoding="utf-8")
        self.assertIn("今日无推荐论文", latest_html)
        self.assertIn("今日无推荐论文", email_text)

    def test_delivery_config_failure_keeps_snapshot_and_skips_site_publish(self) -> None:
        """验证邮件配置失败时返回结构化失败，并且不会推进 latest 页面。"""

        artifacts = write_report(
            report_dir=self.latest_report_dir,
            source_name="arXiv",
            papers=[self._paper("p-1", "Only")],
            command_name="arxiv report --deliver-subscription",
        )

        result = deliver_subscription_run(
            SubscriptionDeliveryRequest(
                papers=[self._paper("p-1", "Only")],
                fetched_count=1,
                subscription_date="2026-04/04-10",
                command_name="arxiv report --deliver-subscription",
                latest_report_dir=self.latest_report_dir,
                report_artifacts=artifacts,
                runs_root_dir=self.runs_root_dir,
                site_dir=self.site_dir,
            ),
            load_email_config=self._raise_missing_config,
            send_email=self._successful_send,
        )

        self.assertEqual("failed", result.status)
        self.assertEqual("skipped", result.site_status)
        self.assertFalse((self.site_dir / "latest.html").exists())
        snapshot = json.loads(Path(result.snapshot_path).read_text(encoding="utf-8"))
        self.assertEqual("failed", snapshot["steps"]["email"]["status"])
        self.assertEqual("skipped", snapshot["steps"]["site"]["status"])
        self.assertIn("SMTP_HOST", result.summary)

    def _paper(self, paper_id: str, title: str) -> Paper:
        return Paper(
            paper_id=paper_id,
            title=title,
            abstract="abstract",
            source="arxiv",
            venue="arXiv",
            authors=["Ada"],
            tags=["cs.AI"],
            organization="OpenAI",
            published_at="2026-04-10",
            sampled_reason="解码策略优化",
            pdf_url=f"https://example.com/{paper_id}.pdf",
            reasons=["推理加速子类：解码策略优化"],
        )

    def _successful_send(self, config: EmailConfig, payload: object, **_: object) -> EmailSendResult:
        self.assertEqual("receiver@example.com", config.to_address)
        return EmailSendResult.success(
            recipient="receiver@example.com",
            message_id="<message-id>",
            eml_path=str(self.test_root / "message.eml"),
        )

    def _raise_missing_config(self) -> EmailConfig:
        raise EmailConfigError("缺少 SMTP 配置：SMTP_HOST")


if __name__ == "__main__":
    unittest.main()
