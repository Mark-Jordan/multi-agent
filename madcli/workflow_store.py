from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class PlannedTask:
    task_id: str
    agent: str
    task: str
    depends_on: list[str] | None = None
    review_by: str | None = None
    status: str = "pending"
    run_id: str | None = None
    review_run_id: str | None = None
    retry_count: int = 0
    retry_delay: float = 5.0
    fallback_task_id: str | None = None
    allow_failure: bool = False
    acceptance_criteria: list[str] | None = None
    auto_evaluate: bool = True
    evaluation_score: float | None = None
    evaluation_summary: str | None = None
    require_approval: bool = False
    require_review_approval: bool = False
    approval_status: str | None = None
    approval_comment: str | None = None


@dataclass(frozen=True)
class WorkflowMetadata:
    workflow_id: str
    goal: str
    status: str
    created_at: str
    updated_at: str
    task_ids: list[str]


def make_workflow_id(goal: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in goal).strip("-")
    slug = "-".join(part for part in slug.split("-") if part)
    if not slug:
        slug = "workflow"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{slug[:36]}-{uuid4().hex[:8]}"


class WorkflowStore:
    def __init__(self, workflows_dir: Path) -> None:
        self.workflows_dir = workflows_dir

    def workflow_dir(self, workflow_id: str) -> Path:
        return self.workflows_dir / workflow_id

    def create_workflow(
        self,
        *,
        workflow_id: str,
        goal: str,
        tasks: list[PlannedTask],
    ) -> WorkflowMetadata:
        workflow_dir = self.workflow_dir(workflow_id)
        (workflow_dir / "tasks").mkdir(parents=True, exist_ok=True)
        (workflow_dir / "handoffs").mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        metadata = WorkflowMetadata(
            workflow_id=workflow_id,
            goal=goal,
            status="created",
            created_at=now,
            updated_at=now,
            task_ids=[task.task_id for task in tasks],
        )
        self.save_workflow(metadata)
        for task in tasks:
            self.save_task(workflow_id, task)
        self.append_event(
            workflow_id,
            "workflow_created",
            {"goal": goal, "tasks": [task.task_id for task in tasks]},
        )
        return metadata

    def save_workflow(self, metadata: WorkflowMetadata) -> None:
        path = self.workflow_dir(metadata.workflow_id) / "workflow.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(metadata), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def load_workflow(self, workflow_id: str) -> WorkflowMetadata:
        data = json.loads(
            (self.workflow_dir(workflow_id) / "workflow.json").read_text(
                encoding="utf-8"
            )
        )
        return WorkflowMetadata(**data)

    def update_workflow_status(self, workflow_id: str, status: str) -> WorkflowMetadata:
        metadata = self.load_workflow(workflow_id)
        updated = replace(
            metadata,
            status=status,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self.save_workflow(updated)
        self.append_event(workflow_id, "workflow_status_changed", {"status": status})
        return updated

    def save_task(self, workflow_id: str, task: PlannedTask) -> None:
        path = self.workflow_dir(workflow_id) / "tasks" / f"{task.task_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(task), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def load_task(self, workflow_id: str, task_id: str) -> PlannedTask:
        data = json.loads(
            (
                self.workflow_dir(workflow_id) / "tasks" / f"{task_id}.json"
            ).read_text(encoding="utf-8")
        )
        return PlannedTask(**data)

    def list_tasks(self, workflow_id: str) -> list[PlannedTask]:
        metadata = self.load_workflow(workflow_id)
        return [self.load_task(workflow_id, task_id) for task_id in metadata.task_ids]

    def update_task(
        self,
        workflow_id: str,
        task_id: str,
        *,
        status: str | None = None,
        run_id: str | None = None,
        review_run_id: str | None = None,
    ) -> PlannedTask:
        task = self.load_task(workflow_id, task_id)
        updated = replace(
            task,
            status=status if status is not None else task.status,
            run_id=run_id if run_id is not None else task.run_id,
            review_run_id=(
                review_run_id if review_run_id is not None else task.review_run_id
            ),
        )
        self.save_task(workflow_id, updated)
        self.append_event(
            workflow_id,
            "task_updated",
            {
                "task_id": task_id,
                "status": updated.status,
                "run_id": updated.run_id,
                "review_run_id": updated.review_run_id,
            },
        )
        return updated

    def append_event(
        self, workflow_id: str, event: str, payload: dict[str, Any]
    ) -> None:
        path = self.workflow_dir(workflow_id) / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "time": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_events(self, workflow_id: str) -> list[str]:
        path = self.workflow_dir(workflow_id) / "events.jsonl"
        if not path.exists():
            return []
        return path.read_text(encoding="utf-8").splitlines()

    def list_workflows(self) -> list[WorkflowMetadata]:
        if not self.workflows_dir.exists():
            return []
        workflows: list[WorkflowMetadata] = []
        for path in sorted(self.workflows_dir.iterdir(), reverse=True):
            metadata_path = path / "workflow.json"
            if metadata_path.exists():
                workflows.append(
                    WorkflowMetadata(
                        **json.loads(metadata_path.read_text(encoding="utf-8"))
                    )
                )
        return workflows
