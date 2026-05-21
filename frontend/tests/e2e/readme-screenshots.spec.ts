import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import readmeQueryResponse from "./fixtures/readme-query-response.json";

const assetsDir = path.resolve(__dirname, "../../../docs/assets");
const smokeDocumentId = process.env.SMOKE_DOCUMENT_ID || "doc-transformer";
const liveDemoBase = process.env.PLAYWRIGHT_LIVE_DEMO_URL || "https://mindmap-ai.osmanyigitsokel.com";

test.describe.configure({ mode: "serial" });

test("capture graph view screenshot from live demo", async ({ browser }) => {
  test.skip(Boolean(process.env.SKIP_LIVE_GRAPH_SCREENSHOT), "Live demo graph capture skipped");
  const graphPath = path.join(assetsDir, "mindmap-graph-view.png");
  if (fs.existsSync(graphPath) && !process.env.FORCE_README_SCREENSHOTS) {
    return;
  }

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    baseURL: liveDemoBase,
  });
  const page = await context.newPage();
  await page.goto("/");
  await page.evaluate((docId) => {
    localStorage.setItem("selectedDocumentId", docId);
  }, smokeDocumentId);
  await page.reload();
  await page.waitForTimeout(5000);
  await page.screenshot({ path: graphPath, fullPage: false });
  await context.close();
});

test("capture query evidence screenshot with mocked semantic response", async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.route("**/api/query/semantic", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(readmeQueryResponse),
    });
  });

  await page.goto("/");
  await page.evaluate((docId) => {
    localStorage.setItem("selectedDocumentId", docId);
  }, smokeDocumentId);
  await page.reload();

  await page.getByTestId("query-input").fill("How is Transformer grounded in this paper?");
  await page.getByTestId("query-send").click();
  await expect(page.getByText("Answer", { exact: true })).toBeVisible();
  await expect(page.getByText(/^Source$/i)).toBeVisible();
  await page.getByText(/^Details$/i).click();
  await page.getByText(/^Citations$/i).click();
  await expect(page.getByTestId("citation-item-0")).toBeVisible();
  await page.waitForTimeout(800);

  await page.screenshot({
    path: path.join(assetsDir, "mindmap-query-evidence.png"),
    fullPage: false,
  });
});
