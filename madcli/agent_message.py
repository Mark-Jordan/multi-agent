from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class AgentMessage:
    message_id: str
    from_task_id: str
    to_task_id: str | None
    message_type: str
    content: str
    artifact_paths: list[str]
    created_at: str


@dataclass(frozen=True)
class TaskHandoff:
    source_task_id: str
    source_run_id: str
    summary: str
    key_files: list[str]
    findings: str
    warnings: str
    suggestions: str

    def to_message(self) -> AgentMessage:
        return AgentMessage(
            message_id=uuid4().hex[:12],
            from_task_id=self.source_task_id,
            to_task_id=None,
            message_type="handoff",
            content=(
                f"Summary: {self.summary}\n"
                f"Findings: {self.findings}\n"
                f"Warnings: {self.warnings}\n"
                f"Suggestions: {self.suggestions}\n"
                f"Key files: {', '.join(self.key_files) or 'none'}"
            ),
            artifact_paths=self.key_files,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def save(self, handoffs_dir: Path) -> Path:
        handoffs_dir.mkdir(parents=True, exist_ok=True)
        path = handoffs_dir / f"{self.source_task_id}.json"
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(cls, path: Path) -> TaskHandoff:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)

    @classmethod
    def load_all(cls, handoffs_dir: Path) -> list[TaskHandoff]:
        if not handoffs_dir.exists():
            return []
        handoffs: list[TaskHandoff] = []
        for path in sorted(handoffs_dir.glob("*.json")):
            try:
                handoffs.append(cls.load(path))
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        return handoffs


def build_handoff_from_result(
    task_id: str,
    run_id: str,
    worker_stdout: str,
    worker_stderr: str,
    result_path: Path | None,
) -> TaskHandoff:
    summary = ""
    if result_path and result_path.exists():
        result_text = result_path.read_text(encoding="utf-8")
        summary = result_text[:500].strip()

    return TaskHandoff(
        source_task_id=task_id,
        source_run_id=run_id,
        summary=summary or worker_stdout[:300].strip() or "Task completed.",
        key_files=[],
        findings=worker_stdout[:200].strip() if worker_stdout else "",
        warnings=worker_stderr[:200].strip() if worker_stderr else "",
        suggestions="",
    )
