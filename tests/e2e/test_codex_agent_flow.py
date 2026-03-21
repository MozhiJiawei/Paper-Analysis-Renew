from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from paper_analysis.testing.case_metadata import CaseMetadataMixin


ROOT_DIR = Path(__file__).resolve().parents[2]


class CodexAgentE2ETests(CaseMetadataMixin, unittest.TestCase):
    def test_codex_discovers_repo_skill_and_completes_arxiv_report_from_natural_language(self) -> None:
        """验证 Codex 能用自然语言发现 repo-local skill 并完成最简单的 arXiv 联网报告任务。"""

        self.set_case_source_label("codex arxiv e2e")
        self.set_failure_check_description(
            "若 Codex 未读取 repo-local skill、未执行 arxiv report、CLI 返回码非 0，或关键产物缺失，则判定失败。"
        )
        self.record_step("准备 Codex 黑盒 e2e：prompt 不显式提及 skill，只描述人类任务目标。")

        codex_path = shutil.which("codex")
        self.assertTrue(codex_path, "未找到 codex CLI，无法执行 Codex 黑盒 e2e。")

        report_dir = ROOT_DIR / "artifacts" / "e2e" / "arxiv" / "latest"
        if report_dir.exists():
            shutil.rmtree(report_dir)
        self.record_step("清理旧的 arXiv e2e 产物目录，避免历史文件造成假阳性。")

        test_output_dir = ROOT_DIR / "artifacts" / "test-output" / "codex-arxiv-e2e"
        if test_output_dir.exists():
            shutil.rmtree(test_output_dir)
        test_output_dir.mkdir(parents=True, exist_ok=True)
        events_path = test_output_dir / "events.jsonl"
        final_message_path = test_output_dir / "final-message.txt"
        self.add_case_artifact(str(events_path))
        self.add_case_artifact(str(final_message_path))

        prompt = (
            "请按这个仓库现有的 arXiv 联网报告链路，为 2025-09/09-01 生成一份报告产物。"
            "不要修改代码，不要新增临时脚本，不要手工加工中间 JSON。"
            "完成后只回复最终生成的 markdown 报告路径。"
        )
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        self.record_step("使用 codex exec --json 运行自然语言任务，并显式关闭沙箱以允许真实联网 arXiv e2e。")

        result = subprocess.run(
            [
                codex_path,
                "exec",
                "--json",
                "--ephemeral",
                "--dangerously-bypass-approvals-and-sandbox",
                "-C",
                str(ROOT_DIR),
                prompt,
            ],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
            timeout=600,
        )
        events_path.write_text(result.stdout, encoding="utf-8")
        self.record_step(f"Codex exec 完成，返回码={result.returncode}。")
        self.assertEqual(0, result.returncode, msg=result.stderr or result.stdout)

        events = _parse_jsonl_events(result.stdout)
        self.assertTrue(events, "Codex exec 没有返回可解析的 JSONL 事件。")

        skill_reads = [
            event
            for event in events
            if event.get("type") == "item.completed"
            and event.get("item", {}).get("type") == "command_execution"
            and ".codex/skills/paper-analysis/SKILL.md" in event.get("item", {}).get("command", "")
        ]
        self.record_step(f"检查事件流中是否读取 repo-local skill，命中 {len(skill_reads)} 次。")
        self.assertTrue(skill_reads, "Codex 没有在事件流中读取 repo-local paper-analysis skill。")

        arxiv_report_runs = [
            event
            for event in events
            if event.get("type") == "item.completed"
            and event.get("item", {}).get("type") == "command_execution"
            and "paper_analysis.cli.main arxiv report" in event.get("item", {}).get("command", "")
            and "--source-mode subscription-api" in event.get("item", {}).get("command", "")
            and "--subscription-date 2025-09/09-01" in event.get("item", {}).get("command", "")
            and event.get("item", {}).get("exit_code") == 0
        ]
        self.record_step(f"检查事件流中是否成功执行联网 arxiv report，命中 {len(arxiv_report_runs)} 次。")
        self.assertTrue(arxiv_report_runs, "Codex 没有成功执行预期的联网 arxiv report 命令。")

        final_message = _last_agent_message(events)
        final_message_path.write_text(final_message, encoding="utf-8")
        self.record_step("记录 Codex 最终回复，并检查它是否返回了约定的 markdown 路径。")
        self.assertIn(str(report_dir / "summary.md"), final_message)

        self.add_case_artifact(str(report_dir / "summary.md"))
        self.add_case_artifact(str(report_dir / "result.json"))
        self.add_case_artifact(str(report_dir / "result.csv"))
        self.add_case_artifact(str(report_dir / "stdout.txt"))
        self.assertTrue((report_dir / "summary.md").exists())
        self.assertTrue((report_dir / "result.json").exists())
        self.assertTrue((report_dir / "result.csv").exists())
        self.assertTrue((report_dir / "stdout.txt").exists())
        self.record_step("校验 Codex 驱动产生的 arXiv 报告产物完整存在。")

        payload = json.loads((report_dir / "result.json").read_text(encoding="utf-8"))
        self.record_step(f"读取 result.json，确认 source={payload['source']}，count={payload['count']}。")
        self.assertEqual("arXiv", payload["source"])
        self.assertGreaterEqual(payload["count"], 1)
        self.assertIn(
            "--subscription-date 2025-09/09-01",
            (report_dir / "summary.md").read_text(encoding="utf-8"),
        )


def _parse_jsonl_events(content: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _last_agent_message(events: list[dict[str, object]]) -> str:
    messages: list[str] = []
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event.get("item", {})
        if not isinstance(item, dict):
            continue
        if item.get("type") != "agent_message":
            continue
        messages.append(str(item.get("text", "")))
    return messages[-1] if messages else ""


if __name__ == "__main__":
    unittest.main()
