from __future__ import annotations

import json
from pathlib import Path


class CliInputError(Exception):
    """Raised when CLI inputs cannot be loaded or validated."""


def read_json_file(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CliInputError(f"输入文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise CliInputError(f"输入文件不是合法 JSON：{path}") from exc
    except OSError as exc:
        raise CliInputError(f"无法读取输入文件：{path}") from exc


def print_cli_error(scope: str, message: str, next_step: str) -> int:
    print(f"[FAIL] scope={scope}")
    print(f"summary: {message}")
    print(f"next: {next_step}")
    return 1
