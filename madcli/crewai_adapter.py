from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from .config import AppConfig
from .crewai_agent_factory import build_multi_agent_crew, classify_agent_role
from .orchestrator import WorkflowRunResult
from .task_runner import AgentTaskRequest, run_agent_task
from .workflow_store import PlannedTask, WorkflowStore, make_workflow_id


class CrewAIUnavailableError(RuntimeError):
    pass


def require_crewai() -> Any:
    try:
        return importlib.import_module("crewai")
    except ModuleNotFoundError as exc:
        raise CrewAIUnavailableError(
            "CrewAI is not installed. Install it with: python -m pip install "
            "\"multi-agent-dev-cli[crewai]\""
        ) from exc


def crewai_role() -> str:
    return (
        "CrewAI is the optional orchestration layer for planning, delegation, "
        "review routing, and workflow decisions. madcli remains responsible for "
        "executing concrete coding tasks through Codex, Claude Code, or OpenCode."
    )


def _import_base_tool() -> Any:
    """Import BaseTool, compatible with crewai 0.1.x (langchain) and 0.5+ (crewai.tools)."""
    try:
        return importlib.import_module("crewai.tools").BaseTool
    except (ImportError, AttributeError):
        pass
    try:
        return importlib.import_module("langchain.tools").BaseTool
    except ImportError:
        pass
    raise ImportError("Cannot find BaseTool in crewai.tools or langchain.tools")


def build_run_agent_task_tool(
    config: AppConfig,
    *,
    workflow_store: WorkflowStore | None = None,
    workflow_id: str | None = None,
) -> Any:
    require_crewai()
    pydantic_module = importlib.import_module("pydantic")
    BaseTool = _import_base_tool()
    BaseModel = pydantic_module.BaseModel
    Field = pydantic_module.Field

    class RunAgentTaskInput(BaseModel):
        task: str = Field(..., description="Task text to send to the madcli agent.")
        agent_name: str = Field(..., description="Configured madcli agent key.")
        context_files: list[str] = Field(
            default_factory=list,
            description="Existing context files to attach to the run.",
        )
        dry_run: bool = Field(
            default=False,
            description="Create artifacts without invoking the external runtime.",
        )

    class RunMadcliAgentTaskTool(BaseTool):
        name: str = "run_madcli_agent_task"
        description: str = (
            "Dispatch a concrete coding task to one configured madcli agent and "
            "return the run id, status, and artifact directory."
        )
        args_schema: type[BaseModel] = RunAgentTaskInput

        def _run(
            self,
            task: str,
            agent_name: str,
            context_files: list[str] | None = None,
            dry_run: bool = False,
        ) -> str:
            result = run_agent_task(
                AgentTaskRequest(
                    config=config,
                    task=task,
                    agent_name=agent_name,
                    context_files=[Path(path) for path in context_files or []],
                    dry_run=dry_run,
                    stream_output=False,
                )
            )
            if workflow_store and workflow_id:
                workflow_store.append_event(
                    workflow_id,
                    "crewai_delegated_run",
                    {
                        "run_id": result.run_id,
                        "agent": result.agent_name,
                        "runtime": result.runtime,
                        "status": result.status,
                    },
                )
            return (
                f"run_id: {result.run_id}\n"
                f"status: {result.status}\n"
                f"agent: {result.agent_name}\n"
                f"runtime: {result.runtime}\n"
                f"run_dir: {result.run_dir}"
            )

    return RunMadcliAgentTaskTool()


def build_read_run_artifact_tool(config: AppConfig) -> Any:
    require_crewai()
    pydantic_module = importlib.import_module("pydantic")
    BaseTool = _import_base_tool()
    BaseModel = pydantic_module.BaseModel
    Field = pydantic_module.Field

    class ReadRunArtifactInput(BaseModel):
        run_id: str = Field(..., description="madcli run id.")
        artifact_path: str = Field(
            default="outputs/result.md",
            description="Relative artifact path under the run directory.",
        )

    class ReadMadcliRunArtifactTool(BaseTool):
        name: str = "read_madcli_run_artifact"
        description: str = "Read a safe artifact file from a madcli run directory."
        args_schema: type[BaseModel] = ReadRunArtifactInput

        def _run(self, run_id: str, artifact_path: str = "outputs/result.md") -> str:
            runs_dir = config.runs_dir.resolve()
            run_dir = (runs_dir / run_id).resolve()
            run_dir.relative_to(runs_dir)
            target = (run_dir / artifact_path).resolve()
            relative = target.relative_to(run_dir)
            if not target.is_file():
                raise ValueError(f"run artifact not found: {relative.as_posix()}")
            return target.read_text(encoding="utf-8")

    return ReadMadcliRunArtifactTool()


def _build_worker_toolkit(
    config: AppConfig,
    agent_name: str,
    store: WorkflowStore | None = None,
    workflow_id: str | None = None,
) -> list[Any]:
    """Build tools for a specific worker agent based on its role."""
    agent_config = config.agents.get(agent_name)
    if not agent_config:
        return []
    role = classify_agent_role(agent_config)

    tools: list[Any] = [
        build_run_agent_task_tool(
            config,
            workflow_store=store,
            workflow_id=workflow_id,
        ),
        build_read_run_artifact_tool(config),
    ]

    if role == "reviewer":
        tools.append(
            build_read_run_artifact_tool(config),
        )
    return tools


