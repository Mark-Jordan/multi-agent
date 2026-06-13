from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from madcli.agent_message import (
    TaskHandoff,
    build_handoff_from_result,
)


class AgentMessageTests(unittest.TestCase):
    def test_handoff_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handoffs_dir = Path(tmp) / "handoffs"
            handoff = TaskHandoff(
                source_task_id="build-feature",
                source_run_id="run-1",
                summary="Built the feature successfully.",
                key_files=["src/main.py", "tests/test_main.py"],
                findings="All tests pass.",
                warnings="Consider adding edge case tests.",
                suggestions="Add logging for the new feature.",
            )
            path = handoff.save(handoffs_dir)
            self.assertTrue(path.exists())

            loaded = TaskHandoff.load(path)
            self.assertEqual(loaded.source_task_id, "build-feature")
            self.assertEqual(loaded.summary, "Built the feature successfully.")
            self.assertEqual(loaded.key_files, ["src/main.py", "tests/test_main.py"])

    def test_load_all_returns_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handoffs_dir = Path(tmp) / "handoffs"
            TaskHandoff(
                source_task_id="task-a",
                source_run_id="r1",
                summary="A",
                key_files=[],
                findings="",
                warnings="",
                suggestions="",
            ).save(handoffs_dir)
            TaskHandoff(
                source_task_id="task-b",
                source_run_id="r2",
                summary="B",
                key_files=[],
                findings="",
                warnings="",
                suggestions="",
            ).save(handoffs_dir)

            all_handoffs = TaskHandoff.load_all(handoffs_dir)
            self.assertEqual(len(all_handoffs), 2)

    def test_load_all_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handoffs_dir = Path(tmp) / "nonexistent"
            all_handoffs = TaskHandoff.load_all(handoffs_dir)
            self.assertEqual(all_handoffs, [])

    def test_build_handoff_from_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "result.md"
            result_path.write_text("# Result\n\nTask completed successfully.", encoding="utf-8")
            handoff = build_handoff_from_result(
                task_id="test-task",
                run_id="run-1",
                worker_stdout="Build output here",
                worker_stderr="",
                result_path=result_path,
            )
            self.assertEqual(handoff.source_task_id, "test-task")
            self.assertEqual(handoff.source_run_id, "run-1")
            self.assertIn("Task completed", handoff.summary)

    def test_to_message_creates_valid_agent_message(self) -> None:
        handoff = TaskHandoff(
            source_task_id="task-1",
            source_run_id="run-1",
            summary="Done",
            key_files=["f.py"],
            findings="Good",
            warnings="None",
            suggestions="Improve",
        )
        msg = handoff.to_message()
        self.assertEqual(msg.from_task_id, "task-1")
        self.assertEqual(msg.message_type, "handoff")
        self.assertIn("Done", msg.content)


if __name__ == "__main__":
    unittest.main()
