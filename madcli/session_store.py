from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class MessageRecord:
    message_id: str
    role: str
    content: str
    created_at: str
    agent_name: str | None = None
    runtime: str | None = None
    run_id: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    title: str
    workspace: str
    active_agent: str
    created_at: str
    updated_at: str
    messages: list[MessageRecord]


class SessionStore:
    def __init__(self, app_dir: Path) -> None:
        self.sessions_dir = app_dir / "sessions"
        self._last_timestamp: datetime | None = None

    def create_session(
        self,
        *,
        title: str,
        workspace: Path,
        active_agent: str,
    ) -> SessionRecord:
        now = self._utc_now()
        session = SessionRecord(
            session_id=f"session-{uuid4().hex[:12]}",
            title=title,
            workspace=workspace.as_posix(),
            active_agent=active_agent,
            created_at=now,
            updated_at=now,
            messages=[],
        )
        self.save_session(session)
        return session

    def append_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        agent_name: str | None = None,
        runtime: str | None = None,
        run_id: str | None = None,
        status: str | None = None,
    ) -> MessageRecord:
        session = self.load_session(session_id)
        message = MessageRecord(
            message_id=f"message-{uuid4().hex[:12]}",
            role=role,
            content=content,
            created_at=self._utc_now(),
            agent_name=agent_name,
            runtime=runtime,
            run_id=run_id,
            status=status,
        )
        updated = SessionRecord(
            session_id=session.session_id,
            title=session.title,
            workspace=session.workspace,
            active_agent=session.active_agent,
            created_at=session.created_at,
            updated_at=message.created_at,
            messages=[*session.messages, message],
        )
        self.save_session(updated)
        return message

    def save_session(self, session: SessionRecord) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        path = self._session_path(session.session_id)
        path.write_text(
            json.dumps(_session_to_dict(session), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def load_session(self, session_id: str) -> SessionRecord:
        data = json.loads(self._session_path(session_id).read_text(encoding="utf-8"))
        return _session_from_dict(data)

    def list_sessions(self) -> list[SessionRecord]:
        if not self.sessions_dir.exists():
            return []
        sessions = [
            _session_from_dict(json.loads(path.read_text(encoding="utf-8")))
            for path in self.sessions_dir.glob("*.json")
        ]
        return sorted(sessions, key=lambda session: session.updated_at, reverse=True)

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def _utc_now(self) -> str:
        now = datetime.now(timezone.utc)
        if self._last_timestamp is not None and now <= self._last_timestamp:
            now = self._last_timestamp + timedelta(microseconds=1)
        self._last_timestamp = now
        return now.isoformat()


def _session_to_dict(session: SessionRecord) -> dict[str, object]:
    return asdict(session)


def _session_from_dict(data: dict[str, object]) -> SessionRecord:
    messages = [
        MessageRecord(**message)
        for message in data.get("messages", [])
        if isinstance(message, dict)
    ]
    return SessionRecord(
        session_id=str(data["session_id"]),
        title=str(data["title"]),
        workspace=str(data["workspace"]),
        active_agent=str(data["active_agent"]),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
        messages=messages,
    )
