import { defineConfig, devices } from "@playwright/test";

/**
 * E2E runs entirely on deterministic fixtures: the backend uses MODEL_PROVIDER=none
 * (no API key, no model), auto-discovery is off (no network — the "abstains" test
 * must stay INSUFFICIENT_EVIDENCE, not NEEDS_SOURCES), and it is seeded before the
 * run. Playwright boots both the backend and the frontend.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "list" : "html",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "cd ../backend && rm -f e2e.db && DATABASE_URL=sqlite+aiosqlite:///./e2e.db .venv/bin/python -m app.cli seed && DATABASE_URL=sqlite+aiosqlite:///./e2e.db AUTO_DISCOVERY_ENABLED=false .venv/bin/uvicorn app.main:app --port 8000",
      url: "http://localhost:8000/api/v1/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
