from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from madcli.config import default_config
from madcli.context import make_run_id, write_context_package
from madcli.run_store import RunStore


class ContextTests(unittest.TestCase):
    def test_make_run_id_contains_slug(self) -> None:
        run_id = make_run_id("Mean reversion strategy")
        self.assertIn("mean-reversion-strategy", run_id)

    def test_write_context_package_creates_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = default_config().agents["strategy_engineer"]
            paths = write_context_package(
                context_dir=Path(tmp),
                task="Build a strategy",
                agent=agent,
                extra_context="Use daily bars.",
            )
            names = {path.name for path in paths}
            self.assertEqual(
                names,
                {
                    "user_goal.md",
                    "agent_context.md",
                    "engineering_task.md",
                    "extra_context.md",
                },
            )
            self.assertIn("Build a strategy", (Path(tmp) / "user_goal.md").read_text())

    def test_run_store_persists_metadata_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(Path(tmp))
            metadata = store.create_run(
                run_id="run-1",
                task="task",
                agent="strategy_engineer",
                runtime="opencode",
                workdir=Path("."),
            )
            self.assertEqual(metadata.status, "created")
            store.update_status("run-1", "dry_run")
            loaded = store.load_metadata("run-1")
            self.assertEqual(loaded.status, "dry_run")
            self.assertEqual(len(store.read_events("run-1")), 2)


if __name__ == "__main__":
    unittest.main()
