from __future__ import annotations

# lint: allow-mojibake

import os
import sys
from typing import TextIO


UTF8_ENV_OVERRIDES = {
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}

MOJIBAKE_SIGNATURES = (
    "锛歚",
    "锛屾",
    "銆?",
    "妫€鏌?",
    "鍏ュ彛",
    "鏈",
    "闃舵",
)


def configure_utf8_stdio() -> None:
    """Best-effort: keep CLI stdout/stderr stable when output is piped on Windows."""

    _reconfigure_stream(sys.stdout)
    _reconfigure_stream(sys.stderr)


def build_utf8_subprocess_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env.update(UTF8_ENV_OVERRIDES)
    return env


def find_mojibake_fragments(content: str) -> list[str]:
    fragments: list[str] = []
    if "\ufffd" in content:
        fragments.append("\ufffd")
    fragments.extend(signature for signature in MOJIBAKE_SIGNATURES if signature in content)
    return fragments


def _reconfigure_stream(stream: TextIO) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except ValueError:
        # Some environments expose a stream object that cannot be reconfigured.
        return
