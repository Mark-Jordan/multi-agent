from __future__ import annotations

from dataclasses import replace
import tempfile
from pathlib import Path
import types
import unittest
from unittest.mock import patch

from madcli.config import default_config
from madcli.crewai_adapter import (
    build_run_agent_task_tool,
    CrewAIUnavailableError,
    crewai_role,
    require_crewai,
    run_crewai_workflow,
)
from madcli.task_runner import AgentTaskResult
from madcli.workflow_store import WorkflowStore


class CrewAIAdapterTests(unittest.TestCase):
    def test_require_crewai_raises_clear_error_when_package_is_missing(self) -> None:
        with patch("madcli.crewai_adapter.importlib.import_module") as import_module:
            import_module.side_effect = ModuleNotFoundError("No module named 'crewai'")

            with self.assertRaisesRegex(CrewAIUnavailableError, "pip install .*crewai"):
                require_crewai()

    def test_crewai_role_explains_boundaries(self) -> None:
        role = crewai_role()

        self.assertIn("orchestration", role)
        self.assertIn("madcli remains responsible", role)

    def test_run_crewai_workflow_builds_hierarchical_crew_with_madcli_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            captured = {}
            agent_count = [0]

            class FakeAgent:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs
                    agent_count[0] += 1

            class FakeTask:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

            class FakeCrew:
                def __init__(self, **kwargs):
                    captured["crew"] = kwargs

                def kickoff(self):
                    captured["kickoff"] = True
                    return "crew finished"

            fake_crewai = types.SimpleNamespace(
                Agent=FakeAgent,
                Task=FakeTask,
                Crew=FakeCrew,
                Process=types.SimpleNamespace(hierarchical="hierarchical"),
            )

            def fake_import(name):
                if name == "crewai":
                    return fake_crewai
                if name == "crewai.tools":
                    return types.SimpleNamespace(BaseTool=object)
                if name == "pydantic":
                    def fake_field(default=None, **_kwargs):
                        return default
                    return types.SimpleNamespace(
                        BaseModel=object,
                        Field=fake_field,
                    )
                raise ModuleNotFoundError(name)

            with patch("madcli.crewai_adapter.importlib.import_module", side_effect=fake_import):
                result = run_crewai_workflow(
                    config=config,
                    store=WorkflowStore(root / "workflows"),
                    goal="Build autonomous orchestration",
                    manager_agent_name="codex_reviewer",
                )

            self.assertEqual(result.status, "succeeded")
            self.assertTrue(captured["kickoff"])
            self.assertEqual(captured["crew"]["process"], "hierarchical")
            self.assertIn("manager_agent", captured["crew"])
            manager_kwargs = captured["crew"]["manager_agent"].kwargs
            self.assertEqual(manager_kwargs["role"], "madcli workflow commander")
            self.assertTrue("allow_delegation" in manager_kwargs)
            agents = captured["crew"]["agents"]
            self.assertGreaterEqual(len(agents), len(config.agents))

    def test_crewai_run_tool_records_delegated_run_event_when_workflow_is_known(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                default_config(),
                runs_dir=root / "runs",
                default_workdir=root,
            )
            store = WorkflowStore(root / "workflows")
            store.create_workflow(
                workflow_id="workflow-1",
                goal="Coordinate work",
                tasks=[],
            )

            class FakeBaseTool:
                pass

            def fake_field(default=None, **_kwargs):
                return default

            def fake_import(name):
                if name == "crewai":
                    return types.SimpleNamespace()
                if name == "crewai.tools":
                    return types.SimpleNamespace(BaseTool=FakeBaseTool)
                if name == "pydantic":
                    return types.SimpleNamespace(BaseModel=object, Field=fake_field)
                raise ModuleNotFoundError(name)

            def fake_run_agent_task(request):
                return AgentTaskResult(
                    run_id="worker-run",
                    run_dir=root / "runs" / "worker-run",
                    status="succeeded",
                    ok=True,
                    runtime="fake",
                    agent_name=request.agent_name,
                    stdout="",
                    stderr="",
                )

            with patch("madcli.crewai_adapter.importlib.import_module", side_effect=fake_import):
                with patch("madcli.crewai_adapter.run_agent_task", side_effect=fake_run_agent_task):
                    tool = build_run_agent_task_tool(
                        config,
                        workflow_store=store,
                        workflow_id="workflow-1",
                    )
                    output = tool._run(
                        task="Implement delegated task",
                        agent_name="strategy_engineer",
                    )

            self.assertIn("run_id: worker-run", output)
            events = "\n".join(store.read_events("workflow-1"))
            self.assertIn("crewai_delegated_run", events)
            self.assertIn("worker-run", events)


if __name__ == "__main__":
    unittest.main()
