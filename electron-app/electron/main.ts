import { app, BrowserWindow, ipcMain, dialog } from "electron";
import * as path from "path";
import { spawn, ChildProcess } from "child_process";

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;

const PORT = 18923;
const PROJECT_ROOT = path.resolve(__dirname, "../../..");

function spawnPython(): Promise<void> {
  return new Promise((resolve, reject) => {
    pythonProcess = spawn(
      "python",
      ["-m", "uvicorn", "src.api:app", "--host", "127.0.0.1", "--port", String(PORT)],
      { cwd: PROJECT_ROOT, stdio: ["ignore", "pipe", "pipe"] }
    );

    let started = false;
    pythonProcess.stdout?.on("data", (data: Buffer) => {
      const msg = data.toString();
      if (msg.includes("Uvicorn running") && !started) {
        started = true;
        resolve();
      }
    });

    pythonProcess.stderr?.on("data", (data: Buffer) => {
      const msg = data.toString();
      if (msg.includes("Uvicorn running") && !started) {
        started = true;
        resolve();
      }
    });

    pythonProcess.on("error", (err) => {
      if (!started) reject(err);
    });

    pythonProcess.on("exit", (code) => {
      if (!started) reject(new Error(`Python exited with code ${code}`));
    });
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
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
  } else {
    mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

ipcMain.handle("select-directory", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory"],
  });
  if (result.canceled) return null;
  return result.filePaths[0];
});

ipcMain.handle("select-file", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openFile"],
    filters: [{ name: "NIfTI", extensions: ["nii", "nii.gz"] }],
  });
  if (result.canceled) return null;
  return result.filePaths[0];
});

app.whenReady().then(async () => {
  try {
    await spawnPython();
    createWindow();
  } catch (err) {
    console.error("Failed to start Python backend:", err);
    app.quit();
  }
});

app.on("window-all-closed", () => {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
  app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
