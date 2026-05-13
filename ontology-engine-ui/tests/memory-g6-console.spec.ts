import { test, expect } from "@playwright/test";

const SPACE_ID = "space_7cee0200";
const BASE_URL = "http://localhost:3000";

test.describe("Memory Page - G6 Graph & Detail Drawer", () => {
  test("memory overview page should not have G6 destroyed/draw errors", async ({ page }) => {
    const g6Errors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (
          text.includes("graph instance has been destroyed") ||
          text.includes("Cannot read properties of undefined (reading 'draw')")
        ) {
          g6Errors.push(text);
        }
      }
    });

    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(5000);

    expect(g6Errors).toEqual([]);
  });

  test("clicking memory node should open detail drawer without G6 errors", async ({ page }) => {
    const g6Errors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (
          text.includes("graph instance has been destroyed") ||
          text.includes("Cannot read properties of undefined (reading 'draw')")
        ) {
          g6Errors.push(text);
        }
      }
    });

    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const viewButtons = page.locator('button:has-text("查看")');
    const count = await viewButtons.count();

    if (count > 0) {
      await viewButtons.first().click();
      await page.waitForTimeout(2000);

      const drawer = page.locator('.ant-drawer-open');
      await expect(drawer).toBeVisible({ timeout: 5000 });

      const drawerClose = page.locator('.ant-drawer-close');
      await drawerClose.click();
      await page.waitForTimeout(1000);
    }

    expect(g6Errors).toEqual([]);
  });

  test("switching tabs should not cause G6 errors", async ({ page }) => {
    const g6Errors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (
          text.includes("graph instance has been destroyed") ||
          text.includes("Cannot read properties of undefined (reading 'draw')")
        ) {
          g6Errors.push(text);
        }
      }
    });

    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const activitiesTab = page.locator('.ant-tabs-tab:has-text("Agent 活动")');
    if (await activitiesTab.isVisible()) {
      await activitiesTab.click();
      await page.waitForTimeout(2000);
    }

    const overviewTab = page.locator('.ant-tabs-tab:has-text("记忆图谱")');
    if (await overviewTab.isVisible()) {
      await overviewTab.click();
      await page.waitForTimeout(3000);
    }

    expect(g6Errors).toEqual([]);
  });

  test("navigating away and back should not cause G6 errors", async ({ page }) => {
    const g6Errors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (
          text.includes("graph instance has been destroyed") ||
          text.includes("Cannot read properties of undefined (reading 'draw')")
        ) {
          g6Errors.push(text);
        }
      }
    });

    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory/manage`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    expect(g6Errors).toEqual([]);
  });
});
