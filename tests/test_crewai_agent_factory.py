from __future__ import annotations

import unittest

from madcli.config import AgentConfig, default_config
from madcli.crewai_agent_factory import classify_agent_role


class CrewAIAgentFactoryTests(unittest.TestCase):
    def test_classify_engineer_by_name(self) -> None:
        agent = AgentConfig(
            name="strategy_engineer",
            runtime="opencode",
            agent="engineer",
            model="test",
            description="Implements strategy code.",
        )
        self.assertEqual(classify_agent_role(agent), "engineer")

    def test_classify_reviewer_by_name_and_description(self) -> None:
        agent = AgentConfig(
            name="codex_reviewer",
            runtime="codex",
            agent="reviewer",
            model="test",
            description="Reviews diffs and implementation reports.",
        )
        self.assertEqual(classify_agent_role(agent), "reviewer")

    def test_classify_planner_by_keywords(self) -> None:
        agent = AgentConfig(
            name="orchestrator_agent",
            runtime="claude_code",
            agent="planner",
            model="test",
            description="Plans and coordinates multi-agent workflows.",
        )
        self.assertEqual(classify_agent_role(agent), "planner")

    def test_classify_defaults_to_engineer_for_unknown(self) -> None:
        agent = AgentConfig(
            name="helper",
            runtime="opencode",
            agent="helper",
            model="test",
            description="Does various things.",
        )
        self.assertEqual(classify_agent_role(agent), "engineer")

    def test_classify_all_default_agents(self) -> None:
        config = default_config()
        roles = {
            name: classify_agent_role(agent)
            for name, agent in config.agents.items()
        }
        self.assertEqual(roles["strategy_engineer"], "engineer")
        self.assertEqual(roles["codex_reviewer"], "reviewer")
        self.assertEqual(roles["claude_engineer"], "engineer")


if __name__ == "__main__":
    unittest.main()
