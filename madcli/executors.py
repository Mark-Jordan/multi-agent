from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading

from .config import AgentConfig, CredentialProfile, RuntimeConfig


@dataclass(frozen=True)
class ExecutorRequest:
    runtime: RuntimeConfig
    agent: AgentConfig
    task: str
    workdir: Path
    context_files: list[Path]
    dry_run: bool = False
    timeout_seconds: int = 3600
    credential_name: str | None = None
    stream_output: bool = False
    last_message_path: Path | None = None
    prompt_mode: str = "context"


@dataclass(frozen=True)
class ExecutorResult:
    ok: bool
    command: list[str]
    stdout: str
    stderr: str
    returncode: int | None
    credential_name: str | None = None
    attempts: list[dict[str, object]] | None = None


class CodingExecutor:
    runtime_name = ""

    def build_command(
        self, request: ExecutorRequest, credential: CredentialProfile | None = None
    ) -> list[str]:
        raise NotImplementedError

    def build_env(
        self, request: ExecutorRequest, credential: CredentialProfile | None = None
    ) -> dict[str, str]:
        return os.environ.copy()

    def select_credentials(self, request: ExecutorRequest) -> list[CredentialProfile | None]:
        if not request.runtime.credentials:
            return [None]
        if request.credential_name:
            for profile in request.runtime.credentials:
                if profile.name == request.credential_name:
                    return [profile]
            raise ValueError(
                f"runtime '{request.runtime.name}' has no credential named '{request.credential_name}'"
            )
        return list(request.runtime.credentials)

    def should_try_next_credential(self, result: ExecutorResult) -> bool:
        text = f"{result.stdout}\n{result.stderr}".lower()
        retry_markers = [
            "401",
            "403",
            "429",
            "api key",
            "auth",
            "authentication",
            "unauthorized",
            "forbidden",
            "quota",
            "rate limit",
            "rate_limit",
            "insufficient_quota",
            "invalid_api_key",
            "permission_denied",
        ]
        return any(marker in text for marker in retry_markers)

    def run(self, request: ExecutorRequest) -> ExecutorResult:
        attempts: list[dict[str, object]] = []
        last_result: ExecutorResult | None = None
        for credential in self.select_credentials(request):
            command = self.build_command(request, credential)
            credential_name = credential.name if credential else None
            if request.dry_run:
                attempts.append(
                    {
                        "credential": credential_name,
                        "returncode": None,
                        "ok": True,
                        "dry_run": True,
                    }
                )
                return ExecutorResult(
                    True,
                    command,
                    "",
                    "",
                    None,
                    credential_name=credential_name,
                    attempts=attempts,
                )
            resolved_command = shutil.which(request.runtime.command)
            if resolved_command is None:
                return ExecutorResult(
                    False,
                    command,
                    "",
                    f"runtime command not found: {request.runtime.command}",
                    None,
                    credential_name=credential_name,
                    attempts=attempts,
                )
            command = [resolved_command, *command[1:]]
            try:
                if request.stream_output:
                    completed = run_process_streaming(
                        command,
                        cwd=request.workdir,
                        env=self.build_env(request, credential),
                        timeout_seconds=request.timeout_seconds,
                    )
                else:
                    completed = subprocess.run(
                        command,
                        cwd=request.workdir,
                        env=self.build_env(request, credential),
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=request.timeout_seconds,
                        check=False,
                    )
            except FileNotFoundError as exc:
                return ExecutorResult(
                    False,
                    command,
                    "",
                    (
                        "runtime command could not be started: "
                        f"{request.runtime.command} ({exc})"
                    ),
                    None,
                    credential_name=credential_name,
                    attempts=attempts,
                )
            except OSError as exc:
                return ExecutorResult(
                    False,
                    command,
                    "",
                    (
                        "runtime command could not be started: "
                        f"{request.runtime.command} ({exc})"
                    ),
                    None,
                    credential_name=credential_name,
                    attempts=attempts,
                )
            result = ExecutorResult(
                completed.returncode == 0,
                command,
                completed.stdout,
                completed.stderr,
                completed.returncode,
                credential_name=credential_name,
            )
            attempts.append(
                {
                    "credential": credential_name,
                    "returncode": result.returncode,
                    "ok": result.ok,
                }
            )
            last_result = result
            if result.ok or not self.should_try_next_credential(result):
                break
        if last_result is None:
            raise RuntimeError("executor did not make an attempt")
        return ExecutorResult(
            last_result.ok,
            last_result.command,
            last_result.stdout,
            last_result.stderr,
            last_result.returncode,
            credential_name=last_result.credential_name,
            attempts=attempts,
        )


