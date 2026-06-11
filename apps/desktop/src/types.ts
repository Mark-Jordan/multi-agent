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
};

export type Message = {
  id: string;
  role: "user" | "agent" | "system" | "event";
  content: string;
  agentId?: string;
  runtime?: RuntimeName;
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
  apiKeyEnv: string;
  model: string;
};

export type RuntimeInstallResult = {
  ok: boolean;
  cancelled: boolean;
  code?: number | null;
  stdout: string;
  stderr: string;
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
    };
  }
}
