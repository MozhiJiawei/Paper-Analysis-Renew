from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from paper_analysis.shared.encoding import find_mojibake_fragments

TARGET_DIRS = ["paper_analysis", "tests", "scripts", ".codex", "docs", "AGENTS.md", "README.md"]
TEXT_SUFFIXES = {".py", ".md", ".json", ".toml"}
ALLOW_MOJIBAKE_MARKER = "lint: allow-mojibake"


def iter_target_files() -> list[Path]:
    files: list[Path] = []
    for target in TARGET_DIRS:
        candidate = ROOT_DIR / target
        if candidate.is_file():
            files.append(candidate)
            continue
        if not candidate.exists():
            continue
        for path in candidate.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                files.append(path)
    return sorted(files)


def main() -> int:
    violations: list[str] = []
    for path in iter_target_files():
        violations.extend(check_file(path))

    if violations:
        print("[FAIL] lint")
        for violation in violations:
            print(violation)
        return 1

    print("[OK] lint")
    return 0


def check_file(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"{path}: 非 UTF-8 文件 ({exc})"]

    lines = content.splitlines()
    for index, line in enumerate(lines, start=1):
        if line.rstrip(" ") != line:
            violations.append(f"{path}:{index}: 行尾存在多余空格")
        if "\t" in line:
            violations.append(f"{path}:{index}: 存在制表符")

    if content and not content.endswith("\n"):
        violations.append(f"{path}: 文件结尾缺少换行")

    if ALLOW_MOJIBAKE_MARKER not in content:
        fragments = find_mojibake_fragments(content)
        for fragment in fragments:
            violations.append(f"{path}: 检测到疑似乱码片段 `{fragment}`")

    return violations


if __name__ == "__main__":
    raise SystemExit(main())
