from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import time
import threading

from .agent_message import TaskHandoff, build_handoff_from_result
from .config import AppConfig
from .event_bus import (
    EventBus,
    REVIEW_COMPLETED,
    REVIEW_FAILED,
    REVIEW_STARTED,
    TASK_BLOCKED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_RETRYING,
    TASK_STARTED,
    WORKFLOW_AWAITING_APPROVAL,
    WORKFLOW_COMPLETED,
    WORKFLOW_FAILED,
    WORKFLOW_STARTED,
)
from .hitl import request_approval
from .planner import plan_tasks_with_agent
from .task_runner import AgentTaskRequest, AgentTaskResult, run_agent_task
from .workflow_store import PlannedTask, WorkflowStore, make_workflow_id


def _build_upstream_context(
    task: PlannedTask, handoffs_dir: Path
) -> str | None:
    if not task.depends_on:
        return None
    handoffs = TaskHandoff.load_all(handoffs_dir)
    upstream = [
        h for h in handoffs if h.source_task_id in (task.depends_on or [])
    ]
    if not upstream:
        return None
    parts = ["# Upstream Task Results\n"]
    for h in upstream:
        parts.append(f"## Task: {h.source_task_id}\n")
        parts.append(f"Summary: {h.summary[:300]}\n")
        if h.findings:
            parts.append(f"Findings: {h.findings[:200]}\n")
        if h.warnings:
            parts.append(f"Warnings: {h.warnings[:200]}\n")
        if h.suggestions:
            parts.append(f"Suggestions: {h.suggestions[:200]}\n")
        parts.append("")
    return "\n".join(parts)


@dataclass(frozen=True)
class WorkflowRunResult:
    workflow_id: str
    status: str
    workflow_dir: Path


