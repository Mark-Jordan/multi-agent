from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from madcli.config import (
    AgentConfig,
    AppConfig,
    CredentialProfile,
    RuntimeConfig,
    default_config,
    load_config,
    save_config,
    validate_config,
)


class ConfigTests(unittest.TestCase):
    def test_default_config_has_supported_runtimes(self) -> None:
        config = default_config()
        self.assertIn("opencode", config.runtimes)
        self.assertIn("codex", config.runtimes)
        self.assertIn("claude_code", config.runtimes)
        self.assertEqual(validate_config(config), [])

    def test_config_round_trips_through_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            save_config(default_config(), path)
            loaded = load_config(path)
            self.assertIn("strategy_engineer", loaded.agents)
            self.assertEqual(loaded.runtimes["codex"].command, "codex")

    def test_validation_rejects_unknown_runtime(self) -> None:
        config = AppConfig(
            runs_dir=Path(".runs"),
            default_workdir=Path("."),
            runtimes={"codex": RuntimeConfig("codex", "codex", [])},
            agents={
                "bad": AgentConfig(
                    name="bad",
                    runtime="missing",
                    agent="bad",
                    model=None,
                    description="bad agent",
                )
            },
        )
        self.assertEqual(
            validate_config(config),
            ["agent 'bad' references unknown runtime 'missing'"],
        )

    def test_validation_rejects_duplicate_credential_names(self) -> None:
        config = AppConfig(
            runs_dir=Path(".runs"),
            default_workdir=Path("."),
            runtimes={
                "codex": RuntimeConfig(
                    "codex",
                    "codex",
                    [
                        CredentialProfile("primary", api_key_env="OPENAI_API_KEY"),
                        CredentialProfile("primary", api_key_env="OPENAI_API_KEY_2"),
                    ],
                )
            },
            agents={
                "reviewer": AgentConfig(
                    name="reviewer",
                    runtime="codex",
                    agent="reviewer",
                    model=None,
                    description="reviewer",
                )
            },
        )
        self.assertIn(
            "runtime 'codex' has duplicate credential 'primary'",
            validate_config(config),
        )

    def test_validation_rejects_credential_without_key_source(self) -> None:
        config = AppConfig(
            runs_dir=Path(".runs"),
            default_workdir=Path("."),
            runtimes={
                "codex": RuntimeConfig(
                    "codex",
                    "codex",
                    [CredentialProfile("primary", base_url="https://example.test")],
                )
            },
            agents={
                "reviewer": AgentConfig(
                    name="reviewer",
                    runtime="codex",
                    agent="reviewer",
                    model=None,
                    description="reviewer",
                )
            },
        )
        self.assertIn(
            "runtime 'codex' credential 'primary' must define api_key or api_key_env",
            validate_config(config),
        )


if __name__ == "__main__":
    unittest.main()
