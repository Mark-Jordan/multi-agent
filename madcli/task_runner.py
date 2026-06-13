from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path

from .config import AppConfig
from .context import make_run_id, write_context_package
from .executors import ExecutorRequest, executor_for
from .run_store import RunStore


@dataclass(frozen=True)
class AgentTaskRequest:
    config: AppConfig
    task: str
    agent_name: str
    workdir: Path | None = None
    extra_context: str | None = None
    context_files: list[Path] | None = None
    dry_run: bool = False
    credential_name: str | None = None
    prompt_mode: str = "context"
    stream_output: bool = True

    @property
    def runs_dir(self) -> Path:
        return self.config.runs_dir


@dataclass(frozen=True)
class AgentTaskResult:
    run_id: str
    run_dir: Path
    status: str
    ok: bool
    runtime: str
    agent_name: str
    stdout: str
    stderr: str
    command: list[str] | None = None
    returncode: int | None = None
    credential_name: str | None = None


def run_agent_task(request: AgentTaskRequest) -> AgentTaskResult:
    config = request.config
    if request.agent_name not in config.agents:
        raise ValueError(f"unknown agent: {request.agent_name}")
    extra_context_files = [Path(path) for path in request.context_files or []]
    for path in extra_context_files:
        if not path.is_file():
            raise ValueError(f"context file not found: {path}")

    agent = config.agents[request.agent_name]
    effective_agent = (
        replace(agent, model=agent.active_model) if agent.active_model else agent
    )
    credential_name = request.credential_name or agent.active_credential
    runtime = config.runtimes[agent.runtime]
    workdir = (request.workdir or config.default_workdir).resolve()
    run_id = make_run_id(request.task)
    store = RunStore(config.runs_dir)
    metadata = store.create_run(
        run_id=run_id,
        task=request.task,
        agent=agent.name,
        runtime=agent.runtime,
        workdir=workdir,
    )
    context_files = write_context_package(
        context_dir=store.run_dir(run_id) / "context",
        task=request.task,
        agent=effective_agent,
        extra_context=request.extra_context,
        extra_context_files=extra_context_files,
    )
    store.append_event(
        run_id,
        "context_written",
        {"files": [str(path) for path in context_files]},
    )

    executor = executor_for(agent.runtime)
    outputs_dir = store.run_dir(run_id) / "outputs"
    last_message_path = outputs_dir / "last_message.txt"
    executor_request = ExecutorRequest(
        runtime=runtime,
        agent=effective_agent,
        task=request.task,
        workdir=workdir,
        context_files=[path.resolve() for path in context_files],
        dry_run=request.dry_run,
        credential_name=credential_name,
        stream_output=request.stream_output and not request.dry_run,
        last_message_path=last_message_path,
        prompt_mode=request.prompt_mode,
    )
    result = executor.run(executor_request)
    (outputs_dir / "command.json").write_text(
        json.dumps(result.command, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (outputs_dir / "attempts.json").write_text(
        json.dumps(result.attempts or [], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (outputs_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (outputs_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    store.append_event(
        run_id,
        "executor_finished",
        {
            "ok": result.ok,
            "dry_run": request.dry_run,
            "returncode": result.returncode,
            "command": result.command,
            "credential": result.credential_name,
            "attempts": result.attempts or [],
        },
    )
    final_status = "dry_run" if request.dry_run else "succeeded" if result.ok else "failed"
    store.update_status(run_id, final_status)
    _write_result_summary(
        outputs_dir=outputs_dir,
        run_id=metadata.run_id,
        status=final_status,
        agent_name=agent.name,
        runtime=agent.runtime,
        task=request.task,
        stdout=result.stdout,
        stderr=result.stderr,
        last_message_path=last_message_path,
    )
    return AgentTaskResult(
        run_id=metadata.run_id,
        run_dir=store.run_dir(run_id),
        status=final_status,
        ok=result.ok,
        runtime=agent.runtime,
        agent_name=agent.name,
        stdout=result.stdout,
        stderr=result.stderr,
        command=result.command,
        returncode=result.returncode,
        credential_name=result.credential_name,
    )


def _write_result_summary(
    *,
    outputs_dir: Path,
    run_id: str,
    status: str,
    agent_name: str,
    runtime: str,
    task: str,
    stdout: str,
    stderr: str,
    last_message_path: Path,
) -> None:
    last_message = ""
    if last_message_path.exists():
        last_message = last_message_path.read_text(encoding="utf-8").strip()
    content = [
        "# Run Result",
        "",
        f"- Run ID: `{run_id}`",
        f"- Status: `{status}`",
        f"- Agent: `{agent_name}`",
        f"- Runtime: `{runtime}`",
        "",
        "## Task",
        "",
        task.strip(),
        "",
        "## Final Message",
        "",
        last_message or stdout.strip() or stderr.strip() or "No runtime message captured.",
        "",
    ]
    (outputs_dir / "result.md").write_text("\n".join(content), encoding="utf-8")
