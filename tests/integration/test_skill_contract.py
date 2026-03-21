from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SKILL_PATH = ROOT_DIR / ".codex" / "skills" / "paper-analysis" / "SKILL.md"
OPENAI_YAML_PATH = ROOT_DIR / ".codex" / "skills" / "paper-analysis" / "agents" / "openai.yaml"
ROUTING_DOC_PATH = ROOT_DIR / ".codex" / "skills" / "paper-analysis" / "references" / "natural-language-routing.md"
QUICKSTART_PATH = ROOT_DIR / "docs" / "agent-guide" / "quickstart.md"
COMMAND_SURFACE_PATH = ROOT_DIR / "docs" / "agent-guide" / "command-surface.md"
ROUTING_FIXTURE_PATH = ROOT_DIR / "tests" / "fixtures" / "agent" / "natural_language_routing.json"
TESTING_QUALITY_PATH = ROOT_DIR / "docs" / "engineering" / "testing-and-quality.md"


def _read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_frontmatter(markdown: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", markdown, re.DOTALL)
    if not match:
        return {}

    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


class SkillContractTests(unittest.TestCase):
    def test_skill_frontmatter_exposes_discoverable_metadata(self) -> None:
        """验证 repo-local skill 具备 Codex 原生发现所需的最小元数据。"""

        markdown = _read_utf8(SKILL_PATH)
        frontmatter = _parse_frontmatter(markdown)

        self.assertEqual("paper-analysis", frontmatter.get("name"))
        description = frontmatter.get("description", "")
        self.assertIn("conference", description)
        self.assertIn("arxiv", description)
        self.assertIn("quality", description)
        self.assertIn("report", description)
        self.assertIn("recommend", description)

    def test_openai_metadata_file_exists_and_matches_skill_surface(self) -> None:
        """验证 skill 补齐了 agents/openai.yaml 元数据层。"""

        content = _read_utf8(OPENAI_YAML_PATH)

        self.assertIn('display_name: "Paper Analysis"', content)
        self.assertIn("conference", content)
        self.assertIn("arxiv", content)
        self.assertIn("quality", content)
        self.assertIn("report", content)
        self.assertNotIn("recommend namespace.", content.replace("do not invent a recommend namespace.", ""))

    def test_skill_references_exist_and_are_utf8(self) -> None:
        """验证 skill 引用的关键文档存在且可按 UTF-8 读取。"""

        expected_paths = [
            ROUTING_DOC_PATH,
            ROOT_DIR / ".codex" / "skills" / "paper-analysis" / "references" / "command-surface.md",
            ROOT_DIR / ".codex" / "skills" / "paper-analysis" / "references" / "workflow.md",
            QUICKSTART_PATH,
            COMMAND_SURFACE_PATH,
            TESTING_QUALITY_PATH,
            ROOT_DIR / "docs" / "engineering" / "extending-cli.md",
        ]

        for path in expected_paths:
            self.assertTrue(path.exists(), msg=f"missing expected reference: {path}")
            self.assertGreater(len(_read_utf8(path)), 0, msg=f"empty expected reference: {path}")

    def test_natural_language_routing_fixture_is_documented(self) -> None:
        """验证自然语言样例与预期命令映射被文档化，避免入口契约漂移。"""

        routing_doc = _read_utf8(ROUTING_DOC_PATH)
        quickstart = _read_utf8(QUICKSTART_PATH)
        command_surface = _read_utf8(COMMAND_SURFACE_PATH)
        fixture = json.loads(_read_utf8(ROUTING_FIXTURE_PATH))

        for case in fixture:
            request = case["request"]
            expected_command = case["expected_command"]
            self.assertIn(request, routing_doc)
            self.assertIn(expected_command, routing_doc)

        self.assertIn("quality local-ci", quickstart)
        self.assertIn("report --source <conference|arxiv>", command_surface)
        self.assertNotIn("recommend", command_surface.split("## 约束", maxsplit=1)[0])

    def test_testing_spec_requires_codex_natural_language_e2e(self) -> None:
        """验证测试规范已把 Codex 自然语言黑盒 e2e 纳入强约束。"""

        testing_quality = _read_utf8(TESTING_QUALITY_PATH)

        self.assertIn("codex exec --json", testing_quality)
        self.assertIn("prompt 不直接点名 skill", testing_quality)
        self.assertIn(".codex/skills/paper-analysis/SKILL.md", testing_quality)
        self.assertIn("arxiv report --source-mode subscription-api", testing_quality)


if __name__ == "__main__":
    unittest.main()
