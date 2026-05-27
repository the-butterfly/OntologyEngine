import { test, expect } from "@playwright/test";

test.describe("Instance Graph Visualization", () => {
  test("graph loads with proper layout and controls visible", async ({ page }) => {
    await page.goto("/spaces/space_bd3eeae3/instance-graph");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // 1. Verify page loads
    await expect(page.getByText("实例图谱")).toBeVisible({ timeout: 10000 });

    // 2. Verify layout mode selector
    await expect(page.getByText("力导向")).toBeVisible();
    await expect(page.getByText("DAG分层")).toBeVisible();
    await expect(page.getByText("同心圆")).toBeVisible();

    // 3. Verify search input is visible
    const searchInput = page.getByPlaceholder("搜索节点...");
    await expect(searchInput).toBeVisible();

    // 4. Verify canvas rendered
    const canvas = page.locator("canvas").first();
    await expect(canvas).toBeVisible();

    // 5. Verify no right sidebar (width: 320) - Drawer mode instead
    const sidebarElements = await page.locator('div[style*="width: 320"]').count();
    expect(sidebarElements).toBe(0);

    // 6. Verify grouping panel exists (title is "逻辑分组")
    const groupingVisible = await page.getByText("逻辑分组").isVisible().catch(() => false);
    expect(groupingVisible).toBe(true);

    // 7. Verify metadata stats (use first() to avoid strict mode violation)
    const hasStats = await page.getByText("实体").first().isVisible().catch(() => false);
    expect(hasStats).toBe(true);

    // 8. Verify canvas is rendering content (has width > 0 and height > 0)
    const canvasWidth = await canvas.evaluate((el: any) => el.width);
    const canvasHeight = await canvas.evaluate((el: any) => el.height);
    expect(canvasWidth).toBeGreaterThan(100);
    expect(canvasHeight).toBeGreaterThan(100);

    // 9. Switch layouts and verify no errors
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        errors.push(msg.text());
      }
    });

    await page.getByText("DAG分层").click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "test-results/instance-graph-dagre-layout.png", fullPage: true });

    await page.getByText("同心圆").click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "test-results/instance-graph-concentric-layout.png", fullPage: true });

    await page.getByText("力导向").click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "test-results/instance-graph-force-layout.png", fullPage: true });

    const criticalErrors = errors.filter(
      (e) => !e.includes("favicon") && !e.includes("socket")
    );
    expect(criticalErrors.length).toBe(0);
  });

  test("search highlights and opens detail drawer", async ({ page }) => {
    await page.goto("/spaces/space_bd3eeae3/instance-graph");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Verify graph data loaded first
    const hasStats = await page.getByText("实体").first().isVisible({ timeout: 10000 });
    expect(hasStats).toBe(true);

    // Search for a concept that exists in this space (Borrower is visible in grouping)
    const searchInput = page.getByPlaceholder("搜索节点...");
    await searchInput.click();
    await searchInput.fill("Borrower");
    await page.waitForTimeout(500);

    // Click the search button
    await page.getByRole("button", { name: "搜索" }).click();
    await page.waitForTimeout(2000);

    // Verify drawer opens with node details
    const drawerContainer = page.locator(".ant-drawer-content-wrapper");
    const isDrawerVisible = await drawerContainer.isVisible({ timeout: 5000 }).catch(() => false);
    expect(isDrawerVisible).toBe(true);

    // Verify drawer title
    const drawerTitle = page.getByText("节点详情");
    await expect(drawerTitle).toBeVisible({ timeout: 3000 });

    // Verify the drawer contains the searched node info
    const drawerContent = await page.locator(".ant-drawer-content").innerText();
    expect(drawerContent).toContain("Borrower");

    await page.screenshot({ path: "test-results/instance-graph-search-result.png", fullPage: true });
  });

  test("layout switching works without errors", async ({ page }) => {
    await page.goto("/spaces/space_bd3eeae3/instance-graph");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        errors.push(msg.text());
      }
    });

    // Test each layout
    const layouts = ["DAG分层", "同心圆", "力导向"];
    for (const layout of layouts) {
      await page.getByText(layout).click();
      await page.waitForTimeout(3000);
    }

    const criticalErrors = errors.filter(
      (e) => !e.includes("favicon") && !e.includes("socket")
    );
    expect(criticalErrors.length).toBe(0);
  });

  test("layout lock switch toggles correctly", async ({ page }) => {
    await page.goto("/spaces/space_bd3eeae3/instance-graph");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const hasStats = await page.getByText("实体").first().isVisible({ timeout: 10000 });
    expect(hasStats).toBe(true);

    const lockSwitch = page.locator(".ant-switch");
    await expect(lockSwitch).toBeVisible();

    const unlockedTag = page.getByText("布局未锁定");
    await expect(unlockedTag).toBeVisible();

    await lockSwitch.click();
    await page.waitForTimeout(500);

    const lockedTag = page.getByText("布局已锁定");
    await expect(lockedTag).toBeVisible();

    await lockSwitch.click();
    await page.waitForTimeout(500);

    await expect(page.getByText("布局未锁定")).toBeVisible();
  });

  test("graph legend displays concept colors", async ({ page }) => {
    await page.goto("/spaces/space_bd3eeae3/instance-graph");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const hasStats = await page.getByText("实体").first().isVisible({ timeout: 10000 });
    expect(hasStats).toBe(true);

    const legend = page.getByText("图例说明");
    await expect(legend).toBeVisible();

    const legendColors = page.locator("div[style*='border-radius: 50%'][style*='background']");
    const colorCount = await legendColors.count();
    expect(colorCount).toBeGreaterThan(0);
  });
});