def _build_manager_toolkit(
    config: AppConfig,
    store: WorkflowStore,
    workflow_id: str,
) -> list[Any]:
    """Build oversight tools for the manager agent."""
    tools = [build_read_run_artifact_tool(config)]

    require_crewai()
    pydantic_module = importlib.import_module("pydantic")
    BaseTool = _import_base_tool()
    BaseModel = pydantic_module.BaseModel
    Field = pydantic_module.Field

    class CheckWorkflowStatusInput(BaseModel):
        pass

    class CheckWorkflowStatusTool(BaseTool):
        name: str = "check_workflow_status"
        description: str = "List all tasks in the current workflow with their statuses."
        args_schema: type[BaseModel] = CheckWorkflowStatusInput

        def _run(self) -> str:
            tasks = store.list_tasks(workflow_id)
            lines = ["Current workflow tasks:"]
            for t in tasks:
                lines.append(
                    f"  {t.task_id}: {t.status} (agent={t.agent}, "
                    f"run={t.run_id or '-'}, review={t.review_run_id or '-'})"
                )
            return "\n".join(lines)

    tools.append(CheckWorkflowStatusTool())

    class SummarizeProgressInput(BaseModel):
        pass

    class SummarizeProgressTool(BaseTool):
        name: str = "summarize_progress"
        description: str = "Summarize workflow completion/failure/pending counts."
        args_schema: type[BaseModel] = SummarizeProgressInput

        def _run(self) -> str:
            tasks = store.list_tasks(workflow_id)
            counts = {"succeeded": 0, "failed": 0, "running": 0, "pending": 0,
                       "blocked": 0, "reviewed": 0, "review_failed": 0}
            for t in tasks:
                key = t.status if t.status in counts else "pending"
                counts[key] = counts.get(key, 0) + 1
            return (
                f"Progress: {counts['succeeded'] + counts['reviewed']} done, "
                f"{counts['failed'] + counts['review_failed']} failed, "
                f"{counts['pending'] + counts['running']} remaining"
            )

    tools.append(SummarizeProgressTool())

    class ListWorkerAgentsInput(BaseModel):
        pass

    class ListWorkerAgentsTool(BaseTool):
        name: str = "list_worker_agents"
        description: str = "List all available worker agents with their capabilities."
        args_schema: type[BaseModel] = ListWorkerAgentsInput

        def _run(self) -> str:
            from .crewai_agent_factory import classify_agent_role
            lines = ["Available worker agents:"]
            for name, agent in sorted(config.agents.items()):
                role = classify_agent_role(agent)
                lines.append(
                    f"  - {name} ({role}): {agent.description[:100]}"
                )
            return "\n".join(lines)

    tools.append(ListWorkerAgentsTool())

    class GetTaskDetailInput(BaseModel):
        task_id: str = Field(..., description="Task ID to inspect.")

    class GetTaskDetailTool(BaseTool):
        name: str = "get_task_detail"
        description: str = "Get detailed status and artifact paths for a specific task."
        args_schema: type[BaseModel] = GetTaskDetailInput

        def _run(self, task_id: str) -> str:
            try:
                task = store.load_task(workflow_id, task_id)
                return (
                    f"Task: {task.task_id}\n"
                    f"Status: {task.status}\n"
                    f"Agent: {task.agent}\n"
                    f"Run ID: {task.run_id or '-'}\n"
                    f"Review Run ID: {task.review_run_id or '-'}\n"
                    f"Task text: {task.task[:200]}"
                )
            except FileNotFoundError:
                return f"Task '{task_id}' not found in workflow '{workflow_id}'"

    tools.append(GetTaskDetailTool())
    return tools


def run_crewai_workflow(
    *,
    config: AppConfig,
    store: WorkflowStore,
    goal: str,
    manager_agent_name: str,
) -> WorkflowRunResult:
    crewai = require_crewai()
    workflow_id = make_workflow_id(goal)
    store.create_workflow(
        workflow_id=workflow_id,
        goal=goal,
        tasks=[
            PlannedTask(
                task_id=f"crewai-{name}",
                agent=name,
                task=f"CrewAI-managed task for {name}",
            )
            for name in sorted(config.agents)
        ],
    )
    store.update_workflow_status(workflow_id, "running")

    tool_builders: dict[str, Any] = {}
    for agent_name in config.agents:
        tool_builders[agent_name] = _build_worker_toolkit(
            config, agent_name, store, workflow_id
        )
    tool_builders["manager"] = _build_manager_toolkit(config, store, workflow_id)

    workers, manager_agent, delegation_task = build_multi_agent_crew(
        config=config,
        goal=goal,
        manager_agent_name=manager_agent_name,
        tool_builders=tool_builders,
        crewai_module=crewai,
    )

    all_agents = [manager_agent] + workers
    crew = crewai.Crew(
        agents=all_agents,
        tasks=[delegation_task],
        process=crewai.Process.hierarchical,
        manager_agent=manager_agent,
    )
    try:
        crew_result = crew.kickoff()
    except Exception:
        for name in sorted(config.agents):
            store.update_task(workflow_id, f"crewai-{name}", status="failed")
        store.update_workflow_status(workflow_id, "failed")
        raise
    store.append_event(
        workflow_id,
        "crewai_finished",
        {"result": str(crew_result)},
    )
    for name in sorted(config.agents):
        store.update_task(workflow_id, f"crewai-{name}", status="succeeded")
    store.update_workflow_status(workflow_id, "succeeded")
    return WorkflowRunResult(
        workflow_id=workflow_id,
        status="succeeded",
        workflow_dir=store.workflow_dir(workflow_id),
    )
