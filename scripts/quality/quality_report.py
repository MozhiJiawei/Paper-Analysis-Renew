from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
TARGET_DIRS = ["paper_analysis", "scripts", "tests"]
TOP_N = 5
LONG_FUNCTION_THRESHOLD = 40
LARGE_FILE_THRESHOLD = 300
IMPORT_FANOUT_THRESHOLD = 12


@dataclass(slots=True)
class FunctionHotspot:
    path: Path
    qualified_name: str
    line_count: int
    branch_score: int


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for target_dir in TARGET_DIRS:
        root = ROOT_DIR / target_dir
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    return sorted(files)


def main() -> int:
    files = iter_python_files()
    large_files = _find_large_files(files)
    long_functions = _find_long_functions(files)
    import_hotspots = _find_import_hotspots(files)
    findings = large_files or long_functions or import_hotspots

    if not findings:
        print("[OK] quality report")
        print("未发现超过当前阈值的复杂度治理热点。")
        return 0

    print("[WARN] quality report")
    _print_large_files(large_files)
    _print_long_functions(long_functions)
    _print_import_hotspots(import_hotspots)
    print("说明：当前代码质量报告只告警，不影响 quality lint 的退出码。")
    return 0


def _find_large_files(files: list[Path]) -> list[tuple[Path, int]]:
    results: list[tuple[Path, int]] = []
    for path in files:
        line_count = path.read_text(encoding="utf-8").count("\n") + 1
        if line_count >= LARGE_FILE_THRESHOLD:
            results.append((path, line_count))
    return sorted(results, key=lambda item: item[1], reverse=True)[:TOP_N]


def _find_long_functions(files: list[Path]) -> list[FunctionHotspot]:
    hotspots: list[FunctionHotspot] = []
    for path in files:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node, qualified_name in _iter_functions(module):
            end_lineno = getattr(node, "end_lineno", node.lineno)
            line_count = end_lineno - node.lineno + 1
            branch_score = _branch_score(node)
            if line_count >= LONG_FUNCTION_THRESHOLD or branch_score >= 10:
                hotspots.append(
                    FunctionHotspot(
                        path=path,
                        qualified_name=qualified_name,
                        line_count=line_count,
                        branch_score=branch_score,
                    )
                )
    return sorted(
        hotspots,
        key=lambda item: (item.line_count, item.branch_score, str(item.path)),
        reverse=True,
    )[:TOP_N]


def _find_import_hotspots(files: list[Path]) -> list[tuple[Path, int]]:
    hotspots: list[tuple[Path, int]] = []
    for path in files:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_modules: set[str] = set()
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module.split(".")[0])
        if len(imported_modules) >= IMPORT_FANOUT_THRESHOLD:
            hotspots.append((path, len(imported_modules)))
    return sorted(hotspots, key=lambda item: item[1], reverse=True)[:TOP_N]


def _iter_functions(module: ast.AST) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]]:
    functions: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]] = []

    def visit(node: ast.AST, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified_name = f"{prefix}{child.name}"
                functions.append((child, qualified_name))
                visit(child, f"{qualified_name}.")

    visit(module)
    return functions


def _branch_score(node: ast.AST) -> int:
    score = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.With,
                ast.AsyncWith,
                ast.BoolOp,
                ast.Match,
                ast.ExceptHandler,
            ),
        ):
            score += 1
    return score


def _print_large_files(large_files: list[tuple[Path, int]]) -> None:
    if not large_files:
        return
    print("大文件热点：")
    for index, (path, line_count) in enumerate(large_files, start=1):
        print(f"{index}. {_relative(path)} 行数={line_count}")


def _print_long_functions(long_functions: list[FunctionHotspot]) -> None:
    if not long_functions:
        return
    print("长函数 / 高分支热点：")
    for index, hotspot in enumerate(long_functions, start=1):
        print(
            f"{index}. {_relative(hotspot.path)}::{hotspot.qualified_name} "
            f"行数={hotspot.line_count} 分支分数={hotspot.branch_score}"
        )


def _print_import_hotspots(import_hotspots: list[tuple[Path, int]]) -> None:
    if not import_hotspots:
        return
    print("模块依赖热点：")
    for index, (path, import_count) in enumerate(import_hotspots, start=1):
        print(f"{index}. {_relative(path)} 直接依赖模块数={import_count}")


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT_DIR)).replace("\\", "/")


if __name__ == "__main__":
    raise SystemExit(main())
