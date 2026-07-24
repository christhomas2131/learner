// Electron desktop shell for Learner.
// Spawns the local backend (uvicorn) + frontend (next dev), waits for them to be
// ready, and opens the app in a native window. On quit, the child servers are
// killed. This is a dev-mode desktop wrapper — packaging into a signed,
// self-contained .app (PyInstaller for the backend + electron-builder) is a
// documented next step, not done here.

const { app, BrowserWindow, shell } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const BACKEND = path.join(ROOT, "backend");
const FRONTEND = path.join(ROOT, "frontend");
const FRONTEND_URL = "http://localhost:3000";
const BACKEND_HEALTH = "http://localhost:8000/api/v1/health";

let procs = [];

function startServers() {
  const uvicorn = path.join(BACKEND, ".venv", "bin", "uvicorn");
  const backend = spawn(uvicorn, ["app.main:app", "--port", "8000"], {
    cwd: BACKEND,
    stdio: "inherit",
  });
  const frontend = spawn("npm", ["run", "dev"], {
    cwd: FRONTEND,
    stdio: "inherit",
    env: { ...process.env, NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000" },
  });
  procs = [backend, frontend];
}

function waitFor(url, done, tries = 90) {
  const req = http.get(url, () => done());
  req.on("error", () => {
    if (tries <= 0) return done();
    setTimeout(() => waitFor(url, done, tries - 1), 1000);
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1320,
    height: 880,
    title: "Learner",
    backgroundColor: "#ffffff",
    webPreferences: { contextIsolation: true },
  });
  // Open external links in the system browser, not inside the app.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  waitFor(BACKEND_HEALTH, () => waitFor(FRONTEND_URL, () => win.loadURL(FRONTEND_URL)));
}

function killServers() {
  for (const p of procs) {
    try {
      p.kill();
    } catch {
      /* already gone */
    }
  }
  procs = [];
}

app.whenReady().then(() => {
  startServers();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  killServers();
  app.quit();
});
app.on("quit", killServers);