class WorkflowOrchestrator:
    def __init__(
        self,
        config: AppConfig,
        store: WorkflowStore,
        task_runner=run_agent_task,
    ) -> None:
        self.config = config
        self.store = store
        self.task_runner = task_runner
        self._lock = threading.Lock()
        self._max_workers = getattr(config, "max_parallel_workers", 4) or 4

    def _topological_layers(
        self, tasks: list[PlannedTask]
    ) -> list[list[PlannedTask]]:
        task_map = {t.task_id: t for t in tasks}
        dep_count: dict[str, int] = {}
        dependents: dict[str, list[str]] = {t.task_id: [] for t in tasks}
        for t in tasks:
            deps = [d for d in (t.depends_on or []) if d in task_map]
            dep_count[t.task_id] = len(deps)
            for d in deps:
                dependents[d].append(t.task_id)

        layers: list[list[PlannedTask]] = []
        remaining = set(task_map.keys())
        while remaining:
            layer_ids = [
                tid for tid in remaining if dep_count.get(tid, 0) == 0
            ]
            if not layer_ids:
                break
            layers.append([task_map[tid] for tid in sorted(layer_ids)])
            for tid in layer_ids:
                remaining.discard(tid)
                for dep_tid in dependents.get(tid, []):
                    dep_count[dep_tid] = max(0, dep_count[dep_tid] - 1)
        if remaining:
            for tid in sorted(remaining):
                if tid in task_map:
                    layers.append([task_map[tid]])
        return layers

    def _run_single_task(
        self,
        task: PlannedTask,
        workflow_id: str,
        dry_run: bool,
    ) -> tuple[PlannedTask, AgentTaskResult | None, bool]:
        if task.require_approval and task.approval_status != "approved":
            if task.approval_status is None:
                request_approval(self.store, workflow_id, task.task_id, "execution")
            return task, None, True

        if task.approval_status == "rejected":
            self.store.update_task(workflow_id, task.task_id, status="failed")
            return task, None, False

        self.store.update_task(workflow_id, task.task_id, status="running")
        EventBus.instance().publish(
            TASK_STARTED,
            {"workflow_id": workflow_id, "task_id": task.task_id, "agent": task.agent},
        )

        handoffs_dir = self.store.workflow_dir(workflow_id) / "handoffs"
        extra_context = _build_upstream_context(task, handoffs_dir)

        max_attempts = 1 + max(0, task.retry_count)
        worker_result: AgentTaskResult | None = None
        for attempt in range(max_attempts):
            if attempt > 0:
                EventBus.instance().publish(
                    TASK_RETRYING,
                    {"workflow_id": workflow_id, "task_id": task.task_id, "attempt": attempt},
                )
                time.sleep(task.retry_delay)
            worker_result = self.task_runner(
                AgentTaskRequest(
                    config=self.config,
                    task=task.task,
                    agent_name=task.agent,
                    workdir=self.config.default_workdir,
                    dry_run=dry_run,
                    context_files=[],
                    extra_context=extra_context,
                )
            )
            if worker_result.ok:
                if not dry_run:
                    result_path = worker_result.run_dir / "outputs" / "result.md"
                    handoff = build_handoff_from_result(
                        task.task_id,
                        worker_result.run_id,
                        worker_result.stdout,
                        worker_result.stderr,
                        result_path,
                    )
                    handoff.save(handoffs_dir)
                break

        if not worker_result or not worker_result.ok:
            if task.fallback_task_id:
                EventBus.instance().publish(
                    TASK_FAILED,
                    {"workflow_id": workflow_id, "task_id": task.task_id, "run_id": worker_result.run_id if worker_result else None, "fallback": task.fallback_task_id},
                )
                return task, worker_result, True if task.allow_failure else False

            with self._lock:
                self.store.update_task(
                    workflow_id,
                    task.task_id,
                    status="failed",
                    run_id=worker_result.run_id if worker_result else None,
                )
            EventBus.instance().publish(
                TASK_FAILED,
                {"workflow_id": workflow_id, "task_id": task.task_id, "run_id": worker_result.run_id if worker_result else None},
            )
            return task, worker_result, task.allow_failure

        with self._lock:
            self.store.update_task(
                workflow_id,
                task.task_id,
                status="succeeded",
                run_id=worker_result.run_id,
            )
        EventBus.instance().publish(
            TASK_COMPLETED,
            {"workflow_id": workflow_id, "task_id": task.task_id, "run_id": worker_result.run_id},
        )

        review_ok = True
        if task.require_review_approval and task.approval_status != "approved":
            if task.approval_status is None:
                request_approval(self.store, workflow_id, task.task_id, "review")
            return task, worker_result, True

        if task.review_by:
            EventBus.instance().publish(
                REVIEW_STARTED,
                {"workflow_id": workflow_id, "task_id": task.task_id, "reviewer": task.review_by},
            )
            review_result = self._run_review(task, worker_result, dry_run)
            with self._lock:
                self.store.update_task(
                    workflow_id,
                    task.task_id,
                    status="reviewed" if review_result.ok else "review_failed",
                    run_id=worker_result.run_id,
                    review_run_id=review_result.run_id,
                )
            if review_result.ok:
                EventBus.instance().publish(
                    REVIEW_COMPLETED,
                    {"workflow_id": workflow_id, "task_id": task.task_id, "review_run_id": review_result.run_id},
                )
            else:
                EventBus.instance().publish(
                    REVIEW_FAILED,
                    {"workflow_id": workflow_id, "task_id": task.task_id, "review_run_id": review_result.run_id},
                )
                review_ok = False

        return task, worker_result, review_ok

    def run_plan(
        self,
        *,
        goal: str,
        tasks: list[PlannedTask],
        workflow_id: str | None = None,
        dry_run: bool = False,
        max_replans: int = 3,
    ) -> WorkflowRunResult:
        workflow_id = workflow_id or make_workflow_id(goal)
        metadata = self.store.create_workflow(
            workflow_id=workflow_id,
            goal=goal,
            tasks=tasks,
        )
        self.store.update_workflow_status(workflow_id, "running")
        EventBus.instance().publish(
            WORKFLOW_STARTED,
            {"workflow_id": workflow_id, "goal": goal, "task_count": len(tasks)},
        )
        completed_tasks: dict[str, PlannedTask] = {}
        replan_count = 0
        current_tasks = list(tasks)
        failed = False

        while current_tasks:
            known_task_ids = {t.task_id for t in current_tasks}
            layers = self._topological_layers(current_tasks)
            layer_failed = False

            for layer_index, layer in enumerate(layers):
                if len(layer) == 1:
                    task = layer[0]
                    deps = task.depends_on or []
                    missing = [d for d in deps if d not in known_task_ids]
                    if missing:
                        EventBus.instance().publish(
                            TASK_BLOCKED,
                            {"workflow_id": workflow_id, "task_id": task.task_id, "missing": missing},
                        )
                        self.store.update_task(workflow_id, task.task_id, status="blocked")
                        self.store.append_event(
                            workflow_id, "task_blocked",
                            {"task_id": task.task_id, "missing_dependencies": missing},
                        )
                        failed = True
                        layer_failed = True
                        continue
                    _, _, ok = self._run_single_task(task, workflow_id, dry_run)
                    if ok:
                        completed_tasks[task.task_id] = task
                    else:
                        failed = True
                        layer_failed = True
                else:
                    futures_map: dict = {}
                    with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                        for task in layer:
                            deps = task.depends_on or []
                            missing = [d for d in deps if d not in known_task_ids]
                            if missing:
                                EventBus.instance().publish(
                                    TASK_BLOCKED,
                                    {"workflow_id": workflow_id, "task_id": task.task_id, "missing": missing},
                                )
                                self.store.update_task(workflow_id, task.task_id, status="blocked")
                                self.store.append_event(
                                    workflow_id, "task_blocked",
                                    {"task_id": task.task_id, "missing_dependencies": missing},
                                )
                                failed = True
                                layer_failed = True
                                continue
                            future = executor.submit(
                                self._run_single_task, task, workflow_id, dry_run
                            )
                            futures_map[future] = task

                    for future in as_completed(futures_map):
                        result_task, _, ok = future.result()
                        if ok:
                            completed_tasks[result_task.task_id] = result_task
                        else:
                            failed = True
                            layer_failed = True

            if not layer_failed:
                break

            if replan_count >= max_replans or dry_run:
                break

            remaining = [
                t for t in current_tasks
                if t.task_id not in completed_tasks
                and self.store.load_task(workflow_id, t.task_id).status in ("pending", "blocked")
            ]
            if not remaining:
                break

            replan_count += 1
            self.store.append_event(
                workflow_id, "replan_triggered",
                {"replan": replan_count, "max_replans": max_replans,
                 "completed": list(completed_tasks.keys()),
                 "remaining": [t.task_id for t in remaining]},
            )
            replan_prompt = (
                f"Original goal:\n{goal}\n\n"
                "The following tasks are already completed. Do NOT re-plan them:\n"
                + "\n".join(
                    f"- {tid}: {completed_tasks[tid].task[:100]}"
                    for tid in sorted(completed_tasks)
                )
                + "\n\nThe following tasks failed or remain. Create a new plan to "
                + "complete the original goal. Consider what went wrong and adjust:\n"
                + "\n".join(
                    f"- {t.task_id}: {t.task[:100]}"
                    for t in remaining
                )
            )
            try:
                new_tasks = plan_tasks_with_agent(
                    config=self.config,
                    goal=replan_prompt,
                    planner_agent=self.config.agents.get(
                        "codex_reviewer", next(iter(self.config.agents))
                    ).name,
                    dry_run=dry_run,
                    task_runner=self.task_runner,
                )
            except (ValueError, Exception):
                break

            current_tasks = [
                t for t in remaining
                if t.task_id in {nt.task_id for nt in new_tasks}
            ]
            for nt in new_tasks:
                if nt.task_id not in completed_tasks:
                    current_tasks.append(nt)

        final_status = "failed" if failed else "succeeded"
        self.store.update_workflow_status(workflow_id, final_status)
        EventBus.instance().publish(
            WORKFLOW_COMPLETED if final_status == "succeeded" else WORKFLOW_FAILED,
            {"workflow_id": workflow_id, "status": final_status},
        )
        return WorkflowRunResult(
            workflow_id=metadata.workflow_id,
            status=final_status,
            workflow_dir=self.store.workflow_dir(workflow_id),
        )

    def resume_workflow(
        self,
        workflow_id: str,
        *,
        dry_run: bool = False,
        max_replans: int = 3,
    ) -> WorkflowRunResult:
        """Resume a paused workflow from where it left off."""
        metadata = self.store.load_workflow(workflow_id)
        if metadata.status not in ("awaiting_approval", "running", "created"):
            raise ValueError(
                f"workflow '{workflow_id}' is {metadata.status}, cannot resume"
            )

        all_tasks = self.store.list_tasks(workflow_id)
        pending: list[PlannedTask] = []
        for t in all_tasks:
            if t.status in ("succeeded", "reviewed", "failed", "blocked"):
                continue
            if t.require_approval and t.approval_status == "approved":
                pending.append(t)
            elif t.require_review_approval and t.approval_status == "approved":
                pending.append(t)
            elif not t.require_approval and not t.require_review_approval:
                pending.append(t)
            elif t.approval_status == "rejected":
                continue

        if not pending:
            self.store.update_workflow_status(workflow_id, "succeeded")
            return WorkflowRunResult(
                workflow_id=workflow_id,
                status="succeeded",
                workflow_dir=self.store.workflow_dir(workflow_id),
            )

        return self.run_plan(
            goal=metadata.goal,
            tasks=pending,
            workflow_id=workflow_id,
            dry_run=dry_run,
            max_replans=max_replans,
        )

    def _run_review(
        self,
        task: PlannedTask,
        worker_result: AgentTaskResult,
        dry_run: bool,
    ) -> AgentTaskResult:
        result_path = worker_result.run_dir / "outputs" / "result.md"
        stdout_path = worker_result.run_dir / "outputs" / "stdout.txt"
        stderr_path = worker_result.run_dir / "outputs" / "stderr.txt"
        context_files = [
            path for path in [result_path, stdout_path, stderr_path] if path.exists()
        ]
        review_task = (
            "Review the completed task result. Focus on correctness, regressions, "
            "missing tests, security, and follow-up work.\n\n"
            f"Original task ID: {task.task_id}\n"
            f"Original task:\n{task.task}"
        )
        if task.acceptance_criteria:
            review_task += "\n\n## Acceptance Criteria\n"
            for i, criterion in enumerate(task.acceptance_criteria, 1):
                review_task += f"{i}. {criterion}\n"
            review_task += "\nEvaluate whether each criterion is met."
        return self.task_runner(
            AgentTaskRequest(
                config=self.config,
                task=review_task,
                agent_name=task.review_by or "",
                workdir=self.config.default_workdir,
                dry_run=dry_run,
                context_files=context_files,
            )
        )
