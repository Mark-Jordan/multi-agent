from __future__ import annotations

import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from madcli.config import CredentialProfile, RuntimeConfig, default_config
from madcli.executors import ExecutorRequest, executor_for, run_process_streaming


class ExecutorTests(unittest.TestCase):
    def request_for(self, agent_name: str) -> ExecutorRequest:
        config = default_config()
        agent = config.agents[agent_name]
        runtime = config.runtimes[agent.runtime]
        return ExecutorRequest(
            runtime=runtime,
            agent=agent,
            task="Implement task",
            workdir=Path("."),
            context_files=[Path("context/engineering_task.md")],
            dry_run=True,
        )

    def test_opencode_command_builder(self) -> None:
        request = self.request_for("strategy_engineer")
        command = executor_for("opencode").build_command(request)
        self.assertEqual(command[0:2], ["opencode", "run"])
        self.assertIn("--agent", command)
        self.assertIn("--file", command)

    def test_codex_command_builder(self) -> None:
        request = self.request_for("codex_reviewer")
        command = executor_for("codex").build_command(request)
        self.assertEqual(command[0:3], ["codex", "exec", "--cd"])
        self.assertIn("--model", command)

    def test_codex_task_prompt_mode_sends_plain_user_text(self) -> None:
        config = default_config()
        agent = config.agents["codex_reviewer"]
        runtime = RuntimeConfig("codex", "codex", [])
        request = ExecutorRequest(
            runtime=runtime,
            agent=agent,
            task="hi",
            workdir=Path("."),
            context_files=[Path("context/engineering_task.md")],
            dry_run=True,
            prompt_mode="task",
            last_message_path=Path("outputs/last_message.txt"),
        )

        command = executor_for("codex").build_command(request)

        self.assertEqual(command[-1], "hi")
        self.assertNotIn("Read the listed context files", command[-1])
        self.assertIn("--output-last-message", command)
        self.assertIn(str(Path("outputs/last_message.txt")), command)

    def test_claude_code_command_builder(self) -> None:
        request = self.request_for("claude_engineer")
        command = executor_for("claude_code").build_command(request)
        self.assertEqual(command[0:4], ["claude", "-p", "--agent", "strategy-engineer"])
        self.assertIn("--model", command)
        self.assertIn("sonnet", command)

    def test_dry_run_does_not_require_binary(self) -> None:
        request = self.request_for("strategy_engineer")
        result = executor_for("opencode").run(request)
        self.assertTrue(result.ok)
        self.assertIsNone(result.returncode)

    def test_codex_credential_adds_dynamic_provider_config(self) -> None:
        config = default_config()
        agent = config.agents["codex_reviewer"]
        runtime = RuntimeConfig(
            "codex",
            "codex",
            [
                CredentialProfile(
                    "primary",
                    base_url="https://codex-one.example/v1",
                    api_key_env="CODEX_KEY_PRIMARY",
                )
            ],
        )
        request = ExecutorRequest(
            runtime=runtime,
            agent=agent,
            task="Review task",
            workdir=Path("."),
            context_files=[Path("context/engineering_task.md")],
            dry_run=True,
        )
        result = executor_for("codex").run(request)
        command = result.command
        self.assertEqual(result.credential_name, "primary")
        self.assertIn('model_provider="madcli_primary"', command)
        self.assertIn(
            'model_providers.madcli_primary.base_url="https://codex-one.example/v1"',
            command,
        )
        self.assertIn(
            'model_providers.madcli_primary.env_key="OPENAI_API_KEY"',
            command,
        )

    def test_claude_credential_env_maps_to_anthropic_variables(self) -> None:
        config = default_config()
        agent = config.agents["claude_engineer"]
        runtime = RuntimeConfig(
            "claude_code",
            "claude",
            [
                CredentialProfile(
                    "primary",
                    base_url="https://claude.example",
                    api_key="secret-value",
                )
            ],
        )
        request = ExecutorRequest(
            runtime=runtime,
            agent=agent,
            task="Implement task",
            workdir=Path("."),
            context_files=[Path("context/engineering_task.md")],
            dry_run=True,
        )
        env = executor_for("claude_code").build_env(
            request, runtime.credentials[0]
        )
        self.assertEqual(env["ANTHROPIC_API_KEY"], "secret-value")
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://claude.example")

    def test_missing_named_credential_raises_clear_error(self) -> None:
        config = default_config()
        agent = config.agents["codex_reviewer"]
        runtime = RuntimeConfig(
            "codex",
            "codex",
            [CredentialProfile("primary", api_key="secret")],
        )
        request = ExecutorRequest(
            runtime=runtime,
            agent=agent,
            task="Review task",
            workdir=Path("."),
            context_files=[Path("context/engineering_task.md")],
            dry_run=True,
            credential_name="backup",
        )
        with self.assertRaisesRegex(ValueError, "no credential named 'backup'"):
            executor_for("codex").run(request)

    def test_run_uses_resolved_runtime_command_path(self) -> None:
        config = default_config()
        agent = config.agents["codex_reviewer"]
        runtime = RuntimeConfig("codex", "codex", [])
        request = ExecutorRequest(
            runtime=runtime,
            agent=agent,
            task="Review task",
            workdir=Path("."),
            context_files=[Path("context/engineering_task.md")],
            dry_run=False,
        )
        captured_command: list[str] = []
        captured_kwargs: dict[str, object] = {}

        def fake_run(command: list[str], **_kwargs: object):
            nonlocal captured_command
            nonlocal captured_kwargs
            captured_command = command
            captured_kwargs = _kwargs
            return type(
                "Completed",
                (),
                {"returncode": 0, "stdout": "ok", "stderr": ""},
            )()

        with patch("madcli.executors.shutil.which", return_value=r"C:\Tools\codex.cmd"):
            with patch("madcli.executors.subprocess.run", side_effect=fake_run):
                result = executor_for("codex").run(request)

        self.assertTrue(result.ok)
        self.assertEqual(captured_command[0], r"C:\Tools\codex.cmd")
        self.assertEqual(result.command[0], r"C:\Tools\codex.cmd")
        self.assertIs(captured_kwargs["stdin"], subprocess.DEVNULL)

    def test_run_reports_missing_runtime_when_process_launch_fails(self) -> None:
        config = default_config()
        agent = config.agents["codex_reviewer"]
        runtime = RuntimeConfig("codex", "codex", [])
        request = ExecutorRequest(
            runtime=runtime,
            agent=agent,
            task="Review task",
            workdir=Path("."),
            context_files=[Path("context/engineering_task.md")],
            dry_run=False,
        )

        with patch("madcli.executors.shutil.which", return_value=r"C:\Tools\codex.cmd"):
            with patch(
                "madcli.executors.subprocess.run",
                side_effect=FileNotFoundError("missing executable"),
            ):
                result = executor_for("codex").run(request)

        self.assertFalse(result.ok)
        self.assertIn("runtime command could not be started", result.stderr)
        self.assertEqual(result.command[0], r"C:\Tools\codex.cmd")

    def test_streaming_output_decodes_utf8_without_thread_crash(self) -> None:
        command = [
            sys.executable,
            "-c",
            (
                "import sys; "
                "sys.stdout.buffer.write('标准输出\\n'.encode('utf-8')); "
                "sys.stdout.flush(); "
                "sys.stderr.buffer.write('错误输出\\n'.encode('utf-8')); "
                "sys.stderr.flush()"
            ),
        ]

        with patch("madcli.executors.sys.stdout", new=io.StringIO()):
            with patch("madcli.executors.sys.stderr", new=io.StringIO()):
                result = run_process_streaming(
                    command,
                    cwd=Path("."),
                    env=os.environ.copy(),
                    timeout_seconds=10,
                )

        self.assertEqual(result.returncode, 0)
        self.assertIn("标准输出", result.stdout)
        self.assertIn("错误输出", result.stderr)


if __name__ == "__main__":
    unittest.main()
