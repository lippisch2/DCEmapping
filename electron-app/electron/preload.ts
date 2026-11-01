import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("dcemapping", {
  selectDirectory: () => ipcRenderer.invoke("select-directory"),
  selectFile: () => ipcRenderer.invoke("select-file"),
});
