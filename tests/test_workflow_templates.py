from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from madcli.workflow_templates import (
    BUILTIN_TEMPLATES_DIR,
    list_templates,
    load_template,
    render_template,
)


class WorkflowTemplatesTests(unittest.TestCase):
    def test_list_templates_returns_all_builtins(self) -> None:
        templates = list_templates()
        self.assertEqual(len(templates), 5)
        self.assertIn("implement-review", templates)
        self.assertIn("debug-fix-verify", templates)
        self.assertIn("multi-perspective-review", templates)

    def test_load_template_returns_valid_data(self) -> None:
        data = load_template("implement-review")
        self.assertIn("tasks", data)
        self.assertIsInstance(data["tasks"], list)
        self.assertEqual(len(data["tasks"]), 2)

    def test_load_template_not_found_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            load_template("nonexistent-template")
        self.assertIn("nonexistent-template", str(ctx.exception))
        self.assertIn("implement-review", str(ctx.exception))

    def test_load_template_from_custom_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            custom_dir = Path(tmp) / "custom_templates"
            custom_dir.mkdir()
            (custom_dir / "custom-one.json").write_text(
                '{"description": "custom", "tasks": [{"id": "t1", "agent": "a1", "task": "do work"}]}',
                encoding="utf-8",
            )
            data = load_template("custom-one", templates_dir=custom_dir)
            self.assertEqual(data["description"], "custom")
            self.assertEqual(len(data["tasks"]), 1)

    def test_render_template_basic(self) -> None:
        template_data = {
            "tasks": [
                {"id": "build", "agent": "engineer", "task": "Implement {{feature}}",
                 "retry_count": 1},
                {"id": "review", "agent": "reviewer", "task": "Review {{feature}}",
                 "depends_on": ["build"]},
            ]
        }
        tasks = render_template(template_data, {"feature": "user-auth"})
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].task_id, "build")
        self.assertEqual(tasks[0].agent, "engineer")
        self.assertEqual(tasks[0].task, "Implement user-auth")
        self.assertEqual(tasks[0].retry_count, 1)
        self.assertEqual(tasks[1].task_id, "review")
        self.assertEqual(tasks[1].depends_on, ["build"])

    def test_render_template_with_acceptance_criteria(self) -> None:
        template_data = {
            "tasks": [
                {
                    "id": "impl",
                    "agent": "a1",
                    "task": "Implement {{goal}}",
                    "acceptance_criteria": [
                        "Criterion: {{goal}} must work",
                        "Tests pass",
                    ],
                    "require_approval": True,
                }
            ]
        }
        tasks = render_template(template_data, {"goal": "login-page"})
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_id, "impl")
        self.assertTrue(tasks[0].require_approval)
        self.assertEqual(tasks[0].acceptance_criteria, [
            "Criterion: login-page must work",
            "Tests pass",
        ])

    def test_render_template_missing_id_raises(self) -> None:
        template_data = {
            "tasks": [
                {"agent": "a1", "task": "do work"}
            ]
        }
        with self.assertRaises(ValueError) as ctx:
            render_template(template_data, {})
        self.assertIn("must define id", str(ctx.exception))

    def test_render_template_missing_agent_raises(self) -> None:
        template_data = {
            "tasks": [
                {"id": "t1", "task": "do work"}
            ]
        }
        with self.assertRaises(ValueError) as ctx:
            render_template(template_data, {})
        self.assertIn("must define id, agent, and task", str(ctx.exception))

    def test_render_template_missing_task_raises(self) -> None:
        template_data = {
            "tasks": [
                {"id": "t1", "agent": "a1"}
            ]
        }
        with self.assertRaises(ValueError) as ctx:
            render_template(template_data, {})
        self.assertIn("must define id, agent, and task", str(ctx.exception))

    def test_render_template_with_review_by(self) -> None:
        template_data = {
            "tasks": [
                {"id": "t1", "agent": "a1", "task": "do work", "review_by": "reviewer"}
            ]
        }
        tasks = render_template(template_data, {})
        self.assertEqual(tasks[0].review_by, "reviewer")

    def test_render_template_with_fallback_and_allow_failure(self) -> None:
        template_data = {
            "tasks": [
                {
                    "id": "t1",
                    "agent": "a1",
                    "task": "risky work",
                    "retry_count": 3,
                    "retry_delay": 10,
                    "fallback_task_id": "fb1",
                    "allow_failure": True,
                }
            ]
        }
        tasks = render_template(template_data, {})
        self.assertEqual(tasks[0].retry_count, 3)
        self.assertEqual(tasks[0].retry_delay, 10)
        self.assertEqual(tasks[0].fallback_task_id, "fb1")
        self.assertTrue(tasks[0].allow_failure)

    def test_all_builtin_templates_are_valid_json(self) -> None:
        for name in list_templates():
            data = load_template(name)
            self.assertIn("tasks", data)
            self.assertIsInstance(data["tasks"], list)
            self.assertTrue(len(data["tasks"]) > 0)

    def test_all_builtin_templates_render(self) -> None:
        vars_ = {
            "goal": "test goal",
            "repo": "test-repo",
            "engineer_agent": "strategy_engineer",
            "reviewer_agent": "codex_reviewer",
            "planner_agent": "codex_reviewer",
            "research_agent": "claude_engineer",
        }
        for name in list_templates():
            data = load_template(name)
            tasks = render_template(data, vars_)
            self.assertGreater(len(tasks), 0, f"template {name} produced no tasks")

    def test_render_template_variable_not_replaced_unchanged(self) -> None:
        template_data = {
            "tasks": [
                {"id": "t1", "agent": "a1", "task": "Use {{unknown_var}} here"}
            ]
        }
        tasks = render_template(template_data, {})
        self.assertEqual(tasks[0].task, "Use {{unknown_var}} here")


if __name__ == "__main__":
    unittest.main()
