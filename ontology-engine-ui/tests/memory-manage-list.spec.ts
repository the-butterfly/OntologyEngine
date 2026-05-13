import { test, expect } from "@playwright/test";

const SPACE_ID = "space_7cee0200";
const BASE_URL = "http://localhost:3000";

test.describe("Memory Manage Page - List spread error", () => {
  test("manage page should render without List spread error", async ({ page }) => {
    const spreadErrors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (text.includes("spread non-iterable") || text.includes("toConsumableArray")) {
          spreadErrors.push(text);
        }
      }
    });

    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory/manage`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(5000);

    expect(spreadErrors).toEqual([]);
  });

  test("manage page should display governance dashboard", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory/manage`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const dashboard = page.locator('text=治理仪表盘');
    await expect(dashboard).toBeVisible({ timeout: 10000 });

    const contradictionBoard = page.locator('text=矛盾看板');
    await expect(contradictionBoard).toBeVisible({ timeout: 10000 });

    const correctionHistory = page.locator('text=更正历史');
    await expect(correctionHistory).toBeVisible({ timeout: 10000 });
  });
});
