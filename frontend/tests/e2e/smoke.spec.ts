import { expect, test } from "@playwright/test";

const backendBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function isBackendReachable(endpoint = "/api/graph/semantic"): Promise<boolean> {
  const probe = await fetch(`${backendBase}${endpoint}`).catch(() => null);
  return Boolean(probe && probe.ok);
}

test("query submit shows answer and evidence", async ({ page }) => {
  if (!(await isBackendReachable())) {
    test.skip(true, `Backend is not reachable at ${backendBase}`);
  }
  await page.goto("/");
  await page.getByTestId("query-input").fill("What methods are used in this paper?");
  await page.getByTestId("query-send").click();
  await expect(page.getByText(/Answer · confidence/i)).toBeVisible();
  await expect(page.getByTestId("top-evidence-heading")).toBeVisible();
});

test("node inspect shows summary and grouped relations", async ({ page }) => {
  if (!(await isBackendReachable())) {
    test.skip(true, `Backend is not reachable at ${backendBase}`);
  }
  await page.goto("/");
  await page.getByTestId("query-input").fill("Which entities are related in this document?");
  await page.getByTestId("query-send").click();
  const inspectButton = page.locator("[data-testid^='inspect-entity-']").first();
  await expect(inspectButton).toBeVisible();
  await inspectButton.click();
  await expect(page.getByText(/Node Details/i)).toBeVisible();
  await expect(
    page
      .locator('[data-testid="incoming-relations-heading"], [data-testid="outgoing-relations-heading"]')
      .first()
  ).toBeVisible();
});

test("citation click opens provenance panel", async ({ page }) => {
  if (!(await isBackendReachable())) {
    test.skip(true, `Backend is not reachable at ${backendBase}`);
  }
  await page.goto("/");
  await page.getByTestId("query-input").fill("Which citations support this method?");
  await page.getByTestId("query-send").click();
  const citationItem = page.locator("[data-testid^='citation-item-']").first();
  await expect(citationItem).toBeVisible();
  await citationItem.click();
  await expect(page.getByTestId("inspector-context-label")).toHaveText("Citation");
  await expect(page.getByText(/Node Details/i)).toBeVisible();
});
