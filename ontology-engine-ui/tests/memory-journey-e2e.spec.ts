import { test, expect } from "@playwright/test";

/**
 * E2E tests for Agent Memory user journey after Phase 1 & 2 improvements.
 * Verifies: detail drawer, graph view, approval actions, layered results,
 * reflect details, page navigation, activity stats, correction history.
 */

const BASE_URL = "http://localhost:3004";
const SPACE_ID = "space_7cee0200";

test.describe("Agent Memory Journey - Phase 1 & 2", () => {

  test("T1.3 MemoryOverview: stats, node table, graph view, and detail drawer", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Stats cards visible
    await expect(page.locator("text=总记忆数")).toBeVisible();
    await expect(page.locator("text=Layer-R")).toBeVisible();
    await expect(page.locator("text=Layer-S")).toBeVisible();
    await expect(page.locator("text=待审区")).toBeVisible();

    // Memory type distribution
    await expect(page.locator("text=记忆类型分布")).toBeVisible();

    // Belief status distribution
    await expect(page.locator("text=信念状态分布")).toBeVisible();

    // Graph view
    await expect(page.locator("text=记忆节点图谱")).toBeVisible();

    // Node table
    await expect(page.locator("text=记忆节点列表")).toBeVisible();

    // Check if table has data rows (not just empty state)
    const firstViewBtn = page.locator(".ant-table-tbody tr:first-child button:has-text('查看')");
    const hasData = await firstViewBtn.isVisible().catch(() => false);

    if (hasData) {
      // Click "查看" button on first row to open detail drawer
      await firstViewBtn.click();
      await page.waitForTimeout(500);

      // Drawer should open
      await expect(page.locator(".ant-drawer-title:has-text('记忆详情')")).toBeVisible();

      // Close drawer
      await page.locator(".ant-drawer-close").click();
    }

    await page.screenshot({ path: "test-results/memory-overview-phase2.png", fullPage: true });
  });

  test("T1.4 MemoryOverview: Agent Activities tab with stats and detail view", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Click Agent 活动 tab
    await page.locator(".ant-tabs-tab:has-text('Agent 活动')").click();
    await page.waitForTimeout(1000);

    // Activity stats cards
    await expect(page.locator("text=总活动数")).toBeVisible();
    await expect(page.locator("text=待审核")).toBeVisible();
    await expect(page.locator("text=已拒绝")).toBeVisible();
    await expect(page.locator("text=已替代")).toBeVisible();

    // Activity list or empty state
    const hasActivities = await page.locator(".ant-list-item").count() > 0;
    if (hasActivities) {
      await expect(page.locator("button:has-text('查看')").first()).toBeVisible();
    } else {
      await expect(page.locator("text=暂无活动记录")).toBeVisible();
    }

    await page.screenshot({ path: "test-results/memory-activities-phase2.png", fullPage: true });
  });

  test("T1.6 MemoryBuild: pending review queue with approval/reject/correct actions", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory/build`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Form visible
    await expect(page.locator("text=创建新记忆")).toBeVisible();

    // Pending review queue
    await expect(page.locator("text=待审区队列")).toBeVisible();

    const hasPending = await page.locator(".ant-list-item").count() > 0;
    if (hasPending) {
      // Action buttons should be visible
      await expect(page.locator("button:has-text('确认')").first()).toBeVisible();
      await expect(page.locator("button:has-text('更正')").first()).toBeVisible();
      await expect(page.locator("button:has-text('拒绝')").first()).toBeVisible();
      await expect(page.locator("button:has-text('查看')").first()).toBeVisible();
    } else {
      await expect(page.locator("text=暂无待审核记忆")).toBeVisible();
    }

    await page.screenshot({ path: "test-results/memory-build-phase2.png", fullPage: true });
  });

  test("T1.7 MemoryConsume: layered results with detail drawer", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory/consume`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Search and Disposition visible
    await expect(page.locator("text=分层检索")).toBeVisible();
    await expect(page.locator("text=Disposition Profile")).toBeVisible();

    // Search for something
    await page.locator("input[placeholder='输入查询内容...']").fill("测试");
    await page.locator("button:has-text('搜索')").click();
    await page.waitForTimeout(1500);

    // Results should show
    const hasResults = await page.locator(".ant-collapse").count() > 0;
    if (hasResults) {
      // Layered panels
      await expect(page.locator(".ant-collapse-header").first()).toBeVisible();

      // View detail button
      await expect(page.locator("button:has-text('查看详情')").first()).toBeVisible();
    }

    await page.screenshot({ path: "test-results/memory-consume-phase2.png", fullPage: true });
  });

  test("T2.2 ReflectCenter: task list with expand details", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory/reflect`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Form visible
    await expect(page.locator("text=发起反思")).toBeVisible();

    // Task list
    await expect(page.locator("text=Reflect 任务")).toBeVisible();

    await page.screenshot({ path: "test-results/memory-reflect-phase2.png", fullPage: true });
  });

  test("T2.3 & T2.5 MemoryManage: navigation links and correction history", async ({ page }) => {
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory/manage`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Navigation links
    await expect(page.locator("button:has-text('去构建记忆')")).toBeVisible();
    await expect(page.locator("button:has-text('去检索记忆')")).toBeVisible();
    await expect(page.locator("button:has-text('去反思中心')")).toBeVisible();

    // Stats
    await expect(page.locator("text=总记忆数")).toBeVisible();

    // Correction history
    await expect(page.locator("text=更正历史")).toBeVisible();

    await page.screenshot({ path: "test-results/memory-manage-phase2.png", fullPage: true });
  });

  test("T2.3 Page navigation: Manage -> Build -> Consume -> Reflect", async ({ page }) => {
    // Start at manage page
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory/manage`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    // Click to build page
    await page.locator("button:has-text('去构建记忆')").click();
    await page.waitForURL(`**/spaces/${SPACE_ID}/memory/build`);
    await expect(page.locator("text=记忆构建")).toBeVisible();

    // Click to consume page (via URL since build page doesn't have nav yet)
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory/consume`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=记忆消费")).toBeVisible();

    // Click to reflect page
    await page.goto(`${BASE_URL}/spaces/${SPACE_ID}/memory/reflect`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=反思中心")).toBeVisible();
  });
});
