from __future__ import annotations

from dataclasses import replace
import tempfile
import unittest
from pathlib import Path

from madcli.config import default_config
from madcli.orchestrator import WorkflowOrchestrator
from madcli.task_runner import AgentTaskResult
from madcli.workflow_store import PlannedTask, WorkflowStore


class FakeTaskRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, request):
        run_number = len(self.calls) + 1
        run_id = f"run-{run_number}"
        run_dir = request.runs_dir / run_id
        outputs_dir = run_dir / "outputs"
        outputs_dir.mkdir(parents=True)
        (outputs_dir / "result.md").write_text(
            f"# Result\n\nagent={request.agent_name}\ntask={request.task}\n",
            encoding="utf-8",
        )
        self.calls.append(
            {
                "agent": request.agent_name,
                "task": request.task,
                "context_files": [Path(path) for path in request.context_files],
            }
        )
        return AgentTaskResult(
            run_id=run_id,
            run_dir=run_dir,
            status="dry_run" if request.dry_run else "succeeded",
            ok=True,
            runtime="fake",
            agent_name=request.agent_name,
            stdout="",
            stderr="",
        )


class FailingTaskRunner:
    """A runner that fails for the first N calls, then succeeds."""

    def __init__(self, fail_count: int = 2) -> None:
        self.fail_count = fail_count
        self.attempts = 0
        self.calls: list[dict[str, object]] = []

    def __call__(self, request):
        self.attempts += 1
        run_number = self.attempts
        run_id = f"run-{run_number}"
        run_dir = request.runs_dir / run_id
        outputs_dir = run_dir / "outputs"
        outputs_dir.mkdir(parents=True)
        (outputs_dir / "result.md").write_text("", encoding="utf-8")
        self.calls.append(
            {
                "agent": request.agent_name,
                "task": request.task,
                "context_files": [Path(path) for path in request.context_files],
            }
        )
        ok = self.attempts > self.fail_count
        return AgentTaskResult(
            run_id=run_id,
            run_dir=run_dir,
            status="succeeded" if ok else "failed",
            ok=ok,
            runtime="fake",
            agent_name=request.agent_name,
            stdout="",
            stderr="" if ok else "simulated failure",
        )


class WorkflowOrchestratorTests(unittest.TestCase):
    def test_worker_task_is_automatically_reviewed_with_worker_result_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            store = WorkflowStore(root / "workflows")
            runner = FakeTaskRunner()
            orchestrator = WorkflowOrchestrator(config, store, runner)

            result = orchestrator.run_plan(
                goal="Build feature",
                tasks=[
                    PlannedTask(
                        task_id="build-feature",
                        agent="strategy_engineer",
                        task="Build the feature",
                        review_by="codex_reviewer",
                    )
                ],
                dry_run=True,
            )

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(len(runner.calls), 2)
            self.assertEqual(runner.calls[0]["agent"], "strategy_engineer")
            self.assertEqual(runner.calls[1]["agent"], "codex_reviewer")
            self.assertIn("Review the completed task", str(runner.calls[1]["task"]))
            self.assertTrue(
                any(
                    path.parts[-4:] == ("runs", "run-1", "outputs", "result.md")
                    for path in runner.calls[1]["context_files"]
                )
            )
            task = store.load_task(result.workflow_id, "build-feature")
            self.assertEqual(task.status, "reviewed")
            self.assertEqual(task.run_id, "run-1")
            self.assertEqual(task.review_run_id, "run-2")

    def test_dependency_failure_prevents_dependent_task_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            store = WorkflowStore(root / "workflows")
            runner = FakeTaskRunner()
            orchestrator = WorkflowOrchestrator(config, store, runner)

            result = orchestrator.run_plan(
                goal="Build feature",
                tasks=[
                    PlannedTask(
                        task_id="first",
                        agent="strategy_engineer",
                        task="First task",
                        depends_on=["missing"],
                    )
                ],
                dry_run=True,
            )

            self.assertEqual(result.status, "failed")
            self.assertEqual(runner.calls, [])
            task = store.load_task(result.workflow_id, "first")
            self.assertEqual(task.status, "blocked")


    def test_retry_exhausts_then_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            store = WorkflowStore(root / "workflows")
            runner = FailingTaskRunner(fail_count=3)
            orchestrator = WorkflowOrchestrator(config, store, runner)

            result = orchestrator.run_plan(
                goal="Retry test",
                tasks=[
                    PlannedTask(
                        task_id="flaky-task",
                        agent="strategy_engineer",
                        task="Flaky work",
                        retry_count=2,
                        retry_delay=0.01,
                    )
                ],
                dry_run=False,
            )

            self.assertEqual(result.status, "failed")
            self.assertEqual(runner.attempts, 3)

    def test_retry_eventually_succeeds_within_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            store = WorkflowStore(root / "workflows")
            runner = FailingTaskRunner(fail_count=1)
            orchestrator = WorkflowOrchestrator(config, store, runner)

            result = orchestrator.run_plan(
                goal="Retry succeed test",
                tasks=[
                    PlannedTask(
                        task_id="flaky-task",
                        agent="strategy_engineer",
                        task="Flaky work",
                        retry_count=3,
                        retry_delay=0.01,
                    )
                ],
                dry_run=False,
            )

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(runner.attempts, 2)

    def test_allow_failure_does_not_block_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            store = WorkflowStore(root / "workflows")

            class ConditionalRunner:
                def __init__(self) -> None:
                    self.attempts = 0
                    self.calls: list[dict[str, object]] = []

                def __call__(self, request):
                    self.attempts += 1
                    run_id = f"run-{self.attempts}"
                    run_dir = request.runs_dir / run_id
                    outputs_dir = run_dir / "outputs"
                    outputs_dir.mkdir(parents=True)
                    (outputs_dir / "result.md").write_text("", encoding="utf-8")
                    self.calls.append({"agent": request.agent_name, "task": request.task})
                    ok = request.agent_name == "claude_engineer"
                    return AgentTaskResult(
                        run_id=run_id,
                        run_dir=run_dir,
                        status="succeeded" if ok else "failed",
                        ok=ok,
                        runtime="fake",
                        agent_name=request.agent_name,
                        stdout="",
                        stderr="" if ok else "error",
                    )

            orchestrator = WorkflowOrchestrator(config, store, ConditionalRunner())

            result = orchestrator.run_plan(
                goal="Allow failure test",
                tasks=[
                    PlannedTask(
                        task_id="required-task",
                        agent="claude_engineer",
                        task="Required work",
                    ),
                    PlannedTask(
                        task_id="optional-task",
                        agent="strategy_engineer",
                        task="Optional work",
                        depends_on=["required-task"],
                        allow_failure=True,
                    ),
                ],
                dry_run=False,
            )

            self.assertEqual(result.status, "succeeded")
            opt_task = store.load_task(result.workflow_id, "optional-task")
            self.assertEqual(opt_task.status, "failed")
            req_task = store.load_task(result.workflow_id, "required-task")
            self.assertEqual(req_task.status, "succeeded")


if __name__ == "__main__":
    unittest.main()
