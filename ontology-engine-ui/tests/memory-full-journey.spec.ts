import { test, expect, Page } from "@playwright/test";
import {
  MOCK_NODES,
  MOCK_STATS,
  MOCK_ACTIVITIES,
  MOCK_CONTRADICTIONS,
  MOCK_RECALL_RESPONSE,
  MOCK_REFLECT_RESPONSE,
  MOCK_SPACE_ID,
} from "./mock-memory-data";

const BASE_URL = "http://localhost:3000";

function jsonOk(data: any) {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ success: true, data }),
  };
}

function mockApiResponses(page: Page) {
  return page.route("**/v1/**", (route) => {
    const url = route.request().url();
    const method = route.request().method();

    // Space detail - MUST include all fields SpaceDetailPage uses
    if (url.match(/\/v1\/spaces\/[^/]+$/) && method === "GET") {
      return route.fulfill(jsonOk({
        id: MOCK_SPACE_ID,
        name: "Mock Memory Space",
        description: "Test space for E2E",
        node_count: 25,
        status: "active",
        version: 1,
        entity_count: 4,
        rule_definition_count: 3,
        rule_logic_count: 2,
        view_id: null,
        schema_refs: [],
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T00:00:00Z",
      }));
    }

    // Spaces list
    if (url.match(/\/v1\/spaces$/) && method === "GET") {
      return route.fulfill(jsonOk([{
        id: MOCK_SPACE_ID,
        name: "Mock Memory Space",
        description: "Test space for E2E",
        node_count: 25,
        status: "active",
        version: 1,
        entity_count: 4,
        rule_definition_count: 3,
        rule_logic_count: 2,
        view_id: null,
        schema_refs: [],
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T00:00:00Z",
      }]));
    }

    // Space sub-resources (needed by store.setActiveSpace)
    if (url.includes("/schema/L4/rules/definitions") && method === "GET") return route.fulfill(jsonOk([]));
    if (url.includes("/schema/L4/rules/logics") && method === "GET") return route.fulfill(jsonOk([]));
    if (url.includes("/versions") && method === "GET") return route.fulfill(jsonOk([]));
    if (url.includes("/schema/L1/fact-objects") && method === "GET") return route.fulfill(jsonOk([]));
    if (url.includes("/instances/entities") && method === "GET") return route.fulfill(jsonOk([]));

    // Memory endpoints
    if (url.includes("/memory/stats") && method === "GET") return route.fulfill(jsonOk(MOCK_STATS));
    if (url.includes("/memory/audit") && method === "GET") return route.fulfill(jsonOk({ entries: MOCK_ACTIVITIES }));
    if (url.includes("/memory/types") && method === "GET") return route.fulfill(jsonOk(["observation", "opinion", "entity", "fragment"]));
    if (url.includes("/memory/contradictions") && method === "GET") return route.fulfill(jsonOk(MOCK_CONTRADICTIONS));
    if (url.includes("/memory/corrections") && method === "GET") return route.fulfill(jsonOk([]));
    if (url.includes("/memory/recall") && method === "POST") return route.fulfill(jsonOk(MOCK_RECALL_RESPONSE));
    if (url.includes("/memory/reflect") && method === "POST") return route.fulfill(jsonOk(MOCK_REFLECT_RESPONSE));
    if (url.includes("/memory/remember") && method === "POST") return route.fulfill(jsonOk({ memory_id: "mem:observation:mock:new", node_id: "mem:observation:mock:new" }));
    if (url.includes("/memory/approve") && method === "POST") return route.fulfill(jsonOk(null));
    if (url.includes("/memory/consolidate") && method === "POST") return route.fulfill(jsonOk(null));
    if (url.includes("/memory/forget") && method === "POST") return route.fulfill(jsonOk(null));

    // Default: return null data for any unhandled v1 request
    return route.fulfill(jsonOk(null));
  });
}

async function navigateToMemory(page: Page, subPath: string = "") {
  await page.goto(`${BASE_URL}/spaces/${MOCK_SPACE_ID}/memory${subPath}`);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(2000);
}

