"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const path = __importStar(require("path"));
const child_process_1 = require("child_process");
let mainWindow = null;
let pythonProcess = null;
const PORT = 18923;
const PROJECT_ROOT = path.resolve(__dirname, "../../..");
function spawnPython() {
    return new Promise((resolve, reject) => {
        pythonProcess = (0, child_process_1.spawn)("python", ["-m", "uvicorn", "src.api:app", "--host", "127.0.0.1", "--port", String(PORT)], { cwd: PROJECT_ROOT, stdio: ["ignore", "pipe", "pipe"] });
        let started = false;
        pythonProcess.stdout?.on("data", (data) => {
            const msg = data.toString();
            if (msg.includes("Uvicorn running") && !started) {
                started = true;
                resolve();
            }
        });
        pythonProcess.stderr?.on("data", (data) => {
            const msg = data.toString();
            if (msg.includes("Uvicorn running") && !started) {
                started = true;
                resolve();
            }
        });
        pythonProcess.on("error", (err) => {
            if (!started)
                reject(err);
        });
        pythonProcess.on("exit", (code) => {
            if (!started)
                reject(new Error(`Python exited with code ${code}`));
        });
    });
}
function createWindow() {
    mainWindow = new electron_1.BrowserWindow({
        width: 1100,
        height: 750,
        title: "DCEMapping",
        webPreferences: {
            preload: path.join(__dirname, "../preload/preload.js"),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });
    if (process.env.VITE_DEV_SERVER_URL) {
        mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
    }
    else {
        mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
    }
    mainWindow.on("closed", () => {
        mainWindow = null;
    });
}
electron_1.ipcMain.handle("select-directory", async () => {
    const result = await electron_1.dialog.showOpenDialog({
        properties: ["openDirectory"],
    });
    if (result.canceled)
        return null;
    return result.filePaths[0];
});
electron_1.ipcMain.handle("select-file", async () => {
    const result = await electron_1.dialog.showOpenDialog({
        properties: ["openFile"],
        filters: [{ name: "NIfTI", extensions: ["nii", "nii.gz"] }],
    });
    if (result.canceled)
        return null;
    return result.filePaths[0];
});
electron_1.app.whenReady().then(async () => {
    try {
        await spawnPython();
        createWindow();
    }
    catch (err) {
        console.error("Failed to start Python backend:", err);
        electron_1.app.quit();
    }
});
electron_1.app.on("window-all-closed", () => {
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
    }
    electron_1.app.quit();
});
electron_1.app.on("activate", () => {
    if (electron_1.BrowserWindow.getAllWindows().length === 0)
        createWindow();
});
