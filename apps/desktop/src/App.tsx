import {
  Activity,
  Bot,
  ChevronRight,
  Code2,
  FileCode2,
  Folder,
  FolderCog,
  FolderOpen,
  KeyRound,
  Loader2,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Save,
  SendHorizontal,
  Server,
  Settings2,
  SplitSquareHorizontal,
  TerminalSquare,
  Trash2,
  Wrench,
  X
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type {
  Agent,
  AgentInstance,
  AgentRunReadiness,
  Artifact,
  CommandResult,
  CredentialSavePayload,
  Message,
  ProjectFile,
  RoleTemplate,
  RuntimeName,
  Session,
  SettingsState,
  StartupDiagnostics
} from "./types";

type SettingsTab = "agents" | "roles" | "profiles" | "runtimes" | "workspace" | "diagnostics";

const agents: Agent[] = [
  {
    id: "strategy_engineer",
    label: "opencode",
    role: "工程师",
    runtime: "opencode",
    model: "anthropic/claude-sonnet-4-20250514",
    activeModel: "anthropic/claude-sonnet-4-20250514",
    activeCredential: "workspace",
    accent: "#4f8cff"
  },
  {
    id: "codex_reviewer",
    label: "codex",
    role: "评审",
    runtime: "codex",
    model: "gpt-5-codex",
    activeModel: "gpt-5-codex",
    activeCredential: "primary",
    accent: "#2fbf8f"
  },
  {
    id: "claude_engineer",
    label: "claude",
    role: "工程师",
    runtime: "claude_code",
    model: "sonnet",
    activeModel: "sonnet",
    activeCredential: "primary",
    accent: "#d9823b"
  }
];

const demoSessions: Session[] = [
  {
    id: "s-1",
    title: "凭据回退检查",
    agentId: "codex_reviewer",
    status: "active",
    updatedAt: "刚刚"
  }
];

const demoMessages: Message[] = [
  {
    id: "m-1",
    role: "user",
    content: "检查当前工作目录并生成一次 dry-run 命令。"
  },
  {
    id: "m-2",
    role: "agent",
    agentId: "codex_reviewer",
    runtime: "codex",
    status: "dry_run",
    content: "在 Electron 桌面端中，发送任务前会先检查当前智能体的运行配置。"
  }
];

const demoFiles: ProjectFile[] = [
  { path: "madcli", name: "madcli", type: "directory", depth: 0 },
  { path: "madcli/cli.py", name: "cli.py", type: "file", depth: 1 },
  { path: "apps/desktop/src/App.tsx", name: "App.tsx", type: "file", depth: 3 }
];

function agentById(agentId?: string): Agent | undefined {
  return agents.find((agent) => agent.id === agentId);
}

export function App() {
  const [activeAgentId, setActiveAgentId] = useState("codex_reviewer");
  const [activeInstanceId, setActiveInstanceId] = useState("codex_reviewer:reviewer");
  const [settingsAgentId, setSettingsAgentId] = useState("codex_reviewer");
  const [roleAssignmentAgentId, setRoleAssignmentAgentId] = useState("codex_reviewer");
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("agents");
  const [activeSessionId, setActiveSessionId] = useState(demoSessions[0]?.id ?? "");
  const [sessionRows, setSessionRows] = useState<Session[]>(demoSessions);
  const [sessionMessages, setSessionMessages] = useState<Message[]>(demoMessages);
  const [projectFiles, setProjectFiles] = useState<ProjectFile[]>(demoFiles);
  const [runArtifacts, setRunArtifacts] = useState<Artifact[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [taskText, setTaskText] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState("");
  const [settingsState, setSettingsState] = useState<SettingsState | null>(null);
  const [configPrompt, setConfigPrompt] = useState<AgentRunReadiness | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorTitle, setEditorTitle] = useState("输出");
  const [editorContent, setEditorContent] = useState("");
  const [diagnostics, setDiagnostics] = useState<StartupDiagnostics | null>(null);
  const [setupBusy, setSetupBusy] = useState(false);
  const [roleForm, setRoleForm] = useState<RoleTemplate>({
    id: "reviewer",
    name: "Reviewer",
    prompt: ""
  });
  const [roleAssignmentIds, setRoleAssignmentIds] = useState<string[]>(["reviewer"]);
  const [credentialForm, setCredentialForm] = useState<CredentialSavePayload>({
    runtime: "codex",
    agentId: "codex_reviewer",
    profileName: "primary",
    baseUrl: "https://api.openai.com/v1",
    apiKey: "",
    model: "gpt-5-codex"
  });
  const messageStreamRef = useRef<HTMLElement | null>(null);

  const hasDesktopBridge = Boolean(window.madcliDesktop);
  const fallbackInstances = useMemo(() => buildFallbackAgentInstances(), []);
  const agentInstances =
    settingsState?.agentInstances && settingsState.agentInstances.length > 0
      ? settingsState.agentInstances
      : fallbackInstances;
  const activeInstance =
    agentInstances.find((instance) => instance.id === activeInstanceId) ??
    agentInstances.find((instance) => instance.agentId === activeAgentId) ??
    agentInstances[0];
  const activeAgent = agentById(activeInstance?.agentId ?? activeAgentId) ?? agents[0];
  const activeRoleId = activeInstance?.roleId ?? defaultRoleIdForAgent(activeAgent.id);
  const settingsAgent = agentById(settingsAgentId) ?? activeAgent;
  const settingsRuntime = settingsAgent.runtime;
  const activeSession = sessionRows.find((session) => session.id === activeSessionId);
  const headerTitle = activeSession?.title ?? "新会话";
  const workspaceRoot = diagnostics?.workspaceRoot ?? "D:/CodeWorkspace/multi-agent";
  const appShellClass = `app-shell ${sidebarOpen ? "" : "sessions-collapsed"}`;
  const selectedRuntimeStatus = useMemo(
    () => diagnostics?.installedRuntimes.find((runtime) => runtime.runtime === settingsRuntime),
    [settingsRuntime, diagnostics?.installedRuntimes]
  );
  const runtimeProfiles = settingsState?.credentialsByRuntime?.[settingsRuntime] ?? [];
  const roleTemplates = useMemo(
    () => sortRoleTemplates(Object.values(settingsState?.roleTemplates ?? {})),
    [settingsState]
  );
  const roleTemplateMap = useMemo(() => settingsState?.roleTemplates ?? {}, [settingsState]);
  const isSystemRoleForm = Boolean(roleForm.system);

  useEffect(() => {
    let mounted = true;
    async function loadDesktopState() {
      if (!window.madcliDesktop) {
        return;
      }
      try {
        const [diagnosticResult, sessionsResult, filesResult, stateResult] = await Promise.all([
          window.madcliDesktop.getStartupDiagnostics(),
          window.madcliDesktop.listSessions(),
          window.madcliDesktop.listProjectFiles(),
          window.madcliDesktop.getSettingsState()
        ]);
        if (!mounted) {
          return;
        }
        setDiagnostics(diagnosticResult);
        setSettingsState(stateResult);
        setRoleForm(defaultRoleForm(stateResult));
        setProjectFiles(filesResult.length > 0 ? filesResult : demoFiles);
        if (sessionsResult.length === 0) {
          const created = await window.madcliDesktop.createSession({
            title: "新会话",
            activeAgent: activeAgent.id
          });
          if (!mounted) {
            return;
          }
          setSessionRows([created]);
          setActiveSessionId(created.id);
          setSessionMessages([]);
          return;
        }
        const first = sessionsResult[0];
        setSessionRows(markActiveSession(sessionsResult, first.id));
        setActiveSessionId(first.id);
        setActiveAgentId(first.agentId);
        setActiveInstanceId(firstInstanceIdForAgent(first.agentId, stateResult));
        setSettingsAgentId(first.agentId);
        const detail = await window.madcliDesktop.loadSession(first.id);
        if (mounted) {
          setSessionMessages(detail.messages);
        }
      } catch (error) {
        setNotice(error instanceof Error ? error.message : String(error));
      }
    }
    void loadDesktopState();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (agentInstances.length === 0) {
      return;
    }
    const current = agentInstances.find((instance) => instance.id === activeInstanceId);
    if (current) {
      if (current.agentId !== activeAgentId) {
        setActiveAgentId(current.agentId);
      }
      return;
    }
    const nextInstance =
      agentInstances.find((instance) => instance.agentId === activeAgentId) ?? agentInstances[0];
    setActiveInstanceId(nextInstance.id);
    setActiveAgentId(nextInstance.agentId);
  }, [activeAgentId, activeInstanceId, agentInstances]);

  useEffect(() => {
    const configuredRoleIds =
      settingsState?.agentRoles?.[roleAssignmentAgentId] ?? [defaultRoleIdForAgent(roleAssignmentAgentId)];
    setRoleAssignmentIds(configuredRoleIds.filter((roleId) => roleTemplateMap[roleId]));
  }, [roleAssignmentAgentId, roleTemplateMap, settingsState]);

  useEffect(() => {
    const runtime = settingsAgent.runtime;
    const config = settingsState?.agents?.[settingsAgent.id];
    const profileName = config?.active_credential ?? (runtime === "claude_code" ? "anthropic" : "primary");
    const model = config?.active_model ?? config?.model ?? settingsAgent.activeModel;
    const profile = settingsState?.credentialsByRuntime?.[runtime]?.find(
      (item) => item.name === profileName
    );
    setCredentialForm({
      runtime,
      agentId: settingsAgent.id,
      profileName,
      baseUrl: profile?.base_url ?? defaultBaseUrl(runtime),
      apiKey: "",
      model: model ?? settingsAgent.model
    });
  }, [settingsAgent.id, settingsAgent.runtime, settingsAgent.activeModel, settingsAgent.model, settingsState]);

  useEffect(() => {
    if (!window.madcliDesktop || !activeSessionId) {
      return;
    }
    if (!sessionMessages.some((message) => message.status === "running")) {
      return;
    }
    let cancelled = false;
    const intervalId = window.setInterval(() => {
      window.madcliDesktop
        ?.loadSession(activeSessionId)
        .then(async (detail) => {
          if (cancelled) {
            return;
          }
          setSessionMessages(detail.messages);
          const latestRunId = [...detail.messages]
            .reverse()
            .find((message) => message.runId)?.runId;
          if (latestRunId) {
            setSelectedRunId(latestRunId);
            setRunArtifacts(await window.madcliDesktop!.listArtifacts(latestRunId));
          }
        })
        .catch((error) => {
          if (!cancelled) {
            setNotice(error instanceof Error ? error.message : String(error));
          }
        });
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [activeSessionId, sessionMessages]);

  useEffect(() => {
    const stream = messageStreamRef.current;
    if (!stream) {
      return;
    }
    stream.scrollTo({
      top: stream.scrollHeight,
      behavior: "smooth"
    });
  }, [sessionMessages]);

  async function loadSettingsState() {
    if (!window.madcliDesktop) {
      return;
    }
    const state = await window.madcliDesktop.getSettingsState();
    setSettingsState(state);
    setRoleForm((current) => (current.prompt ? current : defaultRoleForm(state)));
    setDiagnostics(state.diagnostics);
  }

  function appendLocalMessage(message: Omit<Message, "id">) {
    setSessionMessages((current) => [
      ...current,
      { id: `local-${Date.now()}-${current.length}`, ...message }
    ]);
  }

  async function refreshSessions(nextActiveSessionId: string) {
    if (!window.madcliDesktop) {
      setSessionRows((current) => markActiveSession(current, nextActiveSessionId));
      return;
    }
    const rows = await window.madcliDesktop.listSessions();
    setSessionRows(markActiveSession(rows, nextActiveSessionId));
  }

  async function refreshProjectFiles() {
    if (!window.madcliDesktop) {
      return;
    }
    const [diagnosticResult, filesResult] = await Promise.all([
      window.madcliDesktop.getStartupDiagnostics(),
      window.madcliDesktop.listProjectFiles()
    ]);
    setDiagnostics(diagnosticResult);
    setProjectFiles(filesResult);
  }

  async function openSettings(tab: SettingsTab = "agents") {
    setSettingsTab(tab);
    setSettingsOpen(true);
    setSettingsAgentId(activeAgent.id);
    setRoleAssignmentAgentId(activeAgent.id);
    try {
      await loadSettingsState();
    } catch (error) {
      setSettingsMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function openSession(sessionId: string) {
    setActiveSessionId(sessionId);
    await refreshSessions(sessionId);
    if (!window.madcliDesktop) {
      setSessionMessages(demoMessages);
      return;
    }
    try {
      const detail = await window.madcliDesktop.loadSession(sessionId);
      setActiveAgentId(detail.agentId);
      setActiveInstanceId(firstInstanceIdForAgent(detail.agentId, settingsState));
      setSettingsAgentId(detail.agentId);
      setSessionMessages(detail.messages);
      setNotice("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  }

  async function deleteSession(sessionId: string) {
    if (!window.madcliDesktop) {
      setSessionRows((current) => current.filter((session) => session.id !== sessionId));
      if (sessionId === activeSessionId) {
        setActiveSessionId("");
        setSessionMessages([]);
      }
      return;
    }
    setActionBusy(true);
    try {
      const rows = await window.madcliDesktop.deleteSession(sessionId);
      if (rows.length === 0) {
        const created = await window.madcliDesktop.createSession({
          title: "新会话",
          activeAgent: activeAgent.id
        });
        setSessionRows([created]);
        setActiveSessionId(created.id);
        setSessionMessages([]);
        return;
      }
      const nextActiveId = sessionId === activeSessionId ? rows[0].id : activeSessionId;
      setSessionRows(markActiveSession(rows, nextActiveId));
      if (sessionId === activeSessionId) {
        const detail = await window.madcliDesktop.loadSession(nextActiveId);
        setActiveSessionId(nextActiveId);
        setSessionMessages(detail.messages);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function createSession() {
    if (!window.madcliDesktop) {
      const session: Session = {
        id: `demo-${Date.now()}`,
        title: "新会话",
        agentId: activeAgent.id,
        status: "active",
        updatedAt: "刚刚",
        messageCount: 0
      };
      setSessionRows((current) => markActiveSession([session, ...current], session.id));
      setActiveSessionId(session.id);
      setSessionMessages([]);
      return;
    }
    setActionBusy(true);
    try {
      const created = await window.madcliDesktop.createSession({
        title: "新会话",
        activeAgent: activeAgentId
      });
      setActiveSessionId(created.id);
      setSessionMessages([]);
      await refreshSessions(created.id);
      setNotice("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function runTask() {
    const task = taskText.trim();
    if (!task) {
      setNotice("请输入任务内容。");
      return;
    }
    if (!window.madcliDesktop) {
      appendLocalMessage({ role: "user", content: task });
      appendLocalMessage({
        role: "agent",
        agentId: activeAgent.id,
        runtime: activeAgent.runtime,
        status: "failed",
        content: "浏览器预览不能调用 madcli，请打开桌面端程序。"
      });
      setTaskText("");
      return;
    }
    const readiness = await window.madcliDesktop.canRunAgent(activeAgent.id);
    if (!readiness.ok) {
      setConfigPrompt(readiness);
      return;
    }
    setActionBusy(true);
    setNotice("");
    try {
      const sessionId =
        activeSessionId ||
        (
          await window.madcliDesktop.createSession({
            title: "新会话",
            activeAgent: activeAgent.id
          })
        ).id;
      const result = await window.madcliDesktop.runTask({
        sessionId,
        task,
        agent: activeAgent.id,
        roleId: activeRoleId
      });
      setTaskText("");
      await openSession(sessionId);
      if (result.runId) {
        setSelectedRunId(result.runId);
        setRunArtifacts(await window.madcliDesktop.listArtifacts(result.runId));
      }
      if (!result.ok) {
        showCommandResult(result);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function runCommand(commandName: "doctor" | "status") {
    if (!window.madcliDesktop) {
      appendLocalMessage({
        role: "event",
        content: "该操作需要在 Electron 桌面端中执行。"
      });
      return;
    }
    setActionBusy(true);
    try {
      const result =
        commandName === "doctor"
          ? await window.madcliDesktop.runDoctor()
          : await window.madcliDesktop.runStatus();
      showCommandResult(result);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function chooseWorkspace() {
    if (!window.madcliDesktop) {
      setNotice("选择工作目录需要在桌面端中操作。");
      return;
    }
    setActionBusy(true);
    try {
      const diagnosticResult = await window.madcliDesktop.chooseWorkspace();
      setDiagnostics(diagnosticResult);
      await Promise.all([refreshProjectFiles(), loadSettingsState()]);
      setNotice("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function openProjectFile(file: ProjectFile) {
    if (file.type === "directory") {
      setNotice(`已选择目录：${file.path}`);
      return;
    }
    if (!window.madcliDesktop) {
      setEditorTitle(file.path);
      setEditorContent("读取文件需要在 Electron 桌面端中操作。");
      setEditorOpen(true);
      return;
    }
    try {
      const result = await window.madcliDesktop.readProjectFile(file.path);
      setEditorTitle(result.path);
      setEditorContent(result.content);
      setEditorOpen(true);
      setNotice("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  }

  async function openArtifact(artifact: Artifact) {
    if (!selectedRunId || !window.madcliDesktop) {
      setNotice("当前没有可读取的运行产物。");
      return;
    }
    try {
      const result = await window.madcliDesktop.readArtifact({
        runId: selectedRunId,
        artifactPath: artifact.path
      });
      setEditorTitle(`${selectedRunId}/${result.path}`);
      setEditorContent(result.content);
      setEditorOpen(true);
      setNotice("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  }

  async function saveProfile() {
    if (!window.madcliDesktop) {
      setSettingsMessage("桌面桥接不可用，请从 Electron 桌面端启动。");
      return;
    }
    const existingProfile = runtimeProfiles.find((profile) => profile.name === credentialForm.profileName.trim());
    if (!credentialForm.baseUrl.trim() || (!credentialForm.apiKey.trim() && !existingProfile?.api_key_set)) {
      setSettingsMessage("Base URL 和 API Key 必须成对填写。");
      return;
    }
    setSetupBusy(true);
    setSettingsMessage("");
    try {
      const result = await window.madcliDesktop.saveCredentialProfile(credentialForm);
      setDiagnostics(result);
      await loadSettingsState();
      setSettingsMessage(`已保存到 ${result.configPath}`);
      setConfigPrompt(null);
    } catch (error) {
      setSettingsMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSetupBusy(false);
    }
  }

  async function saveRoleTemplate() {
    if (!window.madcliDesktop) {
      setSettingsMessage("桌面桥接不可用，请从 Electron 桌面端启动。");
      return;
    }
    if (isSystemRoleForm) {
      setSettingsMessage("系统默认角色不能修改。请点击“新建”添加自定义角色提示词。");
      return;
    }
    if (!roleForm.name.trim() || !roleForm.prompt.trim()) {
      setSettingsMessage("角色名称和提示词不能为空。");
      return;
    }
    setSetupBusy(true);
    setSettingsMessage("");
    try {
      const nextState = await window.madcliDesktop.saveRoleTemplate({
        id: roleForm.id.trim(),
        name: roleForm.name.trim(),
        prompt: roleForm.prompt.trim(),
        system: roleForm.system
      });
      setSettingsState(nextState);
      setDiagnostics(nextState.diagnostics);
      const savedRole =
        nextState.roleTemplates[roleForm.id.trim()] ??
        Object.values(nextState.roleTemplates).find((role) => role.name === roleForm.name.trim());
      if (savedRole) {
        setRoleForm(savedRole);
      }
      setSettingsMessage("已保存角色提示词。");
    } catch (error) {
      setSettingsMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSetupBusy(false);
    }
  }

  async function saveAgentRoles() {
    if (!window.madcliDesktop) {
      setSettingsMessage("桌面桥接不可用，请从 Electron 桌面端启动。");
      return;
    }
    if (roleAssignmentIds.length === 0) {
      setSettingsMessage("至少需要为智能体选择一个角色。");
      return;
    }
    setSetupBusy(true);
    setSettingsMessage("");
    try {
      const nextState = await window.madcliDesktop.saveAgentRoles({
        agentId: roleAssignmentAgentId,
        roleIds: roleAssignmentIds
      });
      setSettingsState(nextState);
      setDiagnostics(nextState.diagnostics);
      const nextInstanceId = firstInstanceIdForAgent(roleAssignmentAgentId, nextState);
      if (roleAssignmentAgentId === activeAgent.id) {
        setActiveInstanceId(nextInstanceId);
      }
      setSettingsMessage("已保存智能体角色绑定。");
    } catch (error) {
      setSettingsMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSetupBusy(false);
    }
  }

  async function installRuntime(runtime: RuntimeName) {
    if (!window.madcliDesktop) {
      setSettingsMessage("桌面桥接不可用，请从 Electron 桌面端启动。");
      return;
    }
    setSetupBusy(true);
    setSettingsMessage("");
    try {
      const installResult = await window.madcliDesktop.installRuntime(runtime);
      if (installResult.cancelled) {
        setSettingsMessage("已取消安装。");
        return;
      }
      if (!installResult.ok) {
        setSettingsMessage(installResult.stderr || "安装命令执行失败。");
        return;
      }
      await loadSettingsState();
      setSettingsMessage("运行时已安装。");
    } catch (error) {
      setSettingsMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSetupBusy(false);
    }
  }

  function showCommandResult(result: CommandResult) {
    const title = result.title ?? "madcli";
    const output = [result.stdout, result.stderr].filter(Boolean).join("\n");
    appendLocalMessage({
      role: "event",
      status: result.ok ? "succeeded" : "failed",
      content: `${title} 退出码：${result.code ?? "n/a"}${result.runId ? `，运行 ID：${result.runId}` : ""}。`
    });
    setEditorTitle(title);
    setEditorContent(output || "无输出");
    setEditorOpen(true);
  }

  return (
    <main className={appShellClass}>
      <aside className="session-sidebar" aria-hidden={!sidebarOpen}>
        <div className="brand-block">
          <div className="brand-mark">MA</div>
          <div>
            <h1>madcli 工作台</h1>
            <p>{hasDesktopBridge ? "桌面端已连接" : "浏览器预览"}</p>
          </div>
        </div>

        <button className="new-session-button" disabled={actionBusy} onClick={createSession} type="button">
          {actionBusy ? <Loader2 className="spin" size={15} /> : <MessageSquarePlus size={15} />}
          新建会话
        </button>

        <section className="session-list" aria-label="会话列表">
          {sessionRows.map((session) => {
            const sessionAgent = agentById(session.agentId);
            return (
              <div
                className={`session-item ${session.status === "active" ? "active" : ""}`}
                key={session.id}
              >
                <button
                  className="session-open-button"
                  onClick={() => openSession(session.id)}
                  type="button"
                >
                  <span className="agent-dot" style={{ backgroundColor: sessionAgent?.accent }} />
                  <span className="session-copy">
                    <strong>{session.title}</strong>
                    <small>{sessionAgent?.label ?? session.agentId}</small>
                  </span>
                  <span className={`status-pill ${session.status}`}>{statusLabel(session.status)}</span>
                </button>
                <button
                  className="session-delete-button"
                  disabled={actionBusy}
                  onClick={() => deleteSession(session.id)}
                  title="删除会话"
                  type="button"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            );
          })}
        </section>
      </aside>

      <section className="conversation-panel">
        <header className="topbar">
          <div className="topbar-title">
            <button
              className="icon-button"
              onClick={() => setSidebarOpen((open) => !open)}
              title={sidebarOpen ? "收起会话列表" : "展开会话列表"}
              type="button"
            >
              {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
            </button>
            <div>
              <span className="eyebrow">当前会话</span>
              <h2>{headerTitle}</h2>
            </div>
          </div>
          <div className="topbar-actions">
            <button disabled={actionBusy} onClick={() => runCommand("doctor")} type="button" title="运行诊断">
              <TerminalSquare size={16} />
              诊断
            </button>
            <button onClick={() => openSettings("agents")} type="button" title="打开设置">
              <Settings2 size={16} />
              设置
            </button>
          </div>
        </header>

        {notice ? <div className="notice-bar">{notice}</div> : null}

        <section className="message-stream" aria-label="对话历史" ref={messageStreamRef}>
          {sessionMessages.length === 0 ? (
            <div className="empty-conversation">
              <MessageSquarePlus size={20} />
              <span>在下方输入任务开始当前会话。</span>
            </div>
          ) : (
            sessionMessages.map((message) => {
              const messageAgent = agentById(message.agentId);
              return (
                <article className={`message ${message.role}`} key={message.id}>
                  <div
                    className="message-avatar"
                    style={{ backgroundColor: messageAgent?.accent ?? "#272c33" }}
                  >
                    {message.role === "user"
                      ? "我"
                      : message.role === "event"
                        ? "EV"
                        : message.role === "system"
                          ? "系"
                          : messageAgent?.label.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="message-body">
                    <div className="message-meta">
                      <strong>
                        {message.role === "user"
                          ? "我"
                          : message.role === "event"
                            ? "运行事件"
                            : message.role === "system"
                              ? "系统"
                              : messageAgent?.label}
                      </strong>
                      {message.runtime ? <span>{message.runtime}</span> : null}
                      {message.status ? <span className={`status-pill ${message.status}`}>{statusLabel(message.status)}</span> : null}
                    </div>
                    {message.status === "running" && !message.content.trim() ? (
                      <div className="agent-loading" aria-label="智能体正在输出">
                        <span />
                        <span />
                        <span />
                      </div>
                    ) : (
                      <p>{message.content}</p>
                    )}
                  </div>
                </article>
              );
            })
          )}
        </section>

        <footer className="composer">
          <div className="identity-bar">
            <label>
              当前身份
              <select
                value={activeInstance?.id ?? ""}
                onChange={(event) => {
                  const nextInstance = agentInstances.find((instance) => instance.id === event.target.value);
                  if (!nextInstance) {
                    return;
                  }
                  setActiveInstanceId(nextInstance.id);
                  setActiveAgentId(nextInstance.agentId);
                  setSettingsAgentId(nextInstance.agentId);
                }}
              >
                {agentInstances.map((instance) => {
                  const agent = agentById(instance.agentId);
                  return (
                    <option key={instance.id} value={instance.id}>
                      {agent?.label ?? instance.agentId} · {instance.roleName}
                    </option>
                  );
                })}
              </select>
            </label>
            <span>
              {runtimeLabel(activeAgent.runtime)} · {activeInstance?.roleName ?? "默认角色"}
            </span>
          </div>
          <textarea
            onChange={(event) => setTaskText(event.target.value)}
            placeholder="输入任务并发送给当前会话的智能体..."
            value={taskText}
          />
          <div className="composer-actions">
            <button
              className={editorOpen ? "toggle active" : "toggle"}
              onClick={() => setEditorOpen((open) => !open)}
              type="button"
            >
              <Code2 size={16} />
              {editorOpen ? "隐藏输出" : "显示输出"}
            </button>
            <button className="primary-action" disabled={actionBusy} onClick={runTask} type="button">
              {actionBusy ? <Loader2 className="spin" size={17} /> : <SendHorizontal size={17} />}
            </button>
          </div>
        </footer>
      </section>

      <aside className="project-panel">
        <header>
          <div>
            <span className="eyebrow">工作目录</span>
            <h2>文件</h2>
          </div>
          <button onClick={chooseWorkspace} type="button" title="选择工作目录">
            <FolderOpen size={16} />
            选择
          </button>
        </header>
        <div className="workspace-path">{workspaceRoot}</div>

        <section className="file-tree" aria-label="工作目录文件">
          {projectFiles.map((file) => (
            <button
              className="file-row"
              key={file.path}
              onClick={() => openProjectFile(file)}
              style={{ paddingLeft: `${12 + file.depth * 18}px` }}
              type="button"
            >
              {file.type === "directory" ? <Folder size={14} /> : <FileCode2 size={14} />}
              <span>{file.name}</span>
              {file.type === "directory" ? <ChevronRight size={13} /> : null}
            </button>
          ))}
        </section>

        <section className="run-details">
          <h3>运行产物</h3>
          {runArtifacts.length === 0 ? (
            <button onClick={() => runCommand("status")} type="button">加载最近运行</button>
          ) : (
            runArtifacts.map((artifact) => (
              <button key={artifact.path} onClick={() => openArtifact(artifact)} type="button">
                {artifact.path}
              </button>
            ))
          )}
        </section>
      </aside>

      {settingsOpen ? (
        <section className="settings-modal" role="dialog" aria-modal="true" aria-label="设置">
          <div className="settings-window">
            <aside className="settings-menu">
              <div className="settings-menu-title">
                <Settings2 size={18} />
                <span>设置</span>
              </div>
              {settingsItems.map((item) => (
                <button
                  className={settingsTab === item.id ? "selected" : ""}
                  key={item.id}
                  onClick={() => setSettingsTab(item.id)}
                  type="button"
                >
                  <item.icon size={16} />
                  <span>{item.label}</span>
                </button>
              ))}
            </aside>
            <section className="settings-panel">
              <header>
                <div>
                  <span className="eyebrow">配置中心</span>
                  <h2>{settingsItems.find((item) => item.id === settingsTab)?.label}</h2>
                </div>
                <button className="icon-button" type="button" onClick={() => setSettingsOpen(false)} title="关闭">
                  <X size={16} />
                </button>
              </header>
              <div className="settings-panel-body">
                {settingsTab === "agents" ? (
                  <section className="settings-section">
                    <div className="section-heading">
                      <h3>选择智能体</h3>
                      <p>选中某个智能体后，模型配置页会自动显示对应 runtime 的 Profile。</p>
                    </div>
                    <div className="agent-picker">
                      {agents.map((agent) => (
                        <button
                          className={settingsAgentId === agent.id ? "selected" : ""}
                          key={agent.id}
                          onClick={() => {
                            setSettingsAgentId(agent.id);
                            setActiveAgentId(agent.id);
                            setActiveInstanceId(firstInstanceIdForAgent(agent.id, settingsState));
                            setSettingsTab(agent.runtime === "opencode" ? "runtimes" : "profiles");
                          }}
                          type="button"
                        >
                          <span className="agent-dot large" style={{ backgroundColor: agent.accent }} />
                          <span>
                            <strong>{agent.label}</strong>
                            <small>
                              {runtimeLabel(agent.runtime)} · {agentRoleSummary(agent.id, settingsState)}
                            </small>
                          </span>
                        </button>
                      ))}
                    </div>
                  </section>
                ) : null}

                {settingsTab === "roles" ? (
                  <section className="settings-section">
                    <div className="section-heading">
                      <h3>角色提示词与身份实例</h3>
                      <p>系统默认角色只读。需要调整职责时，请新增自定义角色；同一个智能体可以同时绑定多个角色。</p>
                    </div>
                    <div className="roles-layout">
                      <section className="role-editor-column">
                        <div className="role-list-header">
                          <span>角色模板</span>
                          <button
                            type="button"
                            onClick={() =>
                              setRoleForm({
                                id: "",
                                name: "",
                                prompt: "",
                                system: false
                              })
                            }
                          >
                            <Plus size={14} />
                            新建
                          </button>
                        </div>
                        <div className="role-list">
                          {roleTemplates.map((role) => (
                            <button
                              className={roleForm.id === role.id ? "selected" : ""}
                              key={role.id}
                              onClick={() => setRoleForm(role)}
                              type="button"
                            >
                              <strong>{role.name}</strong>
                              <small>{role.system ? "系统默认角色" : role.id}</small>
                            </button>
                          ))}
                        </div>
                        <div className="role-form">
                          <label className="field">
                            角色 ID
                            <input
                              disabled={Boolean(roleForm.system)}
                              placeholder="例如 qa-reviewer"
                              value={roleForm.id}
                              onChange={(event) =>
                                setRoleForm((form) => ({ ...form, id: event.target.value }))
                              }
                            />
                          </label>
                          <label className="field">
                            角色名称
                            <input
                              disabled={isSystemRoleForm}
                              placeholder="例如 QA Reviewer"
                              value={roleForm.name}
                              onChange={(event) =>
                                setRoleForm((form) => ({ ...form, name: event.target.value }))
                              }
                            />
                          </label>
                          <label className="field wide">
                            角色提示词
                            <textarea
                              readOnly={isSystemRoleForm}
                              placeholder="描述这个身份的职责、边界、输出格式和验证要求。"
                              value={roleForm.prompt}
                              onChange={(event) =>
                                setRoleForm((form) => ({ ...form, prompt: event.target.value }))
                              }
                            />
                          </label>
                          <button
                            className="primary-action compact"
                            disabled={setupBusy || isSystemRoleForm}
                            onClick={saveRoleTemplate}
                            type="button"
                            title={isSystemRoleForm ? "系统默认角色不能修改，请新建自定义角色" : "保存角色"}
                          >
                            {setupBusy ? <Loader2 className="spin" size={15} /> : <Save size={15} />}
                            {isSystemRoleForm ? "系统角色只读" : "保存角色"}
                          </button>
                          {isSystemRoleForm ? (
                            <div className="inline-hint">系统默认提示词不能修改。点击“新建”创建自定义角色提示词。</div>
                          ) : null}
                        </div>
                      </section>

                      <section className="role-assignment-column">
                        <label className="field">
                          绑定到智能体（可多选角色）
                          <select
                            value={roleAssignmentAgentId}
                            onChange={(event) => setRoleAssignmentAgentId(event.target.value)}
                          >
                            {agents.map((agent) => (
                              <option key={agent.id} value={agent.id}>
                                {agent.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <div className="assignment-hint">
                          <strong>{agentById(roleAssignmentAgentId)?.label ?? roleAssignmentAgentId}</strong>
                          <span>当前已选择 {roleAssignmentIds.length} 个角色，保存后会生成 {roleAssignmentIds.length} 个会话身份。</span>
                        </div>
                        <div className="role-checkbox-grid">
                          {roleTemplates.map((role) => (
                            <label key={role.id}>
                              <input
                                checked={roleAssignmentIds.includes(role.id)}
                                type="checkbox"
                                onChange={(event) => {
                                  setRoleAssignmentIds((current) =>
                                    event.target.checked
                                      ? Array.from(new Set([...current, role.id]))
                                      : current.filter((roleId) => roleId !== role.id)
                                  );
                                }}
                              />
                              <span>
                                <strong>{role.name}</strong>
                                <small>{role.id}</small>
                              </span>
                            </label>
                          ))}
                        </div>
                        <button
                          className="primary-action compact"
                          disabled={setupBusy}
                          onClick={saveAgentRoles}
                          type="button"
                        >
                          {setupBusy ? <Loader2 className="spin" size={15} /> : <Save size={15} />}
                          保存绑定
                        </button>
                        <div className="identity-preview">
                          <span>保存后会话可选身份</span>
                          {roleAssignmentIds.map((roleId) => (
                            <strong key={roleId}>
                              {agentById(roleAssignmentAgentId)?.label ?? roleAssignmentAgentId} ·{" "}
                              {roleTemplateMap[roleId]?.name ?? roleId}
                            </strong>
                          ))}
                        </div>
                      </section>
                    </div>
                  </section>
                ) : null}

                {settingsTab === "profiles" ? (
                  <section className="settings-section">
                    <div className="section-heading">
                      <h3>{settingsAgent.label} 的模型 Profile</h3>
                      <p>当前显示 {runtimeLabel(settingsRuntime)} 配置。Base URL 与 API Key 必须成对保存。</p>
                    </div>
                    <label className="field">
                      智能体
                      <select
                        value={settingsAgentId}
                        onChange={(event) => {
                          setSettingsAgentId(event.target.value);
                          setActiveAgentId(event.target.value);
                          setActiveInstanceId(firstInstanceIdForAgent(event.target.value, settingsState));
                        }}
                      >
                        {agents.map((agent) => (
                          <option key={agent.id} value={agent.id}>
                            {agent.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    {settingsRuntime === "opencode" ? (
                      <div className="soft-warning">OpenCode 当前使用本地认证或运行时默认认证，不需要模型 API Profile。</div>
                    ) : (
                      <>
                        <div className="profile-list">
                          {runtimeProfiles.length === 0 ? (
                            <span>尚未配置 {runtimeLabel(settingsRuntime)} Profile。</span>
                          ) : (
                            runtimeProfiles.map((profile) => (
                              <button
                                key={profile.name}
                                onClick={() =>
                                  setCredentialForm((form) => ({
                                    ...form,
                                    runtime: settingsRuntime,
                                    agentId: settingsAgent.id,
                                    profileName: profile.name,
                                    baseUrl: profile.base_url ?? "",
                                    apiKey: ""
                                  }))
                                }
                                type="button"
                              >
                                <strong>{profile.name}</strong>
                                <small>
                                  {profile.base_url} · {profile.api_key_set ? "API Key 已配置" : "API Key 未配置"}
                                </small>
                              </button>
                            ))
                          )}
                        </div>
                        <div className="settings-form-grid">
                          <label className="field">
                            Profile 名称
                            <input
                              value={credentialForm.profileName}
                              onChange={(event) =>
                                setCredentialForm((form) => ({ ...form, profileName: event.target.value }))
                              }
                            />
                          </label>
                          <label className="field">
                            模型
                            <input
                              value={credentialForm.model}
                              onChange={(event) =>
                                setCredentialForm((form) => ({ ...form, model: event.target.value }))
                              }
                            />
                          </label>
                          <label className="field wide">
                            Base URL
                            <input
                              value={credentialForm.baseUrl}
                              onChange={(event) =>
                                setCredentialForm((form) => ({ ...form, baseUrl: event.target.value }))
                              }
                            />
                          </label>
                          <label className="field wide">
                            API Key
                            <input
                              type="password"
                              autoComplete="off"
                              placeholder={
                                runtimeProfiles.find((profile) => profile.name === credentialForm.profileName.trim())
                                  ?.api_key_set
                                  ? "留空则保留已保存 Key"
                                  : "请输入 API Key"
                              }
                              value={credentialForm.apiKey}
                              onChange={(event) =>
                                setCredentialForm((form) => ({ ...form, apiKey: event.target.value }))
                              }
                            />
                          </label>
                        </div>
                        <button className="primary-action compact" disabled={setupBusy} onClick={saveProfile} type="button">
                          {setupBusy ? <Loader2 className="spin" size={15} /> : <Save size={15} />}
                          保存 Profile
                        </button>
                      </>
                    )}
                  </section>
                ) : null}

                {settingsTab === "runtimes" ? (
                  <section className="settings-section">
                    <div className="section-heading">
                      <h3>运行时</h3>
                      <p>这里检查 Codex、Claude Code、OpenCode CLI 是否已安装。</p>
                    </div>
                    <div className="runtime-checks polished">
                      {diagnostics?.installedRuntimes.map((runtime) => (
                        <div className="runtime-check" key={runtime.runtime}>
                          <span>
                            <strong>{runtimeLabel(runtime.runtime)}</strong>
                            <small>{runtime.command}</small>
                          </span>
                          {runtime.installed ? (
                            <span className="status-pill succeeded">已安装</span>
                          ) : (
                            <button disabled={setupBusy} onClick={() => installRuntime(runtime.runtime)} type="button">
                              安装
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}

                {settingsTab === "workspace" ? (
                  <section className="settings-section">
                    <div className="section-heading">
                      <h3>工作目录</h3>
                      <p>右侧文件树和 dry-run 的 --workdir 都会使用这个目录。</p>
                    </div>
                    <div className="settings-readout expanded">
                      <span>当前目录</span>
                      <strong>{workspaceRoot}</strong>
                    </div>
                    <button className="primary-action compact" onClick={chooseWorkspace} type="button">
                      <FolderCog size={15} />
                      选择工作目录
                    </button>
                  </section>
                ) : null}

                {settingsTab === "diagnostics" ? (
                  <section className="settings-section">
                    <div className="section-heading">
                      <h3>诊断</h3>
                      <p>查看配置路径并运行 madcli doctor。</p>
                    </div>
                    <div className="settings-readout expanded">
                      <span>配置文件</span>
                      <strong>{diagnostics?.configPath ?? "不可用"}</strong>
                    </div>
                    <div className="settings-readout expanded">
                      <span>项目根目录</span>
                      <strong>{diagnostics?.projectRoot ?? "不可用"}</strong>
                    </div>
                    <button className="primary-action compact" type="button" onClick={() => runCommand("doctor")}>
                      <TerminalSquare size={15} />
                      运行诊断
                    </button>
                  </section>
                ) : null}

                {settingsMessage ? <pre className="setup-message">{settingsMessage}</pre> : null}
              </div>
            </section>
          </div>
        </section>
      ) : null}

      {configPrompt ? (
        <section className="modal-backdrop" role="presentation">
          <div className="config-modal" role="dialog" aria-modal="true" aria-label="需要配置">
            <div className="modal-icon">
              <Wrench size={20} />
            </div>
            <h2>需要先完成运行配置</h2>
            <p>{readinessMessage(configPrompt.reason, activeAgent.label)}</p>
            <div className="modal-actions">
              <button type="button" onClick={() => setConfigPrompt(null)}>
                取消
              </button>
              <button
                className="primary-action"
                type="button"
                onClick={() => {
                  setConfigPrompt(null);
                  void openSettings("profiles");
                }}
              >
                打开设置
              </button>
            </div>
          </div>
        </section>
      ) : null}

      <section className={`editor-drawer ${editorOpen ? "open" : ""}`} aria-hidden={!editorOpen}>
        <header>
          <div>
            <span className="eyebrow">输出</span>
            <h2>{editorTitle}</h2>
          </div>
          <button type="button" onClick={() => setEditorOpen(false)}>
            <SplitSquareHorizontal size={16} />
            收起
          </button>
        </header>
        <pre>
          <code>{editorContent}</code>
        </pre>
      </section>
    </main>
  );
}

const settingsItems: Array<{
  id: SettingsTab;
  label: string;
  icon: typeof Bot;
}> = [
  { id: "agents", label: "智能体", icon: Bot },
  { id: "roles", label: "角色提示词", icon: Wrench },
  { id: "profiles", label: "模型 Profile", icon: KeyRound },
  { id: "runtimes", label: "运行时", icon: Server },
  { id: "workspace", label: "工作目录", icon: FolderCog },
  { id: "diagnostics", label: "诊断", icon: Activity }
];

function readinessMessage(reason: AgentRunReadiness["reason"], agentLabel: string): string {
  if (reason === "missing_model_api_config") {
    return `${agentLabel} 需要模型 API Profile。请在设置中为对应运行时成对填写 Base URL 和 API Key。`;
  }
  if (reason === "missing_runtime_install") {
    return `${agentLabel} 对应的编码运行时尚未安装。请在设置中安装运行时，或切换到已安装的智能体。`;
  }
  if (reason === "unknown_agent" || reason === "unknown_runtime") {
    return "当前智能体配置无效，请在设置中检查智能体和运行时。";
  }
  return "当前配置尚未满足运行条件，请打开设置检查。";
}

function markActiveSession(sessions: Session[], activeSessionId: string): Session[] {
  return sessions.map((session) => ({
    ...session,
    status: session.id === activeSessionId ? "active" : session.status === "failed" ? "failed" : "idle"
  }));
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "当前",
    idle: "空闲",
    failed: "失败",
    running: "运行中",
    succeeded: "成功",
    dry_run: "预演"
  };
  return labels[status] ?? status;
}

function runtimeLabel(runtime: RuntimeName): string {
  const labels: Record<RuntimeName, string> = {
    opencode: "OpenCode",
    codex: "Codex",
    claude_code: "Claude Code"
  };
  return labels[runtime];
}

function defaultRoleIdForAgent(agentId: string): string {
  if (agentId === "codex_reviewer") {
    return "reviewer";
  }
  return "worker";
}

function defaultRoleName(roleId: string): string {
  const names: Record<string, string> = {
    commander: "Commander",
    worker: "Worker",
    reviewer: "Reviewer"
  };
  return names[roleId] ?? roleId;
}

function buildFallbackAgentInstances(): AgentInstance[] {
  return agents.map((agent) => {
    const roleId = defaultRoleIdForAgent(agent.id);
    return {
      id: `${agent.id}:${roleId}`,
      agentId: agent.id,
      roleId,
      label: `${agent.label} / ${defaultRoleName(roleId)}`,
      runtime: agent.runtime,
      roleName: defaultRoleName(roleId),
      prompt: ""
    };
  });
}

function sortRoleTemplates(roles: RoleTemplate[]): RoleTemplate[] {
  const order: Record<string, number> = {
    commander: 0,
    worker: 1,
    reviewer: 2
  };
  return [...roles].sort((left, right) => {
    const leftOrder = order[left.id] ?? 100;
    const rightOrder = order[right.id] ?? 100;
    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder;
    }
    return left.name.localeCompare(right.name);
  });
}

function firstInstanceIdForAgent(agentId: string, settingsState: SettingsState | null): string {
  const instance = settingsState?.agentInstances?.find((item) => item.agentId === agentId);
  if (instance) {
    return instance.id;
  }
  return `${agentId}:${defaultRoleIdForAgent(agentId)}`;
}

function agentRoleSummary(agentId: string, settingsState: SettingsState | null): string {
  const roleTemplates = settingsState?.roleTemplates ?? {};
  const roleIds = settingsState?.agentRoles?.[agentId] ?? [defaultRoleIdForAgent(agentId)];
  const names = roleIds.map((roleId) => roleTemplates[roleId]?.name ?? defaultRoleName(roleId));
  return names.length > 0 ? names.join(" / ") : defaultRoleName(defaultRoleIdForAgent(agentId));
}

function defaultRoleForm(settingsState: SettingsState): RoleTemplate {
  return (
    settingsState.roleTemplates.reviewer ??
    settingsState.roleTemplates.worker ??
    Object.values(settingsState.roleTemplates)[0] ?? {
      id: "",
      name: "",
      prompt: "",
      system: false
    }
  );
}

function defaultBaseUrl(runtime: RuntimeName): string {
  if (runtime === "claude_code") {
    return "https://api.anthropic.com";
  }
  if (runtime === "codex") {
    return "https://api.openai.com/v1";
  }
  return "";
}
