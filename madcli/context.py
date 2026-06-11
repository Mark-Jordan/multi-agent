from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from uuid import uuid4

from .config import AgentConfig


def make_run_id(task: str) -> str:
    date = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", task.strip().lower()).strip("-")
    if not slug:
        slug = "task"
    return f"{date}-{slug[:36]}-{uuid4().hex[:8]}"


def write_context_package(
    *,
    context_dir: Path,
    task: str,
    agent: AgentConfig,
    extra_context: str | None = None,
    extra_context_files: list[Path] | None = None,
) -> list[Path]:
    context_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "user_goal.md": f"# User Goal\n\n{task.strip()}\n",
        "agent_context.md": (
            "# Agent Context\n\n"
            f"- CLI agent key: `{agent.name}`\n"
            f"- Runtime: `{agent.runtime}`\n"
            f"- Runtime agent: `{agent.agent}`\n"
            f"- Model: `{agent.model or 'runtime default'}`\n"
            f"- Description: {agent.description}\n"
        ),
        "engineering_task.md": (
            "# Engineering Task\n\n"
            "Read all context files first, inspect the repository, then complete the task.\n\n"
            "## Task\n\n"
            f"{task.strip()}\n\n"
            "## Expected Output\n\n"
            "- Summary of changes or findings.\n"
            "- Files modified, if any.\n"
            "- Commands run and their results.\n"
            "- Risks, blockers, and follow-up work.\n"
        ),
    }
    if extra_context:
        files["extra_context.md"] = f"# Extra Context\n\n{extra_context.strip()}\n"
    written: list[Path] = []
    for filename, content in files.items():
        path = context_dir / filename
        path.write_text(content, encoding="utf-8")
        written.append(path)
    for index, source in enumerate(extra_context_files or [], start=1):
        resolved_source = source.resolve()
        path = context_dir / f"context_file_{index}_{source.name}"
        content = resolved_source.read_text(encoding="utf-8")
        path.write_text(
            f"# Context File {index}\n\nSource: `{resolved_source}`\n\n{content}",
            encoding="utf-8",
        )
        written.append(path)
    return written
