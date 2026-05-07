import { test, expect } from "@playwright/test";

/**
 * Debug test to capture console errors on memory pages
 */

const SPACE_ID = "space_7cee0200";
const BASE_URL = "http://localhost:3000";

test.describe("Debug Console Errors", () => {
  test("capture console errors on memory overview", async ({ page }) => {
    const consoleErrors: string[] = [];
    const networkErrors: string[] = [];
    
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
        console.log("CONSOLE ERROR:", msg.text());
      }
    });
    
    page.on("response", (resp) => {
      if (resp.status() >= 400) {
        networkErrors.push(`${resp.url()}: ${resp.status()}`);
        console.log("NETWORK ERROR:", resp.url(), resp.status());
      }
    });
    
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);
    
    console.log("=== Console Errors ===", consoleErrors);
    console.log("=== Network Errors ===", networkErrors);
    
    // Take screenshot
    await page.screenshot({ path: "test-results/debug-console-errors.png", fullPage: true });
    
    // The page should still render even with API errors
    const title = page.locator("h3:has-text('记忆总览')");
    await expect(title).toBeVisible();
  });

  test("check all memory pages for errors", async ({ page }) => {
    const pages = [
      "/memory",
      "/memory/build",
      "/memory/manage",
      "/memory/consume",
      "/memory/reflect",
    ];
    
    for (const path of pages) {
      const consoleErrors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") {
          consoleErrors.push(msg.text());
        }
      });
      
      await page.goto(`${BASE_URL}/spaces/${SPACE_ID}${path}`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);
      
      console.log(`Page ${path} errors:`, consoleErrors);
      
      // Clear listeners for next iteration
      page.removeAllListeners("console");
    }
  });
});
