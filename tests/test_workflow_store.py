from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from madcli.workflow_store import PlannedTask, WorkflowStore


class WorkflowStoreTests(unittest.TestCase):
    def test_create_workflow_persists_metadata_tasks_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = WorkflowStore(root / "workflows")
            tasks = [
                PlannedTask(
                    task_id="implement-feature",
                    agent="strategy_engineer",
                    task="Implement the feature",
                    review_by="codex_reviewer",
                )
            ]

            workflow = store.create_workflow(
                workflow_id="workflow-1",
                goal="Build autonomous orchestration",
                tasks=tasks,
            )

            self.assertEqual(workflow.workflow_id, "workflow-1")
            self.assertEqual(workflow.status, "created")
            self.assertEqual(store.load_workflow("workflow-1").goal, workflow.goal)
            self.assertTrue(
                (root / "workflows" / "workflow-1" / "tasks" / "implement-feature.json").exists()
            )
            events = store.read_events("workflow-1")
            self.assertEqual(len(events), 1)
            self.assertIn("workflow_created", events[0])

    def test_update_task_records_run_ids_status_and_review_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowStore(Path(tmp) / "workflows")
            store.create_workflow(
                workflow_id="workflow-1",
                goal="Build autonomous orchestration",
                tasks=[
                    PlannedTask(
                        task_id="implement-feature",
                        agent="strategy_engineer",
                        task="Implement the feature",
                        review_by="codex_reviewer",
                    )
                ],
            )

            updated = store.update_task(
                "workflow-1",
                "implement-feature",
                status="reviewed",
                run_id="worker-run",
                review_run_id="review-run",
            )

            self.assertEqual(updated.status, "reviewed")
            self.assertEqual(updated.run_id, "worker-run")
            self.assertEqual(updated.review_run_id, "review-run")
            loaded = store.load_task("workflow-1", "implement-feature")
            self.assertEqual(loaded.review_run_id, "review-run")
            self.assertTrue(
                any("task_updated" in event for event in store.read_events("workflow-1"))
            )


if __name__ == "__main__":
    unittest.main()
