export type RuntimeName = "opencode" | "codex" | "claude_code";

export type Agent = {
  id: string;
  label: string;
  role: string;
  runtime: RuntimeName;
  model: string;
  activeModel: string;
  activeCredential: string;
  accent: string;
};

export type CredentialProfile = {
  id: string;
  runtime: RuntimeName;
  label: string;
  baseUrl: string;
  keySource: string;
};

export type Session = {
  id: string;
  title: string;
  agentId: string;
  status: "active" | "idle" | "failed";
  updatedAt: string;
  messageCount?: number;
};

export type Message = {
  id: string;
  role: "user" | "agent" | "system" | "event";
  content: string;
  agentId?: string;
  runtime?: RuntimeName;
  runId?: string;
  status?: "running" | "succeeded" | "failed" | "dry_run";
};

export type ProjectFile = {
  path: string;
  name: string;
  type: "directory" | "file";
  depth: number;
};

export type InstalledRuntime = {
  runtime: RuntimeName;
  command: string;
  installed: boolean;
};

export type StartupDiagnostics = {
  configPath: string;
  projectRoot: string;
  workspaceRoot: string;
  needsModelApiConfig: boolean;
  needsRuntimeInstall: boolean;
  installedRuntimes: InstalledRuntime[];
  messages: string[];
};

export type CredentialSavePayload = {
  runtime: RuntimeName;
  agentId: string;
  profileName: string;
  baseUrl: string;
  apiKey: string;
  model: string;
};

export type RuntimeInstallResult = {
  ok: boolean;
  cancelled: boolean;
  code?: number | null;
  stdout: string;
  stderr: string;
};

export type SessionDetail = Session & {
  messages: Message[];
};

export type ProjectFileContent = {
  path: string;
  content: string;
};

export type CommandResult = {
  ok: boolean;
  code: number | null;
  stdout: string;
  stderr: string;
  title?: string;
  runId?: string;
};

export type Artifact = {
  path: string;
  name: string;
};

export type CreateSessionPayload = {
  title: string;
  activeAgent: string;
};

export type RunDryRunPayload = {
  sessionId: string;
  task: string;
  agent: string;
  roleId?: string;
};

export type RunTaskPayload = RunDryRunPayload;

export type RoleTemplate = {
  id: string;
  name: string;
  prompt: string;
  system?: boolean;
};

export type AgentInstance = {
  id: string;
  agentId: string;
  roleId: string;
  label: string;
  runtime: RuntimeName;
  roleName: string;
  prompt: string;
};

export type AgentRunReadiness = {
  ok: boolean;
  reason:
    | ""
    | "unknown_agent"
    | "unknown_runtime"
    | "missing_runtime_install"
    | "missing_model_api_config";
};

export type SettingsState = {
  configPath: string;
  projectRoot: string;
  workspaceRoot: string;
  config: unknown;
  agents: Record<
    string,
    {
      runtime: RuntimeName;
      agent: string;
      model?: string | null;
      description?: string;
      active_model?: string | null;
      active_credential?: string | null;
    }
  >;
  credentialsByRuntime: Record<
    RuntimeName,
    Array<{
      name: string;
      base_url?: string;
      api_key_env?: string;
      api_key_set?: boolean;
    }>
  >;
  roleTemplates: Record<string, RoleTemplate>;
  agentRoles: Record<string, string[]>;
  agentInstances: AgentInstance[];
  diagnostics: StartupDiagnostics;
};

declare global {
  interface Window {
    madcliDesktop?: {
      version: string;
      getStartupDiagnostics: () => Promise<StartupDiagnostics>;
      saveCredentialProfile: (
        payload: CredentialSavePayload
      ) => Promise<StartupDiagnostics>;
      installRuntime: (runtimeName: RuntimeName) => Promise<RuntimeInstallResult>;
      listSessions: () => Promise<Session[]>;
      createSession: (payload: CreateSessionPayload) => Promise<Session>;
      loadSession: (sessionId: string) => Promise<SessionDetail>;
      deleteSession: (sessionId: string) => Promise<Session[]>;
      listProjectFiles: () => Promise<ProjectFile[]>;
      readProjectFile: (relativePath: string) => Promise<ProjectFileContent>;
      chooseWorkspace: () => Promise<StartupDiagnostics>;
      getSettingsState: () => Promise<SettingsState>;
      saveRoleTemplate: (payload: RoleTemplate) => Promise<SettingsState>;
      saveAgentRoles: (payload: {
        agentId: string;
        roleIds: string[];
      }) => Promise<SettingsState>;
      canRunAgent: (agentId: string) => Promise<AgentRunReadiness>;
      runDoctor: () => Promise<CommandResult>;
      runStatus: () => Promise<CommandResult>;
      runTask: (payload: RunTaskPayload) => Promise<CommandResult>;
      runDryRun: (payload: RunDryRunPayload) => Promise<CommandResult>;
      listArtifacts: (runId: string) => Promise<Artifact[]>;
      readArtifact: (payload: {
        runId: string;
        artifactPath: string;
      }) => Promise<ProjectFileContent>;
    };
  }
}
