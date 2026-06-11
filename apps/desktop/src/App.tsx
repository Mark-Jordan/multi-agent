import {
  ChevronRight,
  Code2,
  FileCode2,
  Folder,
  KeyRound,
  Loader2,
  PanelRight,
  MessageSquarePlus,
  Play,
  Settings2,
  SplitSquareHorizontal,
  TerminalSquare,
  Wrench
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import type {
  Agent,
  CredentialProfile,
  CredentialSavePayload,
  Message,
  ProjectFile,
  RuntimeName,
  Session,
  StartupDiagnostics
} from "./types";

const agents: Agent[] = [
  {
    id: "strategy_engineer",
    label: "Strategy Engineer",
    role: "Engineer",
    runtime: "opencode",
    model: "anthropic/claude-sonnet-4-20250514",
    activeModel: "anthropic/claude-sonnet-4-20250514",
    activeCredential: "workspace",
    accent: "#4f8cff"
  },
  {
    id: "codex_reviewer",
    label: "Codex Reviewer",
    role: "Reviewer",
    runtime: "codex",
    model: "gpt-5-codex",
    activeModel: "gpt-5.1-codex",
    activeCredential: "backup",
    accent: "#2fbf8f"
  },
  {
    id: "claude_engineer",
    label: "Claude Engineer",
    role: "Engineer",
    runtime: "claude_code",
    model: "sonnet",
    activeModel: "sonnet",
    activeCredential: "primary",
    accent: "#d9823b"
  }
];

const credentials: CredentialProfile[] = [
  {
    id: "workspace",
    runtime: "opencode",
    label: "workspace",
    baseUrl: "runtime default",
    keySource: "local auth"
  },
  {
    id: "primary",
    runtime: "codex",
    label: "primary",
    baseUrl: "https://api.openai.com/v1",
    keySource: "env:OPENAI_API_KEY_PRIMARY"
  },
  {
    id: "backup",
    runtime: "codex",
    label: "backup",
    baseUrl: "https://gateway.example/v1",
    keySource: "env:OPENAI_API_KEY_BACKUP"
  },
  {
    id: "primary",
    runtime: "claude_code",
    label: "primary",
    baseUrl: "https://api.anthropic.com",
    keySource: "env:ANTHROPIC_API_KEY"
  }
];

const sessions: Session[] = [
  {
    id: "s-1",
    title: "Credential fallback review",
    agentId: "codex_reviewer",
    status: "active",
    updatedAt: "00:42"
  },
  {
    id: "s-2",
    title: "Context package workflow",
    agentId: "strategy_engineer",
    status: "idle",
    updatedAt: "Yesterday"
  },
  {
    id: "s-3",
    title: "Claude implementation pass",
    agentId: "claude_engineer",
    status: "failed",
    updatedAt: "Jun 10"
  }
];

const messages: Message[] = [
  {
    id: "m-1",
    role: "user",
    content:
      "Build a desktop workbench for madcli with sessions, project files, hidden editor, and immediate credential switching."
  },
  {
    id: "m-2",
    role: "agent",
    agentId: "strategy_engineer",
    runtime: "opencode",
    status: "succeeded",
    content:
      "I will keep madcli as the runtime bridge and add a desktop shell around sessions, runs, context packages, and project inspection."
  },
  {
    id: "m-3",
    role: "agent",
    agentId: "codex_reviewer",
    runtime: "codex",
    status: "dry_run",
    content:
      "Configuration changes should be persisted to madcli.config.json and used on the next run without restarting the app. The active profile selects base URL and API key source."
  },
  {
    id: "m-4",
    role: "event",
    content:
      "Run 20260611-004808-review-task-665224ce selected credential backup and model gpt-5.1-codex."
  }
];

const files: ProjectFile[] = [
  { path: "madcli", name: "madcli", type: "directory", depth: 0 },
  { path: "madcli/cli.py", name: "cli.py", type: "file", depth: 1 },
  { path: "madcli/config.py", name: "config.py", type: "file", depth: 1 },
  { path: "madcli/session_store.py", name: "session_store.py", type: "file", depth: 1 },
  { path: "madcli/project_files.py", name: "project_files.py", type: "file", depth: 1 },
  { path: "tests", name: "tests", type: "directory", depth: 0 },
  { path: "tests/test_cli.py", name: "test_cli.py", type: "file", depth: 1 },
  { path: "apps", name: "apps", type: "directory", depth: 0 },
  { path: "apps/desktop/src/App.tsx", name: "App.tsx", type: "file", depth: 1 }
];

function agentById(agentId?: string): Agent | undefined {
  return agents.find((agent) => agent.id === agentId);
}

export function App() {
  const [activeAgentId, setActiveAgentId] = useState("codex_reviewer");
  const [editorOpen, setEditorOpen] = useState(false);
  const [diagnostics, setDiagnostics] = useState<StartupDiagnostics | null>(null);
  const [setupBusy, setSetupBusy] = useState(false);
  const [setupMessage, setSetupMessage] = useState("");
  const [credentialForm, setCredentialForm] = useState<CredentialSavePayload>({
    runtime: "codex",
    agentId: "codex_reviewer",
    profileName: "primary",
    baseUrl: "https://api.openai.com/v1",
    apiKeyEnv: "OPENAI_API_KEY",
    model: "gpt-5-codex"
  });
  const activeAgent = agentById(activeAgentId) ?? agents[0];
  const availableCredentials = useMemo(
    () => credentials.filter((credential) => credential.runtime === activeAgent.runtime),
    [activeAgent.runtime]
  );
  const hasDesktopBridge = Boolean(window.madcliDesktop);

  useEffect(() => {
    let mounted = true;
    window.madcliDesktop
      ?.getStartupDiagnostics()
      .then((result) => {
        if (mounted) {
          setDiagnostics(result);
        }
      })
      .catch((error: Error) => {
        if (mounted) {
          setSetupMessage(error.message);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  async function saveProfile() {
    if (!window.madcliDesktop) {
      setSetupMessage("Desktop bridge is unavailable. Start the app with Electron.");
      return;
    }
    setSetupBusy(true);
    setSetupMessage("");
    try {
      const result = await window.madcliDesktop.saveCredentialProfile(credentialForm);
      setDiagnostics(result);
      setSetupMessage(`Saved profile to ${result.configPath}`);
    } catch (error) {
      setSetupMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSetupBusy(false);
    }
  }

  async function installRuntime(runtime: RuntimeName) {
    if (!window.madcliDesktop) {
      setSetupMessage("Desktop bridge is unavailable. Start the app with Electron.");
      return;
    }
    setSetupBusy(true);
    setSetupMessage("");
    try {
      const installResult = await window.madcliDesktop.installRuntime(runtime);
      if (installResult.cancelled) {
        setSetupMessage("Install cancelled.");
        return;
      }
      if (!installResult.ok) {
        setSetupMessage(installResult.stderr || "Install command failed.");
        return;
      }
      const nextDiagnostics = await window.madcliDesktop.getStartupDiagnostics();
      setDiagnostics(nextDiagnostics);
      setSetupMessage("Runtime installed.");
    } catch (error) {
      setSetupMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSetupBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <aside className="session-sidebar">
        <div className="brand-block">
          <div className="brand-mark">MA</div>
          <div>
            <h1>madcli Workbench</h1>
            <p>D:/CodeWorkspace/multi-agent</p>
          </div>
        </div>

        <button className="new-session-button" type="button">
          <MessageSquarePlus size={16} />
          New Session
        </button>

        <section className="session-list" aria-label="Sessions">
          {sessions.map((session) => {
            const sessionAgent = agentById(session.agentId);
            return (
              <button
                className={`session-item ${session.status === "active" ? "active" : ""}`}
                key={session.id}
                type="button"
              >
                <span
                  className="agent-dot"
                  style={{ backgroundColor: sessionAgent?.accent }}
                />
                <span className="session-copy">
                  <strong>{session.title}</strong>
                  <small>{sessionAgent?.label}</small>
                </span>
                <span className={`status-pill ${session.status}`}>{session.status}</span>
              </button>
            );
          })}
        </section>
      </aside>

      <section className="agent-rail" aria-label="Agents">
        {agents.map((agent) => (
          <button
            className={`agent-card ${agent.id === activeAgentId ? "selected" : ""}`}
            key={agent.id}
            onClick={() => setActiveAgentId(agent.id)}
            style={{ "--agent-accent": agent.accent } as CSSProperties}
            type="button"
          >
            <span className="agent-avatar">{agent.label.slice(0, 2).toUpperCase()}</span>
            <span>
              <strong>{agent.label}</strong>
              <small>
                {agent.role} · {agent.runtime}
              </small>
            </span>
          </button>
        ))}
      </section>

      <section className="conversation-panel">
        <header className="topbar">
          <div>
            <span className="eyebrow">Session</span>
            <h2>Credential fallback review</h2>
          </div>
          <div className="topbar-actions">
            <span className={hasDesktopBridge ? "bridge-status ok" : "bridge-status warn"}>
              {hasDesktopBridge ? "Desktop" : "Browser preview"}
            </span>
            <button type="button" title="Run doctor">
              <TerminalSquare size={17} />
              Doctor
            </button>
            <button type="button" title="Open settings">
              <Settings2 size={17} />
              Settings
            </button>
          </div>
        </header>

        <section className="runtime-strip">
          <label>
            Agent
            <select value={activeAgentId} onChange={(event) => setActiveAgentId(event.target.value)}>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Model
            <input defaultValue={activeAgent.activeModel} />
          </label>
          <label>
            Profile
            <select defaultValue={activeAgent.activeCredential}>
              {availableCredentials.map((credential) => (
                <option key={`${credential.runtime}-${credential.id}`} value={credential.id}>
                  {credential.label}
                </option>
              ))}
            </select>
          </label>
          <div className="credential-readout">
            <KeyRound size={16} />
            <span>{availableCredentials[0]?.baseUrl ?? "runtime default"}</span>
          </div>
        </section>

        {diagnostics?.needsModelApiConfig || diagnostics?.needsRuntimeInstall ? (
          <section className="setup-panel" aria-label="Setup required">
            <div className="setup-heading">
              <Wrench size={20} />
              <div>
                <span className="eyebrow">Setup Required</span>
                <h3>Configure this desktop app before running agents</h3>
              </div>
            </div>
            <div className="setup-grid">
              <section className="setup-block">
                <h4>Model API profile</h4>
                <p>
                  Add a profile for Codex or Claude. API keys are referenced by
                  environment variable name, not stored inline.
                </p>
                <div className="setup-form">
                  <label>
                    Runtime
                    <select
                      value={credentialForm.runtime}
                      onChange={(event) =>
                        setCredentialForm((form) => ({
                          ...form,
                          runtime: event.target.value as RuntimeName,
                          agentId:
                            event.target.value === "claude_code"
                              ? "claude_engineer"
                              : "codex_reviewer"
                        }))
                      }
                    >
                      <option value="codex">Codex</option>
                      <option value="claude_code">Claude Code</option>
                    </select>
                  </label>
                  <label>
                    Profile
                    <input
                      value={credentialForm.profileName}
                      onChange={(event) =>
                        setCredentialForm((form) => ({
                          ...form,
                          profileName: event.target.value
                        }))
                      }
                    />
                  </label>
                  <label>
                    Base URL
                    <input
                      value={credentialForm.baseUrl}
                      onChange={(event) =>
                        setCredentialForm((form) => ({ ...form, baseUrl: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    API key env
                    <input
                      value={credentialForm.apiKeyEnv}
                      onChange={(event) =>
                        setCredentialForm((form) => ({ ...form, apiKeyEnv: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Model
                    <input
                      value={credentialForm.model}
                      onChange={(event) =>
                        setCredentialForm((form) => ({ ...form, model: event.target.value }))
                      }
                    />
                  </label>
                </div>
                <button className="setup-action" disabled={setupBusy} onClick={saveProfile} type="button">
                  {setupBusy ? <Loader2 className="spin" size={16} /> : <KeyRound size={16} />}
                  Save Profile
                </button>
              </section>
              <section className="setup-block">
                <h4>Coding runtime</h4>
                <p>
                  At least one runtime must be installed. Install actions require
                  confirmation in the desktop app before any command runs.
                </p>
                <div className="runtime-checks">
                  {diagnostics.installedRuntimes.map((runtime) => (
                    <div className="runtime-check" key={runtime.runtime}>
                      <span>
                        <strong>{runtime.runtime}</strong>
                        <small>{runtime.command}</small>
                      </span>
                      {runtime.installed ? (
                        <span className="status-pill succeeded">installed</span>
                      ) : (
                        <button
                          disabled={setupBusy}
                          onClick={() => installRuntime(runtime.runtime)}
                          type="button"
                        >
                          Install
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            </div>
            {setupMessage ? <pre className="setup-message">{setupMessage}</pre> : null}
          </section>
        ) : null}

        <section className="message-stream" aria-label="Conversation">
          {messages.map((message) => {
            const messageAgent = agentById(message.agentId);
            return (
              <article className={`message ${message.role}`} key={message.id}>
                <div
                  className="message-avatar"
                  style={{ backgroundColor: messageAgent?.accent ?? "#272c33" }}
                >
                  {message.role === "user" ? "U" : message.role === "event" ? "EV" : messageAgent?.label.slice(0, 2).toUpperCase()}
                </div>
                <div className="message-body">
                  <div className="message-meta">
                    <strong>
                      {message.role === "user"
                        ? "You"
                        : message.role === "event"
                          ? "Run Event"
                          : messageAgent?.label}
                    </strong>
                    {message.runtime ? <span>{message.runtime}</span> : null}
                    {message.status ? <span className={`status-pill ${message.status}`}>{message.status}</span> : null}
                  </div>
                  <p>{message.content}</p>
                </div>
              </article>
            );
          })}
        </section>

        <footer className="composer">
          <textarea placeholder="Send a task to the selected agent..." />
          <div className="composer-actions">
            <button
              className={editorOpen ? "toggle active" : "toggle"}
              onClick={() => setEditorOpen((open) => !open)}
              type="button"
            >
              <Code2 size={17} />
              {editorOpen ? "Hide Editor" : "Show Editor"}
            </button>
            <button className="primary-action" type="button">
              <Play size={17} />
              Run
            </button>
          </div>
        </footer>
      </section>

      <aside className="project-panel">
        <header>
          <div>
            <span className="eyebrow">Project</span>
            <h2>Files</h2>
          </div>
          <button type="button" title="Toggle split view">
            <PanelRight size={17} />
          </button>
        </header>

        <section className="file-tree" aria-label="Project files">
          {files.map((file) => (
            <button className="file-row" key={file.path} style={{ paddingLeft: `${12 + file.depth * 18}px` }} type="button">
              {file.type === "directory" ? <Folder size={15} /> : <FileCode2 size={15} />}
              <span>{file.name}</span>
              {file.type === "directory" ? <ChevronRight size={14} /> : null}
            </button>
          ))}
        </section>

        <section className="run-details">
          <h3>Run Artifacts</h3>
          <button type="button">metadata.json</button>
          <button type="button">events.jsonl</button>
          <button type="button">command.json</button>
          <button type="button">stdout.txt</button>
          <button type="button">stderr.txt</button>
        </section>
      </aside>

      <section className={`editor-drawer ${editorOpen ? "open" : ""}`} aria-hidden={!editorOpen}>
        <header>
          <div>
            <span className="eyebrow">Editor</span>
            <h2>madcli/config.py</h2>
          </div>
          <button type="button" onClick={() => setEditorOpen(false)}>
            <SplitSquareHorizontal size={17} />
            Collapse
          </button>
        </header>
        <pre>
          <code>{`class AgentConfig:
    name: str
    runtime: str
    agent: str
    model: str | None
    description: str
    active_model: str | None = None
    active_credential: str | None = None`}</code>
        </pre>
      </section>
    </main>
  );
}
