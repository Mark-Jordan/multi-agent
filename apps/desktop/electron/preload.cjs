const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("madcliDesktop", {
  version: "0.1.0",
  getStartupDiagnostics: () => ipcRenderer.invoke("diagnostics:startup"),
  saveCredentialProfile: (payload) =>
    ipcRenderer.invoke("config:saveCredential", payload),
  installRuntime: (runtimeName) => ipcRenderer.invoke("runtime:install", runtimeName),
  listSessions: () => ipcRenderer.invoke("sessions:list"),
  createSession: (payload) => ipcRenderer.invoke("sessions:create", payload),
  loadSession: (sessionId) => ipcRenderer.invoke("sessions:load", sessionId),
  deleteSession: (sessionId) => ipcRenderer.invoke("sessions:delete", sessionId),
  listProjectFiles: () => ipcRenderer.invoke("project:listFiles"),
  readProjectFile: (relativePath) => ipcRenderer.invoke("project:readFile", relativePath),
  chooseWorkspace: () => ipcRenderer.invoke("workspace:choose"),
  getSettingsState: () => ipcRenderer.invoke("settings:get"),
  saveRoleTemplate: (payload) => ipcRenderer.invoke("roles:saveTemplate", payload),
  saveAgentRoles: (payload) => ipcRenderer.invoke("roles:saveAgentRoles", payload),
  canRunAgent: (agentId) => ipcRenderer.invoke("agents:canRun", agentId),
  runDoctor: () => ipcRenderer.invoke("madcli:doctor"),
  runStatus: () => ipcRenderer.invoke("madcli:status"),
  runTask: (payload) => ipcRenderer.invoke("madcli:runTask", payload),
  runDryRun: (payload) => ipcRenderer.invoke("madcli:runDryRun", payload),
  runWorkflow: (payload) => ipcRenderer.invoke("madcli:runWorkflow", payload),
  listArtifacts: (runId) => ipcRenderer.invoke("artifacts:list", runId),
  readArtifact: (payload) => ipcRenderer.invoke("artifacts:read", payload)
});
