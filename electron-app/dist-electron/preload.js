"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
electron_1.contextBridge.exposeInMainWorld("dcemapping", {
    selectDirectory: () => electron_1.ipcRenderer.invoke("select-directory"),
    selectFile: () => electron_1.ipcRenderer.invoke("select-file"),
});
