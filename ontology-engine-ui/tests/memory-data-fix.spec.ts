import { test, expect } from "@playwright/test";

/**
 * E2E tests to verify memory data loading fix.
 * Tests that stats and activities load correctly from real backend API.
 */

const BASE_URL = "http://localhost:3004";
const SPACE_ID = "space_7cee0200";

test.describe("Memory Data Loading Fix Verification", () => {
  test("should load memory overview with stats from backend", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Check page title
    const title = page.locator("h3:has-text('记忆总览')");
    await expect(title).toBeVisible();

    // Wait for stats to load (not loading spinner)
    await page.waitForSelector(".ant-statistic", { timeout: 10000 });

    // Check that stats cards are visible
    const statsCards = page.locator(".ant-statistic");
    await expect(statsCards).toHaveCount(4);

    // Verify specific stat titles
    await expect(page.locator("text=总记忆数")).toBeVisible();
    await expect(page.locator("text=Layer-R")).toBeVisible();
    await expect(page.locator("text=Layer-S")).toBeVisible();
    await expect(page.locator("text=待审区")).toBeVisible();

    // Take screenshot for verification
    await page.screenshot({ path: "test-results/memory-overview-stats.png", fullPage: true });
  });

  test("should switch to Agent Activities tab without errors", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Click on Agent 活动 tab
    const activitiesTab = page.locator(".ant-tabs-tab:has-text('Agent 活动')");
    await expect(activitiesTab).toBeVisible();
    await activitiesTab.click();

    // Wait for tab content to load
    await page.waitForTimeout(1500);

    // Check that the tab panel is visible and not blank
    const tabPanel = page.locator(".ant-tabs-tabpane-active");
    await expect(tabPanel).toBeVisible();

    // Check for console errors - if there are any, the test should fail
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    // Wait a bit and verify no console errors occurred
    await page.waitForTimeout(1000);

    // The page should show either a list or "no data" message, not be blank
    const cardTitle = page.locator("text=最近活动");
    await expect(cardTitle).toBeVisible();

    // Take screenshot
    await page.screenshot({ path: "test-results/memory-activities-tab.png", fullPage: true });

    // Assert no console errors
    expect(consoleErrors).toHaveLength(0);
  });

  test("should display memory type distribution tags", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Check for memory type distribution card
    const typeDistribution = page.locator("text=记忆类型分布");
    await expect(typeDistribution).toBeVisible();

    // Check for belief status distribution card
    const beliefDistribution = page.locator("text=信念状态分布");
    await expect(beliefDistribution).toBeVisible();

    await page.screenshot({ path: "test-results/memory-distributions.png", fullPage: true });
  });
});
