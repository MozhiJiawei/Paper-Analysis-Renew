from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


Runner = Callable[[str], str]


@dataclass(slots=True)
class CodexCliClient:
    """轻量 Codex CLI 调用器，可被多个线程共享复用。"""

    runner: Runner | None = None
    cwd: Path | None = None
    timeout: int | None = None
    json_mode: bool = False
    ephemeral: bool = False

    def exec(self, prompt: str) -> str:
        if self.runner is not None:
            return self.runner(prompt)
        try:
            result = subprocess.run(
                self._build_command(prompt),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                cwd=self.cwd,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Codex CLI 调用超时：timeout={self.timeout}s") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "未知错误"
            raise RuntimeError(
                f"Codex CLI 调用失败：returncode={result.returncode}; {detail}"
            )
        return result.stdout.strip()

    def _build_command(self, prompt: str) -> list[str]:
        command = [
            "codex.cmd" if os.name == "nt" else "codex",
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
        ]
        if self.json_mode:
            command.append("--json")
        if self.ephemeral:
            command.append("--ephemeral")
        command.append(prompt)
        return command
