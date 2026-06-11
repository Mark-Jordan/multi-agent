from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from madcli.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_create_session_persists_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))

            session = store.create_session(
                title="Build strategy",
                workspace=Path("D:/repo"),
                active_agent="strategy_engineer",
            )

            loaded = store.load_session(session.session_id)
            self.assertEqual(loaded.title, "Build strategy")
            self.assertEqual(loaded.workspace, "D:/repo")
            self.assertEqual(loaded.active_agent, "strategy_engineer")
            self.assertEqual(loaded.messages, [])

    def test_append_message_persists_agent_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            session = store.create_session(
                title="Review",
                workspace=Path("."),
                active_agent="codex_reviewer",
            )

            message = store.append_message(
                session.session_id,
                role="agent",
                content="Review complete.",
                agent_name="codex_reviewer",
                runtime="codex",
                run_id="run-1",
                status="succeeded",
            )

            loaded = store.load_session(session.session_id)
            self.assertEqual(len(loaded.messages), 1)
            self.assertEqual(loaded.messages[0].message_id, message.message_id)
            self.assertEqual(loaded.messages[0].agent_name, "codex_reviewer")
            self.assertEqual(loaded.messages[0].runtime, "codex")
            self.assertEqual(loaded.messages[0].run_id, "run-1")
            self.assertEqual(loaded.messages[0].status, "succeeded")

    def test_list_sessions_returns_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            first = store.create_session(
                title="First",
                workspace=Path("."),
                active_agent="strategy_engineer",
            )
            second = store.create_session(
                title="Second",
                workspace=Path("."),
                active_agent="claude_engineer",
            )

            sessions = store.list_sessions()

            self.assertEqual([session.session_id for session in sessions], [second.session_id, first.session_id])


if __name__ == "__main__":
    unittest.main()
