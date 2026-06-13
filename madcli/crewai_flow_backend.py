from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import traceback
from typing import Callable

from .config import AppConfig
from .orchestrator import WorkflowOrchestrator, WorkflowRunResult
from .planner import plan_tasks_with_agent
from .task_runner import AgentTaskResult, run_agent_task
from .workflow_store import PlannedTask, WorkflowStore, make_workflow_id


class FlowState(Enum):
    START = "start"
    PLAN_READY = "plan_ready"
    TASK_DISPATCHING = "task_dispatching"
    TASK_RUNNING = "task_running"
    TASK_SUCCEEDED = "task_succeeded"
    TASK_FAILED = "task_failed"
    REVIEW_REQUIRED = "review_required"
    REVIEW_RUNNING = "review_running"
    REVIEW_PASSED = "review_passed"
    REVIEW_FAILED = "review_failed"
    REPLANNING = "replanning"
    ALL_DONE = "all_done"
    ERROR = "error"


@dataclass(frozen=True)
class FlowStep:
    state: FlowState
    task_id: str | None = None
    run_id: str | None = None
    review_run_id: str | None = None
    error: str | None = None


class FlowStateMachine:
    def __init__(self, workflow_id: str, store: WorkflowStore) -> None:
        self.workflow_id = workflow_id
        self.store = store
        self.history: list[FlowStep] = []
        self._current: FlowState = FlowState.START

    @property
    def current(self) -> FlowState:
        return self._current

    def transition(self, next_state: FlowState, **kwargs: object) -> None:
        step = FlowStep(state=next_state, **kwargs)
        self.history.append(step)
        self._current = next_state
        self._persist_step(step)

    def _persist_step(self, step: FlowStep) -> None:
        record = {
            "state": step.state.value,
            "task_id": step.task_id,
            "run_id": step.run_id,
            "review_run_id": step.review_run_id,
            "error": step.error,
        }
        self.store.append_event(
            self.workflow_id,
            "flow_state_transition",
            record,
        )

    @classmethod
    def restore(cls, workflow_id: str, store: WorkflowStore) -> FlowStateMachine:
        sm = cls(workflow_id, store)
        events = store.read_events(workflow_id)
        for line in events:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("event") == "flow_state_transition":
                payload = record.get("payload", {})
                state_name = payload.get("state")
                if state_name:
                    try:
                        state = FlowState(state_name)
                    except ValueError:
                        continue
                    step = FlowStep(
                        state=state,
                        task_id=payload.get("task_id"),
                        run_id=payload.get("run_id"),
                        review_run_id=payload.get("review_run_id"),
                        error=payload.get("error"),
                    )
                    sm.history.append(step)
                    sm._current = state
        return sm