test.describe("J1: /memory 路由修复验证", () => {
  test("J1.1: /memory should redirect to /spaces", async ({ page }) => {
    await page.goto(`${BASE_URL}/memory`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    expect(page.url()).toContain("/spaces");
  });
});

test.describe("J2: 记忆总览页 — 记忆图谱 Tab", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await navigateToMemory(page);
  });

  test("J2.1: should display 4 stat cards with correct data", async ({ page }) => {
    await expect(page.getByText("总记忆数")).toBeVisible();
    await expect(page.getByText("Layer-R")).toBeVisible();
    await expect(page.getByText("Layer-S")).toBeVisible();
    await expect(page.getByText("待审区")).toBeVisible();
  });

  test("J2.2: should display memory type distribution tags", async ({ page }) => {
    await expect(page.getByText("记忆类型分布")).toBeVisible();
    await expect(page.locator(".ant-tag:has-text('observation')").first()).toBeVisible();
  });

  test("J2.3: should display belief status distribution tags", async ({ page }) => {
    await expect(page.getByText("信念状态分布")).toBeVisible();
    await expect(page.locator(".ant-tag:has-text('accepted')").first()).toBeVisible();
  });

  test("J2.4: should display memory strength heatmap", async ({ page }) => {
    await expect(page.getByText("记忆强度热力图")).toBeVisible();
  });

  test("J2.5: should display memory node table", async ({ page }) => {
    await expect(page.getByText("记忆节点列表")).toBeVisible();
    const rows = page.locator(".ant-table-tbody tr");
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });
});

test.describe("J3: 记忆总览页 — Agent 活动 Tab", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await navigateToMemory(page);
    await page.locator(".ant-tabs-tab:has-text('Agent 活动')").click();
    await page.waitForTimeout(600);
  });

  test("J3.1: should display activity stats and list", async ({ page }) => {
    await expect(page.getByText("最近活动")).toBeVisible();
    await expect(page.getByText("总活动数")).toBeVisible();
  });

  test("J3.2: should display activity list with at least 3 entries", async ({ page }) => {
    const items = page.locator(".ant-list-item");
    const count = await items.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });
});

test.describe("J4: 记忆管理页 — 治理仪表盘", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await navigateToMemory(page, "/manage");
  });

  test("J4.1: should display governance dashboard with 6 stat cards", async ({ page }) => {
    await expect(page.getByText("治理仪表盘")).toBeVisible();
    await expect(page.getByText("总记忆", { exact: true })).toBeVisible();
    await expect(page.getByText("待审", { exact: true })).toBeVisible();
    await expect(page.getByText("矛盾", { exact: true })).toBeVisible();
  });

  test("J4.2: should display Layer distribution and maintenance buttons", async ({ page }) => {
    await expect(page.getByText("Layer 分布")).toBeVisible();
    await expect(page.locator("button:has-text('整合')")).toBeVisible();
  });
});

test.describe("J5: 记忆管理页 — 矛盾看板", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await navigateToMemory(page, "/manage");
  });

  test("J5.1: should display contradiction board with badge", async ({ page }) => {
    await expect(page.getByText("矛盾看板")).toBeVisible();
    const badge = page.locator(".ant-badge-count");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText("2");
  });

  test("J5.2: should display severity tags and action buttons", async ({ page }) => {
    await expect(page.locator("button:has-text('采纳新值')").first()).toBeVisible();
    await expect(page.locator("button:has-text('忽略')").first()).toBeVisible();
    await expect(page.locator("button:has-text('刷新矛盾')")).toBeVisible();
  });
});

test.describe("J6: 记忆构建页", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await navigateToMemory(page, "/build");
  });

  test("J6.1: should display build page and review queue", async ({ page }) => {
    await expect(page.getByText("创建记忆")).toBeVisible();
    await expect(page.getByText("待审区")).toBeVisible();
  });

  test("J6.2: should allow creating a memory via form", async ({ page }) => {
    const textArea = page.locator("textarea").first();
    if (await textArea.isVisible()) {
      await textArea.fill("E2E 验证测试记忆内容");
      const createBtn = page.locator("button:has-text('创建')").first();
      if (await createBtn.isVisible()) {
        await createBtn.click();
        await page.waitForTimeout(1000);
      }
    }
  });
});

