from __future__ import annotations

import json
from pathlib import Path

from .workflow_store import PlannedTask


BUILTIN_TEMPLATES_DIR = Path(__file__).parent / "templates"

TEMPLATE_DESCRIPTIONS = {
    "implement-review": "Standard implement-then-review workflow with acceptance criteria",
    "research-plan-implement": "Research, plan, implement, and verify for technical exploration",
    "refactor-verify": "Refactor, test, review, with rollback plan",
    "multi-perspective-review": "Multiple agents review in parallel, then synthesize findings",
    "debug-fix-verify": "Diagnose, fix, test, and regression verification for bug fixes",
}


def list_templates() -> dict[str, str]:
    return dict(TEMPLATE_DESCRIPTIONS)


def load_template(name: str, templates_dir: Path | None = None) -> dict:
    search_dirs = [BUILTIN_TEMPLATES_DIR]
    if templates_dir and templates_dir.exists():
        search_dirs.insert(0, templates_dir)

    for directory in search_dirs:
        path = directory / f"{name}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

    available = ", ".join(sorted(TEMPLATE_DESCRIPTIONS))
    raise ValueError(
        f"template '{name}' not found. Available built-in templates: {available}"
    )


def _substitute(value: object, variables: dict[str, str]) -> object:
    if isinstance(value, str):
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            value = value.replace(placeholder, var_value)
        return value
    if isinstance(value, list):
        return [_substitute(item, variables) for item in value]
    if isinstance(value, dict):
        return {k: _substitute(v, variables) for k, v in value.items()}
    return value


def render_template(template_data: dict, variables: dict[str, str]) -> list[PlannedTask]:
    raw_tasks = template_data.get("tasks", [])
    tasks: list[PlannedTask] = []
    for item in raw_tasks:
        task_dict: dict[str, object] = {}
        for key, value in item.items():
            task_dict[key] = _substitute(value, variables)

        task_id = str(task_dict.get("id", ""))
        agent = str(task_dict.get("agent", ""))
        task_text = str(task_dict.get("task", ""))
        if not task_id or not agent or not task_text:
            raise ValueError(
                f"template task {len(tasks) + 1} must define id, agent, and task"
            )
        depends_on = task_dict.get("depends_on", [])
        if isinstance(depends_on, list):
            depends_on = [str(d) for d in depends_on]

        tasks.append(
            PlannedTask(
                task_id=task_id,
                agent=agent,
                task=task_text,
                depends_on=list(depends_on) if depends_on else None,
                review_by=(
                    str(task_dict["review_by"])
                    if task_dict.get("review_by") is not None
                    else None
                ),
                retry_count=int(task_dict.get("retry_count", 0)),
                retry_delay=float(task_dict.get("retry_delay", 5.0)),
                fallback_task_id=(
                    str(task_dict["fallback_task_id"])
                    if task_dict.get("fallback_task_id") is not None
                    else None
                ),
                allow_failure=bool(task_dict.get("allow_failure", False)),
                acceptance_criteria=(
                    [str(c) for c in criteria]
                    if (criteria := task_dict.get("acceptance_criteria"))
                    else None
                ),
                require_approval=bool(task_dict.get("require_approval", False)),
                require_review_approval=bool(
                    task_dict.get("require_review_approval", False)
                ),
            )
        )
    return tasks
