const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("madcliDesktop", {
  version: "0.1.0",
  getStartupDiagnostics: () => ipcRenderer.invoke("diagnostics:startup"),
  saveCredentialProfile: (payload) =>
    ipcRenderer.invoke("config:saveCredential", payload),
  installRuntime: (runtimeName) => ipcRenderer.invoke("runtime:install", runtimeName)
});
