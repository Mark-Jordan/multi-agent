from __future__ import annotations

from dataclasses import replace

from .event_bus import EventBus, WORKFLOW_AWAITING_APPROVAL, TASK_APPROVAL_REQUIRED
from .workflow_store import WorkflowStore


def request_approval(
    store: WorkflowStore,
    workflow_id: str,
    task_id: str,
    approval_type: str,
) -> None:
    """Pause workflow and mark task as awaiting approval."""
    store.update_workflow_status(workflow_id, "awaiting_approval")
    store.update_task(
        workflow_id, task_id,
        status="awaiting_approval",
        approval_status="pending",
    )
    store.append_event(
        workflow_id, "approval_requested",
        {"task_id": task_id, "type": approval_type},
    )
    EventBus.instance().publish(
        WORKFLOW_AWAITING_APPROVAL,
        {"workflow_id": workflow_id, "task_id": task_id, "type": approval_type},
    )
    EventBus.instance().publish(
        TASK_APPROVAL_REQUIRED,
        {"workflow_id": workflow_id, "task_id": task_id, "type": approval_type},
    )


def approve_task(
    store: WorkflowStore,
    workflow_id: str,
    task_id: str,
    comment: str | None = None,
) -> None:
    """Approve a task that was awaiting approval."""
    store.update_task(
        workflow_id, task_id,
        approval_status="approved",
        approval_comment=comment,
    )
    store.append_event(
        workflow_id, "task_approved",
        {"task_id": task_id, "comment": comment},
    )


def reject_task(
    store: WorkflowStore,
    workflow_id: str,
    task_id: str,
    reason: str | None = None,
) -> None:
    """Reject a task that was awaiting approval."""
    store.update_task(
        workflow_id, task_id,
        status="failed",
        approval_status="rejected",
        approval_comment=reason,
    )
    store.append_event(
        workflow_id, "task_rejected",
        {"task_id": task_id, "reason": reason},
    )
