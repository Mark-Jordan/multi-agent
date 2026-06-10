from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("madcli.config.json")


@dataclass(frozen=True)
class CredentialProfile:
    name: str
    base_url: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None


@dataclass(frozen=True)
class RuntimeConfig:
    name: str
    command: str
    credentials: list[CredentialProfile]


@dataclass(frozen=True)
class AgentConfig:
    name: str
    runtime: str
    agent: str
    model: str | None
    description: str


@dataclass(frozen=True)
class AppConfig:
    runs_dir: Path
    default_workdir: Path
    runtimes: dict[str, RuntimeConfig]
    agents: dict[str, AgentConfig]


def default_config() -> AppConfig:
    return AppConfig(
        runs_dir=Path(".madcli") / "runs",
        default_workdir=Path("."),
        runtimes={
            "opencode": RuntimeConfig(
                name="opencode", command="opencode", credentials=[]
            ),
            "codex": RuntimeConfig(name="codex", command="codex", credentials=[]),
            "claude_code": RuntimeConfig(
                name="claude_code", command="claude", credentials=[]
            ),
        },
        agents={
            "strategy_engineer": AgentConfig(
                name="strategy_engineer",
                runtime="opencode",
                agent="engineer",
                model="anthropic/claude-sonnet-4-20250514",
                description="Implements strategy code using the selected coding runtime.",
            ),
            "codex_reviewer": AgentConfig(
                name="codex_reviewer",
                runtime="codex",
                agent="reviewer",
                model="gpt-5-codex",
                description="Reviews diffs and implementation reports.",
            ),
            "claude_engineer": AgentConfig(
                name="claude_engineer",
                runtime="claude_code",
                agent="strategy-engineer",
                model="sonnet",
                description="Implements code through Claude Code.",
            ),
        },
    )


def app_config_to_dict(config: AppConfig) -> dict[str, Any]:
    return {
        "runs_dir": str(config.runs_dir),
        "default_workdir": str(config.default_workdir),
        "runtimes": {
            name: {
                "command": runtime.command,
                "credentials": [
                    {
                        key: value
                        for key, value in {
                            "name": profile.name,
                            "base_url": profile.base_url,
                            "api_key": profile.api_key,
                            "api_key_env": profile.api_key_env,
                        }.items()
                        if value is not None
                    }
                    for profile in runtime.credentials
                ],
            }
            for name, runtime in config.runtimes.items()
        },
        "agents": {
            name: {
                "runtime": agent.runtime,
                "agent": agent.agent,
                "model": agent.model,
                "description": agent.description,
            }
            for name, agent in config.agents.items()
        },
    }


def app_config_from_dict(data: dict[str, Any]) -> AppConfig:
    runtimes = {
        name: RuntimeConfig(
            name=name,
            command=str(value["command"]),
            credentials=[
                CredentialProfile(
                    name=str(profile["name"]),
                    base_url=profile.get("base_url"),
                    api_key=profile.get("api_key"),
                    api_key_env=profile.get("api_key_env"),
                )
                for profile in value.get("credentials", [])
            ],
        )
        for name, value in data.get("runtimes", {}).items()
    }
    agents = {
        name: AgentConfig(
            name=name,
            runtime=str(value["runtime"]),
            agent=str(value.get("agent", name)),
            model=value.get("model"),
            description=str(value.get("description", "")),
        )
        for name, value in data.get("agents", {}).items()
    }
    return AppConfig(
        runs_dir=Path(str(data.get("runs_dir", ".madcli/runs"))),
        default_workdir=Path(str(data.get("default_workdir", "."))),
        runtimes=runtimes,
        agents=agents,
    )


def validate_config(config: AppConfig) -> list[str]:
    errors: list[str] = []
    if not config.runtimes:
        errors.append("config must define at least one runtime")
    if not config.agents:
        errors.append("config must define at least one agent")
    for name, runtime in config.runtimes.items():
        if not runtime.command:
            errors.append(f"runtime '{name}' must define a command")
        seen_profiles: set[str] = set()
        for profile in runtime.credentials:
            if not profile.name:
                errors.append(f"runtime '{name}' has a credential without a name")
            if profile.name in seen_profiles:
                errors.append(
                    f"runtime '{name}' has duplicate credential '{profile.name}'"
                )
            seen_profiles.add(profile.name)
            if profile.api_key and profile.api_key_env:
                errors.append(
                    f"runtime '{name}' credential '{profile.name}' must not define both api_key and api_key_env"
                )
            if not profile.api_key and not profile.api_key_env:
                errors.append(
                    f"runtime '{name}' credential '{profile.name}' must define api_key or api_key_env"
                )
    for name, agent in config.agents.items():
        if agent.runtime not in config.runtimes:
            errors.append(
                f"agent '{name}' references unknown runtime '{agent.runtime}'"
            )
        if not agent.agent:
            errors.append(f"agent '{name}' must define runtime agent name")
    return errors


def save_config(config: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.write_text(
        json.dumps(app_config_to_dict(config), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    config = app_config_from_dict(data)
    errors = validate_config(config)
    if errors:
        raise ValueError("; ".join(errors))
    return config
