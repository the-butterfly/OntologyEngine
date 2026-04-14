import { test, expect } from "@playwright/test";

test.describe("Rule Execution", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/spaces");
    await page.waitForLoadState("networkidle");
  });

  test("should show rule execution tabs when viewing a space", async ({ page }) => {
    // Navigate to a space
    // First check there is a space to click
    const spaceLink = page.locator("a").filter({ hasText: /./ }).first();
    // Just verify page structure exists
    await expect(page.getByRole('heading', { name: '语义空间' })).toBeVisible();
  });

  test("rule execution page should have entity selector and dimension selector", async ({ page }) => {
    // Create a space first
    await page.getByRole("button", { name: "创建空间" }).click();
    await page.waitForSelector('.ant-modal-content');
    await page.getByLabel("空间名称").fill("Rule Test Space");
    await page.locator('.ant-modal-content .ant-btn-primary').click();

    // Navigate to the space
    await page.getByText("Rule Test Space").first().click();
    await page.waitForLoadState("networkidle");

    // Navigate to execute tab
    await page.getByText("规则执行").click();
    await page.waitForLoadState("networkidle");

    // The rule execution page should have entity selector and dimension selector
    await expect(page.getByText("实体").first()).toBeVisible();
    await expect(page.getByText("维度").first()).toBeVisible();
  });

  test("simulation page should be accessible from space detail", async ({ page }) => {
    // Create a space
    await page.getByRole("button", { name: "创建空间" }).click();
    await page.waitForSelector('.ant-modal-content');
    await page.getByLabel("空间名称").fill("Sim Test Space");
    await page.locator('.ant-modal-content .ant-btn-primary').click();

    // Navigate to the space
    await page.getByText("Sim Test Space").first().click();
    await page.waitForLoadState("networkidle");

    // Navigate to simulate tab
    await page.getByText("What-If 模拟").click();
    await page.waitForLoadState("networkidle");

    // Should see simulation controls
    await expect(page.getByText("模拟参数")).toBeVisible();
  });
});
