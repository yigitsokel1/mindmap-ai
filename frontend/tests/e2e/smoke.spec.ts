import { expect, test } from "@playwright/test";

const backendBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const smokeDocumentId = process.env.SMOKE_DOCUMENT_ID || "";

async function isBackendReachable(endpoint = "/api/graph/semantic"): Promise<boolean> {
  const probe = await fetch(`${backendBase}${endpoint}`).catch(() => null);
  return Boolean(probe && probe.ok);
}

test.beforeAll(async () => {
  const reachable = await isBackendReachable();
  if (!reachable) {
    throw new Error(`Smoke tests require a running backend at ${backendBase}`);
  }
});

test("@smoke query submit shows answer and evidence", async ({ page }) => {
  await page.goto("/");
  if (smokeDocumentId) {
    await page.evaluate((docId) => localStorage.setItem("selectedDocumentId", docId), smokeDocumentId);
    await page.reload();
  }
  await page.getByTestId("query-input").fill("How is Transformer grounded in this paper?");
  await page.getByTestId("query-send").click();
  await expect(page.getByText("Answer", { exact: true })).toBeVisible();
  await expect(page.getByText(/^Source$/i)).toBeVisible();
  await expect(page.getByText(/^Details$/i)).toBeVisible();
});

test("@smoke node inspect shows summary and canonical panel", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("query-input").fill("Which entities are related to Transformer in this document?");
  await page.getByTestId("query-send").click();
  const inspectButton = page.locator("[data-testid^='inspect-entity-']").first();
  await expect(inspectButton).toBeVisible();
  await inspectButton.click();
  await expect(page.getByText(/Derived semantic node \(not directly from document\)/i)).toBeVisible();
});

test("@smoke citation click opens provenance panel", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("query-input").fill("Which citations support the transformer method?");
  await page.getByTestId("query-send").click();
  await page.getByText(/^Details$/i).click();
  await page.getByText(/^Citations$/i).click();
  const citationItem = page.locator("[data-testid^='citation-item-']").first();
  const noCitationState = page.getByText(/No citation links were returned/i);
  await expect(citationItem.or(noCitationState)).toBeVisible();
  if (await citationItem.isVisible()) {
    await citationItem.click();
    await expect(page.locator("iframe").first()).toBeVisible();
  } else {
    await expect(noCitationState).toBeVisible();
  }
});
