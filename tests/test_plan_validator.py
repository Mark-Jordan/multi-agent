from __future__ import annotations

import unittest

from madcli.config import default_config
from madcli.plan_validator import validate_plan
from madcli.workflow_store import PlannedTask


class PlanValidatorTests(unittest.TestCase):
    def test_valid_plan_passes_validation(self) -> None:
        config = default_config()
        tasks = [
            PlannedTask(
                task_id="build",
                agent="strategy_engineer",
                task="Build feature",
                depends_on=[],
                review_by="codex_reviewer",
            ),
            PlannedTask(
                task_id="review",
                agent="codex_reviewer",
                task="Review build",
                depends_on=["build"],
            ),
        ]
        errors = validate_plan(tasks, config)
        self.assertEqual(errors, [])

    def test_rejects_duplicate_task_id(self) -> None:
        config = default_config()
        tasks = [
            PlannedTask(task_id="same", agent="strategy_engineer", task="A"),
            PlannedTask(task_id="same", agent="strategy_engineer", task="B"),
        ]
        errors = validate_plan(tasks, config)
        self.assertTrue(any("duplicate task_id" in e for e in errors))

    def test_rejects_unknown_agent(self) -> None:
        config = default_config()
        tasks = [
            PlannedTask(task_id="t1", agent="nonexistent_agent", task="Do stuff"),
        ]
        errors = validate_plan(tasks, config)
        self.assertTrue(any("unknown agent" in e for e in errors))

    def test_rejects_unknown_dependency(self) -> None:
        config = default_config()
        tasks = [
            PlannedTask(
                task_id="t1",
                agent="strategy_engineer",
                task="Do stuff",
                depends_on=["nonexistent_task"],
            ),
        ]
        errors = validate_plan(tasks, config)
        self.assertTrue(any("depends on unknown task" in e for e in errors))

    def test_rejects_self_dependency(self) -> None:
        config = default_config()
        tasks = [
            PlannedTask(
                task_id="t1",
                agent="strategy_engineer",
                task="Do stuff",
                depends_on=["t1"],
            ),
        ]
        errors = validate_plan(tasks, config)
        self.assertTrue(any("cannot depend on itself" in e for e in errors))

    def test_rejects_unknown_reviewer(self) -> None:
        config = default_config()
        tasks = [
            PlannedTask(
                task_id="t1",
                agent="strategy_engineer",
                task="Do stuff",
                review_by="nonexistent_reviewer",
            ),
        ]
        errors = validate_plan(tasks, config)
        self.assertTrue(any("unknown reviewer" in e for e in errors))

    def test_rejects_self_reviewer(self) -> None:
        config = default_config()
        tasks = [
            PlannedTask(
                task_id="t1",
                agent="strategy_engineer",
                task="Do stuff",
                review_by="strategy_engineer",
            ),
        ]
        errors = validate_plan(tasks, config)
        self.assertTrue(any("reviewer must not be the same agent" in e for e in errors))

    def test_detects_circular_dependency(self) -> None:
        config = default_config()
        tasks = [
            PlannedTask(task_id="a", agent="strategy_engineer", task="A", depends_on=["c"]),
            PlannedTask(task_id="b", agent="codex_reviewer", task="B", depends_on=["a"]),
            PlannedTask(task_id="c", agent="claude_engineer", task="C", depends_on=["b"]),
        ]
        errors = validate_plan(tasks, config)
        self.assertTrue(any("circular dependency" in e for e in errors))

    def test_detects_unreachable_tasks(self) -> None:
        config = default_config()
        tasks = [
            PlannedTask(task_id="a", agent="strategy_engineer", task="A"),
            PlannedTask(task_id="b", agent="codex_reviewer", task="B", depends_on=["a"]),
            PlannedTask(task_id="orphan", agent="claude_engineer", task="Orphan", depends_on=["nonexistent"]),
        ]
        errors = validate_plan(tasks, config)
        self.assertTrue(any("depends on unknown task" in e for e in errors))

    def test_rejects_empty_plan(self) -> None:
        config = default_config()
        errors = validate_plan([], config)
        self.assertTrue(any("at least one task" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
