import { test, expect } from "@playwright/test";

test.describe("Space Management", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/spaces");
    await page.waitForLoadState("networkidle");
  });

  test("should show space list page with title", async ({ page }) => {
    await expect(page.getByRole('heading', { name: '语义空间' })).toBeVisible();
  });

  test("should open create space modal when clicking 创建空间 button", async ({ page }) => {
    await page.getByRole("button", { name: "创建空间" }).click();
    await expect(page.getByText("创建语义空间")).toBeVisible();
  });

  test("should create a new space with name and domain", async ({ page }) => {
    // Open create modal
    await page.getByRole("button", { name: "创建空间" }).click();
    await expect(page.getByText("创建语义空间")).toBeVisible();

    // Wait for modal to be fully rendered
    await page.waitForSelector('.ant-modal-content');

    // Fill form
    await page.getByLabel("空间名称").fill("Test Space E2E");
    await page.getByLabel("业务域").fill("finance");

    // Submit - click the button inside the modal content
    await page.locator('.ant-modal-content .ant-btn-primary').click();

    // Verify space appears in list
    await expect(page.getByText("Test Space E2E")).toBeVisible({ timeout: 10000 });
  });

  test("should show space table columns", async ({ page }) => {
    // Table headers
    await expect(page.getByText("名称")).toBeVisible();
    await expect(page.getByText("状态")).toBeVisible();
    await expect(page.getByText("域")).toBeVisible();
  });
});
