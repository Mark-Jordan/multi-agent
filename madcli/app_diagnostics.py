from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig


API_RUNTIMES = {"codex", "claude_code"}


@dataclass(frozen=True)
class StartupDiagnostics:
    needs_model_api_config: bool
    needs_runtime_install: bool
    messages: list[str]


def build_startup_diagnostics(
    config: AppConfig,
    *,
    installed_commands: dict[str, bool],
) -> StartupDiagnostics:
    has_api_credentials = any(
        runtime_name in API_RUNTIMES and runtime.credentials
        for runtime_name, runtime in config.runtimes.items()
    )
    has_runtime = any(installed_commands.values())
    messages: list[str] = []
    if not has_api_credentials:
        messages.append("Add a Codex or Claude credential profile.")
    if not has_runtime:
        messages.append("Install at least one coding runtime.")
    return StartupDiagnostics(
        needs_model_api_config=not has_api_credentials,
        needs_runtime_install=not has_runtime,
        messages=messages,
    )
