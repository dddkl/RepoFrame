import { defineConfig } from "@playwright/test";
import path from "node:path";
import { mkdirSync } from "node:fs";

// Keep browser profiles and temporary files alongside this project by default.
const temporary = process.env.TEMP || path.resolve(".tmp/browser-runtime");
mkdirSync(temporary, { recursive: true });
process.env.TEMP = temporary;
process.env.TMP = temporary;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 45000,
  workers: 1,
  fullyParallel: false,
  use: {
    browserName: "chromium",
    viewport: { width: 1440, height: 1080 },
    locale: "zh-CN",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  reporter: "list",
  outputDir: "test-results",
});