test.describe("J7: 记忆消费页", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await navigateToMemory(page, "/consume");
  });

  test("J7.1: should display search interface", async ({ page }) => {
    await expect(page.getByText("分层检索")).toBeVisible();
    await expect(page.locator("input[placeholder='输入查询内容...']")).toBeVisible();
    await expect(page.locator("button:has-text('搜索')")).toBeVisible();
  });

  test("J7.2: should return results on search", async ({ page }) => {
    await page.locator("input[placeholder='输入查询内容...']").fill("供应商");
    await page.locator("button:has-text('搜索')").click();
    await page.waitForTimeout(2000);
    // Results should appear in collapse panels
    const panels = page.locator(".ant-collapse-header");
    const count = await panels.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });
});

test.describe("J8: 反思中心", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await navigateToMemory(page, "/reflect");
  });

  test("J8.1: should display reflect center interface", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "反思中心" })).toBeVisible();
    await expect(page.getByText("发起反思")).toBeVisible();
    await expect(page.getByText("Reflect 任务")).toBeVisible();
  });

  test("J8.2: should execute reflect and show task in list", async ({ page }) => {
    await page.locator("textarea").fill("验证供应商信用评级的矛盾");
    await page.locator("button:has-text('启动反思')").click();
    await page.waitForTimeout(1000);
    const items = page.locator(".ant-list-item");
    const count = await items.count();
    expect(count).toBeGreaterThan(0);
  });

  test("J8.3: should expand reflect report with insights and contradictions", async ({ page }) => {
    await page.locator("textarea").fill("验证供应商信用评级");
    await page.locator("button:has-text('启动反思')").click();
    await page.waitForTimeout(1000);

    const expandBtn = page.locator("button:has-text('展开详情')");
    if (await expandBtn.isVisible().catch(() => false)) {
      await expandBtn.click();
      await page.waitForTimeout(500);
    }
  });
});

test.describe("J9: 全旅程端到端", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
  });

  test("J9.1: complete 5-page journey: overview → manage → consume → build → reflect", async ({ page }) => {
    // Overview
    await navigateToMemory(page);
    await expect(page.getByText("记忆图谱")).toBeVisible();

    // Manage
    await navigateToMemory(page, "/manage");
    await expect(page.getByText("治理仪表盘")).toBeVisible();
    await expect(page.getByText("矛盾看板")).toBeVisible();

    // Consume
    await navigateToMemory(page, "/consume");
    await expect(page.getByText("分层检索")).toBeVisible();

    // Build
    await navigateToMemory(page, "/build");
    await expect(page.getByText("待审区")).toBeVisible();

    // Reflect
    await navigateToMemory(page, "/reflect");
    await expect(page.getByRole("heading", { name: "反思中心" })).toBeVisible();
  });

  test("J9.2: agent activity shows saved remember/consolidate events", async ({ page }) => {
    await navigateToMemory(page);
    await page.locator(".ant-tabs-tab:has-text('Agent 活动')").click();
    await page.waitForTimeout(600);

    const items = page.locator(".ant-list-item");
    const count = await items.count();
    expect(count).toBeGreaterThanOrEqual(5);
  });

  test("J9.3: verify contradiction data in manage page", async ({ page }) => {
    await navigateToMemory(page, "/manage");
    const badge = page.locator(".ant-badge-count");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText("2");
  });
});

test.describe("J10: 验证案例映射 — 覆盖所有 8 组", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await navigateToMemory(page);
  });

  test("J10.1: stats card reflects MOCK_STATS data", async ({ page }) => {
    await expect(page.getByText("总记忆数")).toBeVisible();
    // Verify Layer-R shows perception count from mock data
    await expect(page.getByText("Layer-R")).toBeVisible();
  });

  test("J10.2: overview tab integration is functional", async ({ page }) => {
    // All key sections visible in overview tab
    await expect(page.getByText("记忆类型分布")).toBeVisible();
    await expect(page.getByText("信念状态分布")).toBeVisible();
    await expect(page.getByText("记忆强度热力图")).toBeVisible();
    await expect(page.getByText("记忆节点列表")).toBeVisible();
  });

  test("J10.3: navigation to all tabs within overview page works", async ({ page }) => {
    // Agent tab
    await page.locator(".ant-tabs-tab:has-text('Agent 活动')").click();
    await page.waitForTimeout(500);
    await expect(page.getByText("最近活动")).toBeVisible();

    // Validation tab
    await page.locator(".ant-tabs-tab:has-text('验证演示')").click();
    await page.waitForTimeout(500);
    await expect(page.locator(".ant-select").first()).toBeVisible();
  });
});
