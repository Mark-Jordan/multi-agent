from __future__ import annotations

from typing import Any, Callable

# Predefined event type constants
WORKFLOW_STARTED = "workflow.started"
WORKFLOW_COMPLETED = "workflow.completed"
WORKFLOW_FAILED = "workflow.failed"
WORKFLOW_AWAITING_APPROVAL = "workflow.awaiting_approval"
TASK_STARTED = "task.started"
TASK_COMPLETED = "task.completed"
TASK_FAILED = "task.failed"
TASK_RETRYING = "task.retrying"
TASK_BLOCKED = "task.blocked"
TASK_APPROVAL_REQUIRED = "task.approval_required"
REVIEW_STARTED = "review.started"
REVIEW_COMPLETED = "review.completed"
REVIEW_FAILED = "review.failed"
RUN_STARTED = "run.started"
RUN_FINISHED = "run.finished"
EXECUTOR_FINISHED = "executor.finished"


class EventBus:
    _instance: EventBus | None = None

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[str, dict[str, Any]], None]]] = {}

    @classmethod
    def instance(cls) -> EventBus:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[str, dict[str, Any]], None],
    ) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(
        self,
        event_type: str,
        callback: Callable[[str, dict[str, Any]], None],
    ) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                cb for cb in self._subscribers[event_type] if cb is not callback
            ]

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        for cb in self._subscribers.get(event_type, []):
            try:
                cb(event_type, payload)
            except Exception:
                pass

    def reset(self) -> None:
        self._subscribers.clear()

    @classmethod
    def reset_instance(cls) -> None:
        if cls._instance is not None:
            cls._instance.reset()
