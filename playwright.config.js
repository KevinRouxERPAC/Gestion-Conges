// @ts-check
const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5000",
    trace: "on-first-retry",
  },
  webServer: {
    command: "python run_wsgi.py",
    env: {
      // Config minimale pour permettre au serveur de démarrer en E2E.
      // (Config.py refuse de démarrer si SECRET_KEY est vide.)
      SECRET_KEY: "e2e-dev-secret-key",
      MAIL_SUPPRESS_SEND: "true",
    },
    url: "http://127.0.0.1:5000/login",
    reuseExistingServer: true,
    timeout: 120_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
