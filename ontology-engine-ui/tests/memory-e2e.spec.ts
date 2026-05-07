import { test, expect } from "@playwright/test";

/**
 * E2E tests for Agent Memory pages with real backend API.
 *
 * Prerequisites:
 * - Backend server running on localhost:8000
 * - Frontend dev server running on localhost:3000
 */

const SPACE_ID = "test-space";
const BASE_URL = "http://localhost:3000";

// Helper to navigate to a memory page and wait for it to load
async function navigateToMemoryPage(page: any, path: string) {
  await page.goto(`${BASE_URL}/spaces/${SPACE_ID}${path}`);
  // Wait for the page to finish loading (either content or error)
  await page.waitForLoadState("networkidle");
  // Wait a bit more for React to render
  await page.waitForTimeout(1000);
}

test.describe("Agent Memory - Real API Integration", () => {
  test.describe("Navigation", () => {
    test("should display Agent Memory navigation group", async ({ page }) => {
      await navigateToMemoryPage(page, "/memory");
      
      // Look for Agent Memory text in the menu - it should be visible in the sidebar
      const memoryNav = page.locator("text=Agent Memory");
      await expect(memoryNav).toBeVisible();
    });

    test("should navigate to all 5 memory pages", async ({ page }) => {
      const pages = [
        { label: "记忆总览", path: "/memory" },
        { label: "记忆构建", path: "/memory/build" },
        { label: "记忆管理", path: "/memory/manage" },
        { label: "记忆消费", path: "/memory/consume" },
        { label: "反思中心", path: "/memory/reflect" },
      ];

      for (const { path } of pages) {
        await navigateToMemoryPage(page, path);
        // Check URL matches
        await expect(page).toHaveURL(new RegExp(path.replace(/\/$/, "") + "$"));
        // Check page title is visible
        const title = page.locator("h3").first();
        await expect(title).toBeVisible();
      }
    });
  });

  test.describe("Memory Overview Page", () => {
    test.beforeEach(async ({ page }) => {
      await navigateToMemoryPage(page, "/memory");
    });

    test("should display page title", async ({ page }) => {
      const title = page.locator("h3:has-text('记忆总览')");
      await expect(title).toBeVisible();
    });

    test("should display tabs", async ({ page }) => {
      // Look for tab elements
      const tabs = page.locator(".ant-tabs-tab");
      await expect(tabs.first()).toBeVisible();
    });

    test("should display stats cards or loading state", async ({ page }) => {
      // Either stats are loaded or loading spinner is shown
      const statsCard = page.locator("text=总记忆数");
      const loading = page.locator(".ant-spin");
      await expect(statsCard.or(loading)).toBeVisible();
    });
  });

  test.describe("Memory Build Page", () => {
    test.beforeEach(async ({ page }) => {
      await navigateToMemoryPage(page, "/memory/build");
    });

    test("should display build page title", async ({ page }) => {
      const title = page.locator("h3:has-text('记忆构建')");
      await expect(title).toBeVisible();
    });

    test("should display form elements", async ({ page }) => {
      // Look for form inputs
      const textarea = page.locator("textarea").first();
      await expect(textarea).toBeVisible();
    });
  });

  test.describe("Memory Manage Page", () => {
    test.beforeEach(async ({ page }) => {
      await navigateToMemoryPage(page, "/memory/manage");
    });

    test("should display manage page title", async ({ page }) => {
      const title = page.locator("h3:has-text('记忆管理')");
      await expect(title).toBeVisible();
    });

    test("should display action buttons", async ({ page }) => {
      const buttons = page.locator("button");
      await expect(buttons.first()).toBeVisible();
    });
  });

  test.describe("Memory Consume Page", () => {
    test.beforeEach(async ({ page }) => {
      await navigateToMemoryPage(page, "/memory/consume");
    });

    test("should display consume page title", async ({ page }) => {
      const title = page.locator("h3:has-text('记忆消费')");
      await expect(title).toBeVisible();
    });

    test("should display search input", async ({ page }) => {
      const input = page.locator("input").first();
      await expect(input).toBeVisible();
    });
  });

  test.describe("Reflect Center Page", () => {
    test.beforeEach(async ({ page }) => {
      await navigateToMemoryPage(page, "/memory/reflect");
    });

    test("should display reflect page title", async ({ page }) => {
      const title = page.locator("h3:has-text('反思中心')");
      await expect(title).toBeVisible();
    });

    test("should display reflect form", async ({ page }) => {
      const textarea = page.locator("textarea").first();
      await expect(textarea).toBeVisible();
    });
  });

  test.describe("API Integration", () => {
    test("should render memory overview with stats cards", async ({ page }) => {
      await navigateToMemoryPage(page, "/memory");
      
      // Page should show the stats cards
      const statsCards = page.locator(".ant-statistic");
      await expect(statsCards.first()).toBeVisible();
      
      // Should show 4 stat cards (总记忆数, Layer-R, Layer-S, 待审区)
      await expect(statsCards).toHaveCount(4);
    });
  });
});
