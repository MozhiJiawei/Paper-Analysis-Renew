"""Shared helpers for CLI argument loading and terminal output."""

from __future__ import annotations

import json
import sys
from pathlib import Path


class CliInputError(Exception):
    """Raised when CLI inputs cannot be loaded or validated."""


def read_json_file(path: Path | str) -> object:
    """Read a UTF-8 JSON file from a path-like object."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CliInputError(f"输入文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise CliInputError(f"输入文件不是合法 JSON：{path}") from exc
    except OSError as exc:
        raise CliInputError(f"无法读取输入文件：{path}") from exc


def print_cli_error(scope: str, message: str, next_step: str) -> int:
    """Write a structured CLI failure message to stdout."""
    emit_lines(
        f"[FAIL] scope={scope}",
        f"summary: {message}",
        f"next: {next_step}",
    )
    return 1


def emit_lines(*lines: str) -> None:
    """Write one or more terminal lines without using print()."""
    for line in lines:
        sys.stdout.write(f"{line}\n")
