import { defineConfig, devices } from "@playwright/test";

/**
 * E2E runs entirely on deterministic fixtures and offline: the backend uses
 * MODEL_PROVIDER=none (no API key, no model), embeddings off (FTS-only — no
 * ~300MB fastembed/HF download at seed/startup), and auto-discovery off (the
 * "abstains" test must stay INSUFFICIENT_EVIDENCE, not NEEDS_SOURCES). Seeded
 * before the run. Playwright boots both the backend and the frontend.
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
        "cd ../backend && rm -f e2e.db && DATABASE_URL=sqlite+aiosqlite:///./e2e.db RETRIEVAL_USE_EMBEDDINGS=false .venv/bin/python -m app.cli seed && DATABASE_URL=sqlite+aiosqlite:///./e2e.db AUTO_DISCOVERY_ENABLED=false RETRIEVAL_USE_EMBEDDINGS=false .venv/bin/uvicorn app.main:app --port 8000",
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
