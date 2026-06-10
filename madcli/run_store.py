from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass
class RunMetadata:
    run_id: str
    task: str
    agent: str
    runtime: str
    status: str
    created_at: str
    workdir: str


class RunStore:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def create_run(
        self,
        *,
        run_id: str,
        task: str,
        agent: str,
        runtime: str,
        workdir: Path,
    ) -> RunMetadata:
        run_dir = self.run_dir(run_id)
        (run_dir / "context").mkdir(parents=True, exist_ok=True)
        (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
        metadata = RunMetadata(
            run_id=run_id,
            task=task,
            agent=agent,
            runtime=runtime,
            status="created",
            created_at=datetime.now(timezone.utc).isoformat(),
            workdir=str(workdir),
        )
        self.save_metadata(metadata)
        self.append_event(run_id, "run_created", asdict(metadata))
        return metadata

    def save_metadata(self, metadata: RunMetadata) -> None:
        path = self.run_dir(metadata.run_id) / "metadata.json"
        path.write_text(
            json.dumps(asdict(metadata), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def load_metadata(self, run_id: str) -> RunMetadata:
        path = self.run_dir(run_id) / "metadata.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return RunMetadata(**data)

    def update_status(self, run_id: str, status: str) -> RunMetadata:
        metadata = self.load_metadata(run_id)
        metadata.status = status
        self.save_metadata(metadata)
        self.append_event(run_id, "status_changed", {"status": status})
        return metadata

    def append_event(self, run_id: str, event: str, payload: dict[str, Any]) -> None:
        path = self.run_dir(run_id) / "events.jsonl"
        record = {
            "time": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def list_runs(self) -> list[RunMetadata]:
        if not self.runs_dir.exists():
            return []
        runs: list[RunMetadata] = []
        for path in sorted(self.runs_dir.iterdir(), reverse=True):
            metadata_path = path / "metadata.json"
            if metadata_path.exists():
                data = json.loads(metadata_path.read_text(encoding="utf-8"))
                runs.append(RunMetadata(**data))
        return runs

    def read_events(self, run_id: str) -> list[str]:
        path = self.run_dir(run_id) / "events.jsonl"
        if not path.exists():
            return []
        return path.read_text(encoding="utf-8").splitlines()
