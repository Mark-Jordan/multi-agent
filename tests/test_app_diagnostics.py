from __future__ import annotations

import unittest

from madcli.app_diagnostics import build_startup_diagnostics
from madcli.config import (
    AgentConfig,
    AppConfig,
    CredentialProfile,
    RuntimeConfig,
)


class AppDiagnosticsTests(unittest.TestCase):
    def config_with_credentials(self, credentials: list[CredentialProfile]) -> AppConfig:
        return AppConfig(
            runs_dir=".madcli/runs",
            default_workdir=".",
            runtimes={
                "codex": RuntimeConfig(
                    name="codex",
                    command="codex",
                    credentials=credentials,
                ),
                "claude_code": RuntimeConfig(
                    name="claude_code",
                    command="claude",
                    credentials=[],
                ),
                "opencode": RuntimeConfig(
                    name="opencode",
                    command="opencode",
                    credentials=[],
                ),
            },
            agents={
                "codex_reviewer": AgentConfig(
                    name="codex_reviewer",
                    runtime="codex",
                    agent="reviewer",
                    model="gpt-5-codex",
                    description="reviewer",
                )
            },
        )

    def test_diagnostics_require_model_api_when_api_runtime_has_no_credentials(self) -> None:
        diagnostics = build_startup_diagnostics(
            self.config_with_credentials([]),
            installed_commands={"codex": True, "claude": False, "opencode": False},
        )

        self.assertTrue(diagnostics.needs_model_api_config)
        self.assertIn("Add a Codex or Claude credential profile.", diagnostics.messages)

    def test_diagnostics_accept_model_api_when_api_runtime_has_credentials(self) -> None:
        diagnostics = build_startup_diagnostics(
            self.config_with_credentials(
                [CredentialProfile("primary", api_key_env="OPENAI_API_KEY")]
            ),
            installed_commands={"codex": True, "claude": False, "opencode": False},
        )

        self.assertFalse(diagnostics.needs_model_api_config)

    def test_diagnostics_require_runtime_install_when_none_are_available(self) -> None:
        diagnostics = build_startup_diagnostics(
            self.config_with_credentials(
                [CredentialProfile("primary", api_key_env="OPENAI_API_KEY")]
            ),
            installed_commands={"codex": False, "claude": False, "opencode": False},
        )

        self.assertTrue(diagnostics.needs_runtime_install)
        self.assertIn("Install at least one coding runtime.", diagnostics.messages)

    def test_diagnostics_accept_runtime_when_one_command_is_available(self) -> None:
        diagnostics = build_startup_diagnostics(
            self.config_with_credentials(
                [CredentialProfile("primary", api_key_env="OPENAI_API_KEY")]
            ),
            installed_commands={"codex": False, "claude": True, "opencode": False},
        )

        self.assertFalse(diagnostics.needs_runtime_install)


if __name__ == "__main__":
    unittest.main()
