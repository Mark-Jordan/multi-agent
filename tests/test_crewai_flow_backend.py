from __future__ import annotations

from dataclasses import replace
import tempfile
from pathlib import Path
import unittest

from madcli.config import default_config, save_config
from madcli.crewai_flow_backend import (
    FlowOrchestrator,
    FlowState,
    FlowStateMachine,
    flow_status_report,
    run_flow_workflow,
)
from madcli.orchestrator import AgentTaskResult, run_agent_task, AgentTaskRequest
from madcli.workflow_store import PlannedTask, WorkflowStore


def _make_dry_result(run_id="run-1", ok=True) -> AgentTaskResult:
    import tempfile
    run_dir = Path(tempfile.mkdtemp())
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs" / "result.md").write_text("# Result", encoding="utf-8")
    return AgentTaskResult(
        run_id=run_id,
        status="succeeded" if ok else "failed",
        ok=ok,
        agent_name="test-agent",
        runtime="test-runtime",
        command=["echo", "test"],
        stdout="ok",
        stderr="",
        run_dir=run_dir,
    )


def _failing_runner(req: AgentTaskRequest) -> AgentTaskResult:
    return _make_dry_result(ok=False)


class FlowStateMachineTests(unittest.TestCase):
    def test_transitions_record_in_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowStore(Path(tmp))
            store.create_workflow(
                workflow_id="wf-1",
                goal="test",
                tasks=[
                    PlannedTask(task_id="t1", agent="a1", task="do work")
                ],
            )
            sm = FlowStateMachine("wf-1", store)
            sm.transition(FlowState.START)
            sm.transition(FlowState.PLAN_READY)
            sm.transition(FlowState.TASK_DISPATCHING, task_id="t1")
            sm.transition(FlowState.TASK_RUNNING, task_id="t1")
            sm.transition(FlowState.TASK_SUCCEEDED, task_id="t1", run_id="run-1")
            sm.transition(FlowState.ALL_DONE)

            self.assertEqual(sm.current, FlowState.ALL_DONE)
            self.assertEqual(len(sm.history), 6)
            self.assertEqual(sm.history[0].state, FlowState.START)
            self.assertEqual(sm.history[2].task_id, "t1")

    def test_restore_recovers_previous_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowStore(Path(tmp))
            store.create_workflow(
                workflow_id="wf-1",
                goal="test",
                tasks=[
                    PlannedTask(task_id="t1", agent="a1", task="do work")
                ],
            )
            sm1 = FlowStateMachine("wf-1", store)
            sm1.transition(FlowState.START)
            sm1.transition(FlowState.PLAN_READY)
            sm1.transition(FlowState.TASK_DISPATCHING, task_id="t1")
            sm1.transition(FlowState.TASK_RUNNING, task_id="t1", run_id="run-1")

            sm2 = FlowStateMachine.restore("wf-1", store)
            self.assertEqual(sm2.current, FlowState.TASK_RUNNING)
            self.assertEqual(len(sm2.history), 4)
            self.assertEqual(sm2.history[-1].run_id, "run-1")


class FlowOrchestratorTests(unittest.TestCase):
    def _config_and_store(self, tmp: str):
        root = Path(tmp)
        config = replace(
            default_config(),
            runs_dir=root / "runs",
            default_workdir=root,
        )
        store = WorkflowStore(root / "workflows")
        return config, store

    def test_run_simple_task_plan_reaches_all_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config, store = self._config_and_store(tmp)
            tasks = [
                PlannedTask(task_id="build", agent="strategy_engineer", task="build it"),
                PlannedTask(task_id="review", agent="codex_reviewer", task="review it",
                            depends_on=["build"]),
            ]
            orchestrator = FlowOrchestrator(config, store)
            result = orchestrator.run(
                goal="test flow",
                tasks=tasks,
                dry_run=True,
            )
            self.assertEqual(result.status, "succeeded")
            sm = FlowStateMachine.restore(result.workflow_id, store)
            self.assertEqual(sm.current, FlowState.ALL_DONE)

    def test_failing_task_goes_to_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config, store = self._config_and_store(tmp)
            failing_orch = FlowOrchestrator(config, store)
            failing_orch._orchestrator.task_runner = _failing_runner
            tasks = [
                PlannedTask(task_id="risky", agent="strategy_engineer", task="risky work"),
            ]
            result = failing_orch.run(
                goal="test failure",
                tasks=tasks,
                dry_run=True,
            )
            self.assertEqual(result.status, "failed")
            sm = FlowStateMachine.restore(result.workflow_id, store)
            self.assertEqual(sm.current, FlowState.ERROR)

    def test_allow_failure_task_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config, store = self._config_and_store(tmp)

            class ConditionalRunner:
                def __init__(self) -> None:
                    self.calls = 0
                def __call__(self, request):
                    self.calls += 1
                    ok = request.agent_name != "strategy_engineer"
                    return _make_dry_result(run_id=f"run-{self.calls}", ok=ok)

            failing_orch = FlowOrchestrator(config, store)
            failing_orch._orchestrator.task_runner = ConditionalRunner()
            tasks = [
                PlannedTask(task_id="optional", agent="strategy_engineer",
                            task="optional work", allow_failure=True),
                PlannedTask(task_id="required", agent="codex_reviewer",
                            task="required work"),
            ]
            result = failing_orch.run(
                goal="test allow failure",
                tasks=tasks,
                dry_run=True,
            )
            self.assertEqual(result.status, "succeeded")
            sm = FlowStateMachine.restore(result.workflow_id, store)
            self.assertEqual(sm.current, FlowState.ALL_DONE)

    def test_flow_status_report_contains_state_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config, store = self._config_and_store(tmp)
            tasks = [
                PlannedTask(task_id="t1", agent="strategy_engineer", task="do it"),
            ]
            orchestrator = FlowOrchestrator(config, store)
            result = orchestrator.run(goal="test", tasks=tasks, dry_run=True)
            report = flow_status_report(result.workflow_id, store)
            self.assertIn("all_done", report)
            self.assertIn(result.workflow_id, report)

    def test_run_flow_workflow_with_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            store = WorkflowStore(root / "workflows")
            tasks = [
                PlannedTask(task_id="t1", agent="strategy_engineer", task="do work"),
            ]
            result = run_flow_workflow(
                config=config,
                store=store,
                goal="test",
                tasks=tasks,
                dry_run=True,
            )
            self.assertEqual(result.status, "succeeded")

    def test_run_flow_workflow_from_plan_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            store = WorkflowStore(root / "workflows")
            plan_path = root / "plan.json"
            plan_path.write_text(
                '{"tasks": [{"id": "t1", "agent": "strategy_engineer", "task": "do it"}]}',
                encoding="utf-8",
            )
            result = run_flow_workflow(
                config=config,
                store=store,
                goal="test from file",
                plan_file=plan_path,
                dry_run=True,
            )
            self.assertEqual(result.status, "succeeded")


if __name__ == "__main__":
    unittest.main()
