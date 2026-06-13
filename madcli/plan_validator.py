from __future__ import annotations

from .config import AppConfig
from .workflow_store import PlannedTask


def validate_plan(tasks: list[PlannedTask], config: AppConfig) -> list[str]:
    errors: list[str] = []
    if not tasks:
        return ["plan must contain at least one task"]

    task_ids = {t.task_id for t in tasks}
    if len(task_ids) != len(tasks):
        seen: set[str] = set()
        for t in tasks:
            if t.task_id in seen:
                errors.append(f"task '{t.task_id}': duplicate task_id")
            seen.add(t.task_id)
    agent_names = set(config.agents.keys())

    for task in tasks:
        if task.agent not in agent_names:
            errors.append(
                f"task '{task.task_id}': unknown agent '{task.agent}' "
                f"(available: {', '.join(sorted(agent_names))})"
            )
        if task.depends_on:
            for dep_id in task.depends_on:
                if dep_id not in task_ids:
                    errors.append(
                        f"task '{task.task_id}': depends on unknown task '{dep_id}'"
                    )
                if dep_id == task.task_id:
                    errors.append(
                        f"task '{task.task_id}': cannot depend on itself"
                    )
        if task.review_by and task.review_by not in agent_names:
            errors.append(
                f"task '{task.task_id}': unknown reviewer '{task.review_by}'"
            )
        if task.review_by == task.agent:
            errors.append(
                f"task '{task.task_id}': reviewer must not be the same agent as the worker"
            )

    if not errors:
        cycle_errors = _detect_cycles(tasks)
        errors.extend(cycle_errors)

    if not errors:
        reach_errors = _check_reachability(tasks)
        errors.extend(reach_errors)

    return errors


def _detect_cycles(tasks: list[PlannedTask]) -> list[str]:
    adjacency: dict[str, list[str]] = {t.task_id: [] for t in tasks}
    for t in tasks:
        if t.depends_on:
            for dep in t.depends_on:
                if dep in adjacency:
                    adjacency[dep].append(t.task_id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {t.task_id: WHITE for t in tasks}
    parent: dict[str, str | None] = {t.task_id: None for t in tasks}

    def dfs(node: str) -> list[str]:
        color[node] = GRAY
        for neighbor in adjacency[node]:
            if color[neighbor] == GRAY:
                cycle = [neighbor, node]
                current = node
                while parent.get(current) and parent[current] != neighbor:
                    current = parent[current]
                    if current:
                        cycle.append(current)
                cycle.append(neighbor)
                cycle.reverse()
                return [
                    "circular dependency detected: "
                    + " -> ".join(cycle)
                ]
            if color[neighbor] == WHITE:
                parent[neighbor] = node
                result = dfs(neighbor)
                if result:
                    return result
        color[node] = BLACK
        return []

    for task_id in adjacency:
        if color[task_id] == WHITE:
            result = dfs(task_id)
            if result:
                return result
    return []


def _check_reachability(tasks: list[PlannedTask]) -> list[str]:
    task_ids = {t.task_id for t in tasks}
    depended_by: dict[str, list[str]] = {tid: [] for tid in task_ids}
    nodes_with_deps: set[str] = set()
    for t in tasks:
        deps = t.depends_on or []
        if deps:
            nodes_with_deps.add(t.task_id)
        for dep in deps:
            if dep in depended_by:
                depended_by[dep].append(t.task_id)

    roots = task_ids - nodes_with_deps
    if not roots and task_ids:
        return ["plan has no tasks without dependencies; all tasks are interdependent"]

    reachable: set[str] = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        if node in reachable:
            continue
        reachable.add(node)
        stack.extend(depended_by.get(node, []))

    orphaned = task_ids - reachable
    if orphaned:
        return [
            f"unreachable tasks (not connected to any root): {', '.join(sorted(orphaned))}"
        ]
    return []
