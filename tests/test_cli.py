from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from madcli.cli import main
from madcli.config import AgentConfig, CredentialProfile, RuntimeConfig, default_config, save_config
from madcli.orchestrator import WorkflowRunResult


class CliTests(unittest.TestCase):
    def test_run_dry_run_copies_context_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "madcli.config.json"
            runs_dir = root / "runs"
            config = replace(
                default_config(),
                runs_dir=runs_dir,
                default_workdir=root,
            )
            save_config(config, config_path)
            notes_path = root / "notes.md"
            notes_path.write_text("# Notes\n\nCarry this into the run.\n", encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                try:
                    return_code = main(
                        [
                            "--config",
                            str(config_path),
                            "run",
                            "smoke task",
                            "--agent",
                            "strategy_engineer",
                            "--dry-run",
                            "--context-file",
                            str(notes_path),
                        ]
                    )
                except SystemExit as exc:
                    return_code = int(exc.code)

            self.assertEqual(return_code, 0, stderr.getvalue())
            run_dirs = list(runs_dir.iterdir())
            self.assertEqual(len(run_dirs), 1)
            copied = run_dirs[0] / "context" / "context_file_1_notes.md"
            self.assertTrue(copied.exists())
            self.assertIn(
                "Carry this into the run.",
                copied.read_text(encoding="utf-8"),
            )

    def test_run_rejects_missing_context_file_before_creating_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "madcli.config.json"
            runs_dir = root / "runs"
            config = replace(
                default_config(),
                runs_dir=runs_dir,
                default_workdir=root,
            )
            save_config(config, config_path)

            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                return_code = main(
                    [
                        "--config",
                        str(config_path),
                        "run",
                        "smoke task",
                        "--dry-run",
                        "--context-file",
                        str(root / "missing.md"),
                    ]
                )

            self.assertEqual(return_code, 1)
            self.assertIn("context file not found", stderr.getvalue())
            self.assertFalse(runs_dir.exists())

    def test_run_dry_run_uses_agent_active_model_and_credential(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "madcli.config.json"
            config = default_config()
            agent = config.agents["codex_reviewer"]
            runtime = config.runtimes["codex"]
            config = replace(
                config,
                runs_dir=root / "runs",
                default_workdir=root,
                runtimes={
                    **config.runtimes,
                    "codex": RuntimeConfig(
                        name="codex",
                        command=runtime.command,
                        credentials=[
                            CredentialProfile(
                                name="primary",
                                base_url="https://one.example/v1",
                                api_key_env="OPENAI_API_KEY_ONE",
                            ),
                            CredentialProfile(
                                name="backup",
                                base_url="https://two.example/v1",
                                api_key_env="OPENAI_API_KEY_TWO",
                            ),
                        ],
                    ),
                },
                agents={
                    **config.agents,
                    "codex_reviewer": AgentConfig(
                        name=agent.name,
                        runtime=agent.runtime,
                        agent=agent.agent,
                        model=agent.model,
                        description=agent.description,
                        active_model="gpt-5.1-codex",
                        active_credential="backup",
                    ),
                },
            )
            save_config(config, config_path)

            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                return_code = main(
                    [
                        "--config",
                        str(config_path),
                        "run",
                        "review task",
                        "--agent",
                        "codex_reviewer",
                        "--dry-run",
                    ]
                )

            self.assertEqual(return_code, 0, stderr.getvalue())
            output = stdout.getvalue()
            self.assertIn("credential: backup", output)
            run_dirs = list((root / "runs").iterdir())
            self.assertEqual(len(run_dirs), 1)
            command = json.loads(
                (run_dirs[0] / "outputs" / "command.json").read_text(encoding="utf-8")
            )
            self.assertIn("gpt-5.1-codex", command)
            self.assertIn('model_provider="madcli_backup"', command)

    def test_workflow_run_dry_run_executes_worker_then_reviewer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "madcli.config.json"
            runs_dir = root / "runs"
            config = replace(
                default_config(),
                runs_dir=runs_dir,
                default_workdir=root,
            )
            save_config(config, config_path)
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "build-feature",
                                "agent": "strategy_engineer",
                                "task": "Build the feature",
                                "review_by": "codex_reviewer",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                return_code = main(
                    [
                        "--config",
                        str(config_path),
                        "workflow",
                        "run",
                        "Build autonomous orchestration",
                        "--plan-file",
                        str(plan_path),
                        "--dry-run",
                    ]
                )

            self.assertEqual(return_code, 0, stderr.getvalue())
            self.assertIn("workflow_id:", stdout.getvalue())
            workflows_dir = root / "workflows"
            workflow_dirs = list(workflows_dir.iterdir())
            self.assertEqual(len(workflow_dirs), 1)
            run_dirs = list(runs_dir.iterdir())
            self.assertEqual(len(run_dirs), 2)
            task_path = workflow_dirs[0] / "tasks" / "build-feature.json"
            task_data = json.loads(task_path.read_text(encoding="utf-8"))
            self.assertEqual(task_data["status"], "reviewed")
            self.assertTrue(task_data["run_id"])
            self.assertTrue(task_data["review_run_id"])

    def test_workflow_run_requires_plan_file_or_planner_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "madcli.config.json"
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            save_config(config, config_path)

            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                return_code = main(
                    [
                        "--config",
                        str(config_path),
                        "workflow",
                        "run",
                        "Build autonomous orchestration",
                        "--dry-run",
                    ]
                )

            self.assertEqual(return_code, 1)
            self.assertIn("requires --plan-file, --template, or --planner-agent", stderr.getvalue())

    def test_workflow_dry_run_with_planner_agent_requires_plan_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "madcli.config.json"
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            save_config(config, config_path)

            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                return_code = main(
                    [
                        "--config",
                        str(config_path),
                        "workflow",
                        "run",
                        "Build autonomous orchestration",
                        "--planner-agent",
                        "codex_reviewer",
                        "--dry-run",
                    ]
                )

            self.assertEqual(return_code, 1)
            self.assertIn("dry-run workflows require --plan-file", stderr.getvalue())

    def test_workflow_run_crewai_backend_uses_manager_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "madcli.config.json"
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            save_config(config, config_path)
            captured = {}

            def fake_crewai_workflow(*, config, store, goal, manager_agent_name):
                captured["goal"] = goal
                captured["manager_agent_name"] = manager_agent_name
                return WorkflowRunResult(
                    workflow_id="crew-wf",
                    status="succeeded",
                    workflow_dir=root / "workflows" / "crew-wf",
                )

            stdout = StringIO()
            stderr = StringIO()
            with patch("madcli.cli.run_crewai_workflow", side_effect=fake_crewai_workflow):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    return_code = main(
                        [
                            "--config",
                            str(config_path),
                            "workflow",
                            "run",
                            "Build autonomous orchestration",
                            "--backend",
                            "crewai",
                            "--manager-agent",
                            "codex_reviewer",
                        ]
                    )

            self.assertEqual(return_code, 0, stderr.getvalue())
            self.assertEqual(captured["goal"], "Build autonomous orchestration")
            self.assertEqual(captured["manager_agent_name"], "codex_reviewer")
            self.assertIn("workflow_id: crew-wf", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
