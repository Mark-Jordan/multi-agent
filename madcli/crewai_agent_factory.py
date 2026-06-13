from __future__ import annotations

from typing import Any

from .config import AppConfig, AgentConfig


ENGINEER_KEYWORDS = (
    "engineer", "implement", "build", "code", "develop",
    "strategy", "architect", "design", "create",
)
REVIEWER_KEYWORDS = (
    "reviewer", "review", "audit", "inspect", "verify",
    "qa", "quality",
)
PLANNER_KEYWORDS = (
    "planner", "orchestrat", "plan", "command", "manage",
    "coordinate", "dispatch", "lead", "direct",
)


def _score_keywords(text: str, keywords: tuple[str, ...]) -> int:
    """Score keyword matches with name matches weighted 2x."""
    return sum(1 for kw in keywords if kw in text)


def classify_agent_role(agent: AgentConfig) -> str:
    name_lower = agent.name.lower()
    desc_lower = agent.description.lower()

    planner_score = _score_keywords(
        f"{name_lower} {name_lower} {desc_lower}", PLANNER_KEYWORDS
    )
    reviewer_score = _score_keywords(
        f"{name_lower} {name_lower} {desc_lower}", REVIEWER_KEYWORDS
    )
    engineer_score = _score_keywords(
        desc_lower, ENGINEER_KEYWORDS
    )

    if planner_score > reviewer_score and planner_score > engineer_score:
        return "planner"
    if reviewer_score > engineer_score:
        return "reviewer"
    return "engineer"


def _build_worker_agent(
    agent_config: AgentConfig,
    role: str,
    tools: list[Any],
    crewai_module: Any,
) -> Any:
    role_descriptions = {
        "engineer": {
            "role": f"madcli engineer: {agent_config.name}",
            "goal": (
                f"Implement coding tasks using the {agent_config.runtime} runtime. "
                "Write, test, and deliver implementation work through the "
                "run_madcli_agent_task tool."
            ),
            "backstory": (
                f"{agent_config.description}\n"
                f"You use {agent_config.runtime} to execute concrete coding tasks. "
                "Dispatch work through run_madcli_agent_task and produce clear artifacts."
            ),
        },
        "reviewer": {
            "role": f"madcli reviewer: {agent_config.name}",
            "goal": (
                "Review implementation artifacts, verify correctness, detect "
                "regressions, and report findings using available tools."
            ),
            "backstory": (
                f"{agent_config.description}\n"
                f"You use {agent_config.runtime} to inspect code and artifacts. "
                "Read run artifacts, check diffs, and provide structured review feedback."
            ),
        },
        "planner": {
            "role": f"madcli planner: {agent_config.name}",
            "goal": (
                "Analyze goals, decompose into concrete tasks, assign to suitable "
                "agents, and track overall workflow progress."
            ),
            "backstory": (
                f"{agent_config.description}\n"
                f"You use {agent_config.runtime} to plan and coordinate. "
                "Break down complex goals into actionable tasks with clear dependencies."
            ),
        },
    }
    rd = role_descriptions[role]
    return crewai_module.Agent(
        role=rd["role"],
        goal=rd["goal"],
        backstory=rd["backstory"],
        tools=tools,
        allow_delegation=False,
    )


def build_multi_agent_crew(
    config: AppConfig,
    goal: str,
    manager_agent_name: str,
    tool_builders: dict[str, Any],
    crewai_module: Any,
) -> tuple[list[Any], Any, Any]:
    """Create independent CrewAI agents for each madcli agent + a manager.

    Returns (all_agents, manager_agent, delegation_task).
    """
    workers: list[Any] = []
    for name, agent_config in sorted(config.agents.items()):
        role = classify_agent_role(agent_config)
        tools = tool_builders.get(name, tool_builders.get("default", []))
        if callable(tools):
            tools = tools()
        worker = _build_worker_agent(agent_config, role, list(tools or []), crewai_module)
        workers.append(worker)

    manager = crewai_module.Agent(
        role="madcli workflow commander",
        goal=(
            "Plan, delegate, review, and conclude the workflow. Use available "
            "workers and tools instead of doing repository work directly. Monitor "
            "progress and adapt the plan when needed."
        ),
        backstory=(
            "You coordinate a team of specialized madcli coding agents. "
            "Each worker has specific capabilities:\n"
            + "\n".join(
                f"- {agent_config.name} ({classify_agent_role(agent_config)}): "
                f"{agent_config.description[:120]}"
                for agent_config in sorted(config.agents.values(), key=lambda a: a.name)
            )
            + "\n\nDelegate concrete work to the right worker. Check progress "
            "before making decisions. Read artifacts when you need to verify results."
        ),
        tools=tool_builders.get("manager", []),
        allow_delegation=True,
    )

    delegation_task = crewai_module.Task(
        description=(
            "Complete this user goal as an autonomous multi-agent workflow. "
            "First decide which workers should handle each part. Then delegate "
            "tasks, monitor progress, trigger review when useful, and summarize "
            "the final result.\n\n"
            f"Goal:\n{goal}"
        ),
        expected_output=(
            "A concise workflow report listing delegated tasks, review findings, "
            "final status, risks, and follow-up work."
        ),
        agent=manager,
    )

    return workers, manager, delegation_task
