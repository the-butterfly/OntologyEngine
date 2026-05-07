import { test, expect } from "@playwright/test";

/**
 * Debug test to capture screenshots of memory navigation issues
 */

const SPACE_ID = "space_7cee0200";
const BASE_URL = "http://localhost:3000";

test.describe("Debug Memory Navigation", () => {
  test("capture screenshot of space detail page", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    
    // Take screenshot of full page
    await page.screenshot({ path: "test-results/debug-space-detail.png", fullPage: true });
    
    // Check if menu is visible
    const menu = page.locator(".ant-menu");
    console.log("Menu visible:", await menu.isVisible().catch(() => false));
    
    // Check for Agent Memory text
    const memoryText = page.locator("text=Agent Memory");
    console.log("Agent Memory visible:", await memoryText.isVisible().catch(() => false));
    
    // List all menu items
    const menuItems = await page.locator(".ant-menu-item, .ant-menu-submenu-title").allTextContents();
    console.log("Menu items:", menuItems);
  });

  test("capture screenshot of memory page directly", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    
    await page.screenshot({ path: "test-results/debug-memory-page.png", fullPage: true });
    
    // Check page title
    const title = page.locator("h3").first();
    console.log("Page title:", await title.textContent().catch(() => "not found"));
    
    // Check for console errors
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });
    
    await page.waitForTimeout(1000);
    console.log("Console errors:", consoleErrors);
  });

  test("test navigation from space detail to memory", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    
    // Try to find and click Agent Memory menu
    const memoryMenu = page.locator("text=Agent Memory").first();
    
    if (await memoryMenu.isVisible().catch(() => false)) {
      await memoryMenu.click();
      await page.waitForTimeout(1000);
      
      // Try to click 记忆总览
      const overview = page.locator("text=记忆总览").first();
      if (await overview.isVisible().catch(() => false)) {
        await overview.click();
        await page.waitForTimeout(2000);
        
        await page.screenshot({ path: "test-results/debug-after-nav.png", fullPage: true });
        console.log("Current URL:", page.url());
      }
    }
  });
});
