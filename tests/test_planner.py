from __future__ import annotations

from dataclasses import replace
import tempfile
import unittest
from pathlib import Path

from madcli.config import default_config
from madcli.planner import parse_planned_tasks, plan_tasks_with_agent
from madcli.task_runner import AgentTaskResult


class PlannerTests(unittest.TestCase):
    def test_parse_planned_tasks_accepts_json_object_with_tasks(self) -> None:
        tasks = parse_planned_tasks(
            """
            Here is the plan:

            ```json
            {
              "tasks": [
                {
                  "id": "build-feature",
                  "agent": "strategy_engineer",
                  "task": "Build the feature",
                  "depends_on": [],
                  "review_by": "codex_reviewer"
                }
              ]
            }
            ```
            """
        )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_id, "build-feature")
        self.assertEqual(tasks[0].agent, "strategy_engineer")
        self.assertEqual(tasks[0].review_by, "codex_reviewer")

    def test_plan_tasks_with_agent_runs_planner_and_parses_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            calls = []

            def fake_runner(request):
                calls.append(request)
                return AgentTaskResult(
                    run_id="planner-run",
                    run_dir=root / "runs" / "planner-run",
                    status="succeeded",
                    ok=True,
                    runtime="fake",
                    agent_name=request.agent_name,
                    stdout='{"tasks":[{"id":"review","agent":"codex_reviewer","task":"Review repo"}]}',
                    stderr="",
                )

            tasks = plan_tasks_with_agent(
                config=config,
                goal="Review this project",
                planner_agent="codex_reviewer",
                task_runner=fake_runner,
            )

            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0].agent_name, "codex_reviewer")
            self.assertIn("Return only JSON", calls[0].task)
            self.assertEqual(tasks[0].task_id, "review")

    def test_plan_tasks_with_agent_prefers_last_message_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            run_dir = root / "runs" / "planner-run"
            outputs_dir = run_dir / "outputs"
            outputs_dir.mkdir(parents=True)
            (outputs_dir / "last_message.txt").write_text(
                '{"tasks":[{"id":"build","agent":"strategy_engineer","task":"Build feature"}]}',
                encoding="utf-8",
            )

            def fake_runner(request):
                return AgentTaskResult(
                    run_id="planner-run",
                    run_dir=run_dir,
                    status="succeeded",
                    ok=True,
                    runtime="fake",
                    agent_name=request.agent_name,
                    stdout="runtime logs without json",
                    stderr="",
                )

            tasks = plan_tasks_with_agent(
                config=config,
                goal="Build this",
                planner_agent="codex_reviewer",
                task_runner=fake_runner,
            )

            self.assertEqual(tasks[0].task_id, "build")


if __name__ == "__main__":
    unittest.main()