class FlowOrchestrator:
    def __init__(
        self,
        config: AppConfig,
        store: WorkflowStore,
    ) -> None:
        self.config = config
        self.store = store
        self._orchestrator = WorkflowOrchestrator(config, store)
        self._max_replans = 3

    def run(
        self,
        *,
        goal: str,
        tasks: list[PlannedTask],
        workflow_id: str | None = None,
        dry_run: bool = False,
    ) -> WorkflowRunResult:
        workflow_id = workflow_id or make_workflow_id(goal)
        sm = FlowStateMachine(workflow_id, self.store)

        self.store.create_workflow(
            workflow_id=workflow_id,
            goal=goal,
            tasks=tasks,
        )

        sm.transition(FlowState.START)
        sm.transition(FlowState.PLAN_READY, task_id=None)

        self.store.update_workflow_status(workflow_id, "running")

        task_map: dict[str, PlannedTask] = {t.task_id: t for t in tasks}
        completed: set[str] = set()
        failed: set[str] = set()
        remaining = list(tasks)
        replan_count = 0

        while remaining:
            ready = [t for t in remaining if all(
                d in completed for d in (t.depends_on or [])
            )]

            if not ready:
                stuck = [t.task_id for t in remaining]
                sm.transition(FlowState.ERROR, error=f"deadlock: tasks with unsatisfied dependencies: {stuck}")
                self.store.update_workflow_status(workflow_id, "failed")
                return WorkflowRunResult(
                    workflow_id=workflow_id,
                    status="failed",
                    workflow_dir=self.store.workflow_dir(workflow_id),
                )

            for task in ready:
                sm.transition(FlowState.TASK_DISPATCHING, task_id=task.task_id)
                sm.transition(FlowState.TASK_RUNNING, task_id=task.task_id)

                result, task_ok = self._execute_task(task, workflow_id, dry_run)

                stored = self.store.load_task(workflow_id, task.task_id)
                run_id = stored.run_id

                if task_ok:
                    if stored.status in ("reviewed", "succeeded"):
                        sm.transition(FlowState.TASK_SUCCEEDED,
                                      task_id=task.task_id, run_id=run_id)
                        if stored.review_run_id:
                            sm.transition(FlowState.REVIEW_REQUIRED, task_id=task.task_id)
                            sm.transition(FlowState.REVIEW_RUNNING, task_id=task.task_id)
                            sm.transition(FlowState.REVIEW_PASSED,
                                          task_id=task.task_id,
                                          review_run_id=stored.review_run_id)
                    elif stored.status == "review_failed":
                        sm.transition(FlowState.TASK_SUCCEEDED,
                                      task_id=task.task_id, run_id=run_id)
                        sm.transition(FlowState.REVIEW_REQUIRED, task_id=task.task_id)
                        sm.transition(FlowState.REVIEW_RUNNING, task_id=task.task_id)
                        sm.transition(FlowState.REVIEW_FAILED,
                                      task_id=task.task_id,
                                      review_run_id=stored.review_run_id)
                        task_ok = False
                    elif stored.status == "failed":
                        sm.transition(FlowState.TASK_FAILED,
                                      task_id=task.task_id, run_id=run_id)
                    else:
                        sm.transition(FlowState.TASK_SUCCEEDED,
                                      task_id=task.task_id, run_id=run_id)

                if not task_ok:
                    sm.transition(FlowState.TASK_FAILED,
                                  task_id=task.task_id, run_id=run_id)
                    if not task.allow_failure:
                        failed.add(task.task_id)

                if task_ok or task.allow_failure:
                    completed.add(task.task_id)

                remaining = [t for t in remaining if t.task_id != task.task_id]

            if failed:
                if replan_count < self._max_replans and not dry_run:
                    replan_count += 1
                    sm.transition(FlowState.REPLANNING)
                    new_tasks = self._try_replan(goal, task_map, completed, failed)
                    if new_tasks:
                        remaining = new_tasks
                        failed.clear()
                        continue
                sm.transition(FlowState.ERROR, error=f"tasks failed: {sorted(failed)}")
                self.store.update_workflow_status(workflow_id, "failed")
                return WorkflowRunResult(
                    workflow_id=workflow_id,
                    status="failed",
                    workflow_dir=self.store.workflow_dir(workflow_id),
                )

        sm.transition(FlowState.ALL_DONE)
        self.store.update_workflow_status(workflow_id, "succeeded")
        return WorkflowRunResult(
            workflow_id=workflow_id,
            status="succeeded",
            workflow_dir=self.store.workflow_dir(workflow_id),
        )

    def _execute_task(
        self, task: PlannedTask, workflow_id: str, dry_run: bool
    ) -> tuple[AgentTaskResult | None, bool]:
        _, result, ok = self._orchestrator._run_single_task(task, workflow_id, dry_run)
        return result, ok

    def _try_replan(
        self,
        goal: str,
        task_map: dict[str, PlannedTask],
        completed: set[str],
        failed: set[str],
    ) -> list[PlannedTask] | None:
        failed_tasks = [task_map[tid] for tid in failed if tid in task_map]
        completed_tasks = [task_map[tid] for tid in completed if tid in task_map]
        replan_prompt = (
            f"Original goal:\n{goal}\n\n"
            "Already completed:\n"
            + "\n".join(f"- {t.task_id}: {t.task[:100]}" for t in completed_tasks)
            + "\n\nFailed tasks:\n"
            + "\n".join(f"- {t.task_id}: {t.task[:100]}" for t in failed_tasks)
            + "\n\nCreate a new plan to complete the goal."
        )
        try:
            planner_agent = self.config.agents.get(
                "codex_reviewer", next(iter(self.config.agents))
            ).name
            return plan_tasks_with_agent(
                config=self.config,
                goal=replan_prompt,
                planner_agent=planner_agent,
                dry_run=False,
                task_runner=self._orchestrator.task_runner,
            )
        except Exception:
            return None


def run_flow_workflow(
    *,
    config: AppConfig,
    store: WorkflowStore,
    goal: str,
    tasks: list[PlannedTask] | None = None,
    plan_file: Path | None = None,
    planner_agent: str | None = None,
    dry_run: bool = False,
) -> WorkflowRunResult:
    if tasks:
        pass
    elif plan_file:
        from .planner import parse_planned_tasks
        tasks = parse_planned_tasks(
            plan_file.read_text(encoding="utf-8"), config=config
        )
    elif planner_agent:
        tasks = plan_tasks_with_agent(
            config=config,
            goal=goal,
            planner_agent=planner_agent,
            dry_run=dry_run,
        )
    else:
        raise ValueError("flow backend requires --plan-file, --planner-agent, or --template")

    orchestrator = FlowOrchestrator(config, store)
    return orchestrator.run(goal=goal, tasks=tasks, dry_run=dry_run)


def flow_status_report(workflow_id: str, store: WorkflowStore) -> str:
    sm = FlowStateMachine.restore(workflow_id, store)
    lines = [
        f"Workflow: {workflow_id}",
        f"Current state: {sm.current.value}",
        f"Total transitions: {len(sm.history)}",
        "",
        "State history:",
    ]
    for i, step in enumerate(sm.history):
        extra = ""
        if step.task_id:
            extra += f" task={step.task_id}"
        if step.run_id:
            extra += f" run={step.run_id}"
        if step.error:
            extra += f" error={step.error}"
        lines.append(f"  {i + 1}. {step.state.value}{extra}")
    return "\n".join(lines)
