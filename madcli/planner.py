from __future__ import annotations

import json
import re

from .config import AppConfig
from .plan_validator import validate_plan
from .task_runner import AgentTaskRequest, run_agent_task
from .workflow_store import PlannedTask


def parse_planned_tasks(text: str, config: AppConfig | None = None) -> list[PlannedTask]:
    data = json.loads(_extract_json_object(text))
    raw_tasks = data.get("tasks") if isinstance(data, dict) else data
    if not isinstance(raw_tasks, list):
        raise ValueError("planner output must contain a tasks array")
    tasks: list[PlannedTask] = []
    for index, item in enumerate(raw_tasks, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"planner task {index} must be an object")
        task_id = str(item.get("id") or item.get("task_id") or "").strip()
        agent = str(item.get("agent") or "").strip()
        task_text = str(item.get("task") or "").strip()
        if not task_id or not agent or not task_text:
            raise ValueError(f"planner task {index} must define id, agent, and task")
        depends_on = item.get("depends_on") or []
        if not isinstance(depends_on, list):
            raise ValueError(f"planner task {task_id} depends_on must be a list")
        tasks.append(
            PlannedTask(
                task_id=task_id,
                agent=agent,
                task=task_text,
                depends_on=[str(value) for value in depends_on],
                review_by=(
                    str(item["review_by"]).strip()
                    if item.get("review_by") is not None
                    else None
                ),
            )
        )
    if config:
        errors = validate_plan(tasks, config)
        if errors:
            raise ValueError("plan validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
    return tasks


def plan_tasks_with_agent(
    *,
    config: AppConfig,
    goal: str,
    planner_agent: str,
    dry_run: bool = False,
    task_runner=run_agent_task,
) -> list[PlannedTask]:
    agent_list = ", ".join(f'"{name}"' for name in sorted(config.agents))
    agent_details = "\n".join(
        f'- "{name}": {agent.description} (runtime: {agent.runtime})'
        for name, agent in sorted(config.agents.items())
    )
    prompt = (
        "You are the workflow commander for madcli. Split the user's goal into "
        "concrete coding-runtime tasks and assign each task to one configured "
        "agent. Do not implement the tasks yourself.\n\n"
        "Choose agents based on their capabilities:\n"
        f"{agent_details}\n\n"
        "Return only JSON with this shape:\n"
        "{\n"
        '  "tasks": [\n'
        "    {\n"
        '      "id": "short-stable-id",\n'
        f'      "agent": {agent_list},\n'
        '      "task": "specific task for that agent",\n'
        '      "depends_on": [],\n'
        '      "review_by": "agent-name-or-null",\n'
        '      "acceptance_criteria": ["criterion 1", "criterion 2"],\n'
        '      "retry_count": 0\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Goal:\n{goal}"
    )
    result = task_runner(
        AgentTaskRequest(
            config=config,
            task=prompt,
            agent_name=planner_agent,
            workdir=config.default_workdir,
            dry_run=dry_run,
            prompt_mode="task",
            stream_output=False,
        )
    )
    if not result.ok:
        raise ValueError(f"planner agent failed: {result.stderr or result.stdout}")
    planner_output = _read_last_message(result.run_dir) or result.stdout
    return parse_planned_tasks(planner_output)


def _read_last_message(run_dir) -> str:
    path = run_dir / "outputs" / "last_message.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _extract_json_object(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    raise ValueError("planner output does not contain JSON")
