from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.quality.lint import check_file


class LintTests(unittest.TestCase):
    def test_check_file_flags_replacement_character_as_mojibake(self) -> None:
        """验证 lint 会拦截常见的编码损坏占位符。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "broken.md"
            path.write_text("正常文本\ufffd\n", encoding="utf-8")

            violations = check_file(path)

        self.assertEqual([f"{path}: 检测到疑似乱码片段 `\ufffd`"], violations)

    def test_check_file_allows_explicit_mojibake_fixture_marker(self) -> None:
        """验证显式豁免标记会跳过乱码片段检测。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "allowed.md"
            path.write_text("<!-- lint: allow-mojibake -->\n正常文本\ufffd\n", encoding="utf-8")

            violations = check_file(path)

        self.assertEqual([], violations)

    def test_check_file_skips_python_whitespace_hygiene_rules(self) -> None:
        """验证 Python 文件的尾随空格与 Tab 交给 Ruff，而不是 repo rules 重复报错。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.py"
            path.write_text("def demo():    \n\treturn 1", encoding="utf-8")

            violations = check_file(path)

        self.assertEqual([], violations)

    def test_check_file_keeps_non_python_whitespace_hygiene_rules(self) -> None:
        """验证非 Python 文本文件仍会执行仓库特有的空白字符卫生检查。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.md"
            path.write_text("标题  \n\t正文", encoding="utf-8")

            violations = check_file(path)

        self.assertEqual(
            [
                f"{path}:1: 行尾存在多余空格",
                f"{path}:2: 存在制表符",
                f"{path}: 文件结尾缺少换行",
            ],
            violations,
        )


if __name__ == "__main__":
    unittest.main()
