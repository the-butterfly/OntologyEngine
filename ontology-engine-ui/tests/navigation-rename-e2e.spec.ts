import { test, expect } from "@playwright/test";

const BASE_URL = "http://localhost:3003";

test.describe("Navigation Rename Verification", () => {
  test("顶部导航显示 知识管理 / 记忆空间 / 知识消费", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    // Verify navigation labels
    await expect(page.locator(".ant-menu-item:has-text('知识管理')")).toBeVisible();
    await expect(page.locator(".ant-menu-item:has-text('记忆空间')")).toBeVisible();
    await expect(page.locator(".ant-menu-item:has-text('知识消费')")).toBeVisible();

    // Verify old labels are gone
    await expect(page.locator("text=管理面")).toHaveCount(0);
    await expect(page.locator("text=消费面")).toHaveCount(0);

    await page.screenshot({ path: "test-results/nav-rename.png", fullPage: false });
  });

  test("点击 知识管理 跳转空间列表", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces`);
    await page.waitForLoadState("networkidle");

    await page.locator(".ant-menu-item:has-text('知识管理')").click();
    await page.waitForURL("**/spaces");
    await expect(page.locator("text=语义空间")).toBeVisible();
  });

  test("点击 记忆空间 跳转记忆总览", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces`);
    await page.waitForLoadState("networkidle");

    await page.locator(".ant-menu-item:has-text('记忆空间')").click();
    await page.waitForURL("**/memory");
    await expect(page.locator("text=记忆总览")).toBeVisible();
  });

  test("点击 知识消费 跳转消费列表", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces`);
    await page.waitForLoadState("networkidle");

    await page.locator(".ant-menu-item:has-text('知识消费')").click();
    await page.waitForURL("**/consumption");
    await expect(page.locator("h4:has-text('消费视图')")).toBeVisible();
  });
});
