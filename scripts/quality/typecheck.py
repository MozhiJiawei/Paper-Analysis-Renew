from __future__ import annotations

import ast
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
PACKAGE_DIR = ROOT_DIR / "paper_analysis"


def main() -> int:
    violations: list[str] = []
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in module.body:
            if isinstance(node, ast.FunctionDef):
                violations.extend(validate_function(path, node))
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and not child.name.startswith("_"):
                        violations.extend(validate_function(path, child, class_name=node.name))

    if violations:
        print("[FAIL] typecheck")
        for violation in violations:
            print(violation)
        return 1

    print("[OK] typecheck")
    return 0


def validate_function(path: Path, node: ast.FunctionDef, class_name: str | None = None) -> list[str]:
    name = f"{class_name}.{node.name}" if class_name else node.name
    violations: list[str] = []
    if node.name.startswith("_"):
        return violations

    if node.returns is None:
        violations.append(f"{path}:{node.lineno}: {name} 缺少返回类型注解")

    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
        if arg.arg in {"self", "cls"}:
            continue
        if arg.annotation is None:
            violations.append(f"{path}:{node.lineno}: {name} 的参数 {arg.arg} 缺少类型注解")
    return violations


if __name__ == "__main__":
    raise SystemExit(main())
