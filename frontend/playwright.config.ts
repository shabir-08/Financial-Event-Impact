import { defineConfig } from '@playwright/test';

// End-to-end tests against BOTH running servers: backend (uvicorn :8000) and frontend (vite :5173).
// Uses the locally installed Microsoft Edge (no browser download needed).
export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
    channel: 'msedge',
    headless: true,
    viewport: { width: 1600, height: 1000 },
    acceptDownloads: true,
  },
});