def run_process_streaming(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    def read_stream(pipe, sink, writer) -> None:
        try:
            for chunk in iter(pipe.readline, ""):
                sink.append(chunk)
                writer.write(chunk)
                writer.flush()
        finally:
            pipe.close()

    stdout_thread = threading.Thread(
        target=read_stream,
        args=(process.stdout, stdout_parts, sys.stdout),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=read_stream,
        args=(process.stderr, stderr_parts, sys.stderr),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        returncode = process.wait()
        stderr_parts.append(f"\nprocess timed out after {timeout_seconds} seconds\n")
        sys.stderr.write(stderr_parts[-1])
        sys.stderr.flush()
    stdout_thread.join(timeout=1)
    stderr_thread.join(timeout=1)
    return subprocess.CompletedProcess(
        command,
        returncode,
        stdout="".join(stdout_parts),
        stderr="".join(stderr_parts),
    )


def _context_prompt(task: str, context_files: list[Path]) -> str:
    files = "\n".join(f"- {path}" for path in context_files)
    return (
        "Read the listed context files first, then inspect the repository and complete "
        "the task.\n\n"
        f"Context files:\n{files}\n\n"
        f"Task:\n{task}"
    )


def _runtime_prompt(task: str, context_files: list[Path], prompt_mode: str) -> str:
    if prompt_mode == "task":
        return task
    return _context_prompt(task, context_files)


class OpenCodeExecutor(CodingExecutor):
    runtime_name = "opencode"

    def build_command(
        self, request: ExecutorRequest, credential: CredentialProfile | None = None
    ) -> list[str]:
        command = [
            request.runtime.command,
            "run",
            "--agent",
            request.agent.agent,
            "--dir",
            str(request.workdir),
            "--format",
            "json",
        ]
        if request.agent.model:
            command.extend(["--model", request.agent.model])
        for path in request.context_files:
            command.extend(["--file", str(path)])
        command.append(
            _runtime_prompt(request.task, request.context_files, request.prompt_mode)
        )
        return command


class CodexExecutor(CodingExecutor):
    runtime_name = "codex"

    def build_command(
        self, request: ExecutorRequest, credential: CredentialProfile | None = None
    ) -> list[str]:
        command = [
            request.runtime.command,
            "exec",
            "--cd",
            str(request.workdir),
        ]
        if credential:
            provider_id = f"madcli_{credential.name}"
            command.extend(["-c", f'model_provider="{provider_id}"'])
            command.extend(
                [
                    "-c",
                    f'model_providers.{provider_id}.name="madcli {credential.name}"',
                ]
            )
            if credential.base_url:
                command.extend(
                    [
                        "-c",
                        f'model_providers.{provider_id}.base_url="{credential.base_url}"',
                    ]
                )
            command.extend(
                [
                    "-c",
                    f'model_providers.{provider_id}.env_key="OPENAI_API_KEY"',
                ]
            )
            command.extend(
                ["-c", f'model_providers.{provider_id}.wire_api="responses"']
            )
        if request.agent.model:
            command.extend(["--model", request.agent.model])
        if request.last_message_path:
            command.extend(["--output-last-message", str(request.last_message_path)])
        command.append(
            _runtime_prompt(request.task, request.context_files, request.prompt_mode)
        )
        return command

    def build_env(
        self, request: ExecutorRequest, credential: CredentialProfile | None = None
    ) -> dict[str, str]:
        env = os.environ.copy()
        if credential:
            api_key = credential.api_key
            if credential.api_key_env:
                api_key = os.environ.get(credential.api_key_env)
            if api_key:
                env["OPENAI_API_KEY"] = api_key
            if credential.base_url:
                env["OPENAI_BASE_URL"] = credential.base_url
        return env


class ClaudeCodeExecutor(CodingExecutor):
    runtime_name = "claude_code"

    def build_command(
        self, request: ExecutorRequest, credential: CredentialProfile | None = None
    ) -> list[str]:
        command = [
            request.runtime.command,
            "-p",
            "--agent",
            request.agent.agent,
        ]
        if request.agent.model:
            command.extend(["--model", request.agent.model])
        command.append(
            _runtime_prompt(request.task, request.context_files, request.prompt_mode)
        )
        return command

    def build_env(
        self, request: ExecutorRequest, credential: CredentialProfile | None = None
    ) -> dict[str, str]:
        env = os.environ.copy()
        if credential:
            api_key = credential.api_key
            if credential.api_key_env:
                api_key = os.environ.get(credential.api_key_env)
            if api_key:
                env["ANTHROPIC_API_KEY"] = api_key
            if credential.base_url:
                env["ANTHROPIC_BASE_URL"] = credential.base_url
        return env


def executor_for(runtime_name: str) -> CodingExecutor:
    executors: dict[str, CodingExecutor] = {
        "opencode": OpenCodeExecutor(),
        "codex": CodexExecutor(),
        "claude_code": ClaudeCodeExecutor(),
    }
    try:
        return executors[runtime_name]
    except KeyError as exc:
        raise ValueError(f"unsupported runtime: {runtime_name}") from exc
