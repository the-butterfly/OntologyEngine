import { test, expect } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL || "http://localhost:3002";
const TEST_SPACE_ID = process.env.E2E_SPACE_ID || "space_7cee0200";

test.describe("Agent Memory 功能验收测试", () => {
  test.describe("1. 记忆总览页面", () => {
    test("1.1 页面加载成功，显示记忆统计", async ({ page }) => {
      await page.goto(`${BASE_URL}/spaces/${TEST_SPACE_ID}/memory`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      // 验证页面标题
      await expect(page.getByRole("heading", { name: "记忆总览" })).toBeVisible();

      // 验证统计卡片
      await expect(page.getByText("总记忆数")).toBeVisible();
      await expect(page.getByText("Layer-R")).toBeVisible();
      await expect(page.getByText("Layer-S")).toBeVisible();
      await expect(page.getByText("待审区")).toBeVisible();

      // 验证记忆类型分布
      await expect(page.getByText("记忆类型分布")).toBeVisible();

      // 验证信念状态分布
      await expect(page.getByText("信念状态分布")).toBeVisible();

      // 验证记忆强度热力图
      await expect(page.getByText("记忆强度热力图")).toBeVisible();

      // 验证记忆节点图谱
      await expect(page.getByText("记忆节点图谱")).toBeVisible();

      // 验证记忆节点列表
      await expect(page.getByText("记忆节点列表")).toBeVisible();
    });

    test("1.2 记忆图谱画布显示节点", async ({ page }) => {
      await page.goto(`${BASE_URL}/spaces/${TEST_SPACE_ID}/memory`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(3000);

      // 检查记忆节点图谱区域是否存在
      await expect(page.getByText("记忆节点图谱")).toBeVisible();
    });
  });

  test.describe("2. Agent 活动 Tab", () => {
    test("2.1 显示活动统计和列表", async ({ page }) => {
      await page.goto(`${BASE_URL}/spaces/${TEST_SPACE_ID}/memory?tab=activities`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      // 验证统计卡片
      await expect(page.getByText("总活动数")).toBeVisible();
      await expect(page.locator(".ant-statistic-title", { hasText: "Remember" }).first()).toBeVisible();
      await expect(page.locator(".ant-statistic-title", { hasText: "Recall" }).first()).toBeVisible();
      await expect(page.locator(".ant-statistic-title", { hasText: "成功" }).first()).toBeVisible();

      // 验证活动列表
      await expect(page.getByText("最近活动")).toBeVisible();
    });

    test("2.2 活动数据显示正确", async ({ page }) => {
      await page.goto(`${BASE_URL}/spaces/${TEST_SPACE_ID}/memory?tab=activities`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      // 获取活动列表项
      const activities = page.locator(".ant-list-item");
      const count = await activities.count();

      // 验证有活动数据
      expect(count).toBeGreaterThan(0);

      // 验证每个活动项都有状态标签
      for (let i = 0; i < Math.min(count, 3); i++) {
        const item = activities.nth(i);
        const statusTag = item.locator(".ant-tag").first();
        await expect(statusTag).toBeVisible();
      }
    });
  });

  test.describe("3. 验证演示 Tab", () => {
    test("3.1 显示验证案例选择", async ({ page }) => {
      await page.goto(`${BASE_URL}/spaces/${TEST_SPACE_ID}/memory?tab=validation`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      // 验证选择框
      await expect(page.locator(".ant-card-head-title", { hasText: "选择验证案例" }).first()).toBeVisible();

      // 验证按钮
      await expect(page.getByRole("button", { name: "开始验证" })).toBeVisible();
      await expect(page.getByRole("button", { name: "重置" })).toBeVisible();
    });
  });

  test.describe("4. 记忆构建页面", () => {
    test("4.1 创建记忆成功", async ({ page }) => {
      await page.goto(`${BASE_URL}/spaces/${TEST_SPACE_ID}/memory/build`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      // 填写表单
      await page.getByPlaceholder("输入记忆内容...").fill("验收测试记忆内容");
      await page.getByRole("button", { name: "创建记忆" }).click();

      // 等待响应
      await page.waitForTimeout(2000);

      // 验证成功提示或记忆列表更新
      const pageContent = await page.content();
      expect(pageContent).toContain("记忆创建成功");
    });
  });

  test.describe("5. 记忆消费页面", () => {
    test("5.1 搜索功能正常", async ({ page }) => {
      await page.goto(`${BASE_URL}/spaces/${TEST_SPACE_ID}/memory/consume`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      // 验证搜索框和按钮存在
      await expect(page.getByPlaceholder("输入查询内容...")).toBeVisible();
      await expect(page.getByRole("button", { name: "搜索" })).toBeVisible();

      // 执行搜索
      await page.getByPlaceholder("输入查询内容...").fill("测试");
      await page.getByRole("button", { name: "搜索" }).click();

      // 等待结果
      await page.waitForTimeout(2000);

      // 验证页面内容包含搜索结果相关文本
      const pageContent = await page.content();
      expect(pageContent).toMatch(/搜索结果|分层检索|记忆召回/);
    });
  });

  test.describe("6. 反思中心页面", () => {
    test("6.1 反思表单显示正确", async ({ page }) => {
      await page.goto(`${BASE_URL}/spaces/${TEST_SPACE_ID}/memory/reflect`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      // 验证表单元素
      await expect(page.getByPlaceholder("输入反思主题或问题...")).toBeVisible();
      await expect(page.getByText("最大迭代数")).toBeVisible();
      await expect(page.getByRole("button", { name: "启动反思" })).toBeVisible();
    });
  });

  test.describe("7. 数据一致性验证", () => {
    test("7.1 统计数据与节点列表一致", async ({ page }) => {
      await page.goto(`${BASE_URL}/spaces/${TEST_SPACE_ID}/memory`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      // 获取统计卡片中的总记忆数
      const totalStat = page.locator(".ant-statistic-title", { hasText: "总记忆数" }).locator("..").locator(".ant-statistic-content");
      const totalText = await totalStat.textContent();
      const totalCount = parseInt(totalText || "0", 10);

      // 获取表格中的行数
      const tableRows = page.locator(".ant-table-tbody tr");
      const rowCount = await tableRows.count();

      // 验证统计与表格数据一致（考虑分页）
      expect(totalCount).toBeGreaterThanOrEqual(rowCount);
    });

    test("7.2 API 响应格式正确", async ({ request }) => {
      // 测试 stats API
      const statsResponse = await request.get(`${BASE_URL}/v1/spaces/${TEST_SPACE_ID}/memory/stats`);
      expect(statsResponse.ok()).toBeTruthy();
      const statsData = await statsResponse.json();
      expect(statsData.success).toBe(true);
      expect(statsData.data).toHaveProperty("total");
      expect(statsData.data).toHaveProperty("by_type");
      expect(statsData.data).toHaveProperty("by_belief");

      // 测试 recall API
      const recallResponse = await request.post(`${BASE_URL}/v1/spaces/${TEST_SPACE_ID}/memory/recall`, {
        data: { query: "*", max_results: 10 },
      });
      expect(recallResponse.ok()).toBeTruthy();
      const recallData = await recallResponse.json();
      expect(recallData.success).toBe(true);
      expect(recallData.data).toHaveProperty("results");
      expect(recallData.data).toHaveProperty("total");

      // 测试 audit API
      const auditResponse = await request.get(`${BASE_URL}/v1/spaces/${TEST_SPACE_ID}/memory/audit?limit=5`);
      expect(auditResponse.ok()).toBeTruthy();
      const auditData = await auditResponse.json();
      expect(auditData.success).toBe(true);
      expect(auditData.data).toHaveProperty("entries");
      const entries = auditData.data.entries || auditData.data.activity_entries || [];
      if (entries.length > 0) {
        const entry = entries[0];
        expect(entry).toHaveProperty("id");
        expect(entry).toHaveProperty("activity_type");
        expect(typeof entry.success).toBe("boolean");
      }
    });

    test("7.3 Dream Cycle API 可调用", async ({ request }) => {
      const dreamResponse = await request.post(`${BASE_URL}/v1/spaces/${TEST_SPACE_ID}/memory/dream`);
      expect(dreamResponse.ok()).toBeTruthy();
      const dreamData = await dreamResponse.json();
      expect(dreamData.success).toBe(true);
      expect(dreamData.data).toHaveProperty("contradictions");
      expect(dreamData.data).toHaveProperty("expired");
      expect(dreamData.data).toHaveProperty("errors");
      expect(dreamData.data).toHaveProperty("space_id");
    });
  });
});
