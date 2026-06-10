from __future__ import annotations

import unittest
from pathlib import Path

from madcli.config import CredentialProfile, RuntimeConfig, default_config
from madcli.executors import ExecutorRequest, executor_for


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

    def test_claude_code_command_builder(self) -> None:
        request = self.request_for("claude_engineer")
        command = executor_for("claude_code").build_command(request)
        self.assertEqual(command[0:2], ["claude", "-p"])
        self.assertIn("--output-format", command)

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


if __name__ == "__main__":
    unittest.main()
