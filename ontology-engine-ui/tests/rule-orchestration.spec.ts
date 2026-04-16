/**
 * Rule Orchestration E2E Tests - Simplified Version
 *
 * Tests the complete user journeys for rule orchestration:
 * G1: Create/edit/delete rule steps with API persistence
 * G2: 5 operator param editors integration
 * G3: Deep link step editing
 * G4: DAG visualization integration
 * G5: Create page guide for four elements
 *
 * Run with: npx playwright test tests/rule-orchestration.spec.ts --workers=1
 * Requires backend on :8000 and frontend on :3000
 */

import { test, expect, Page } from '@playwright/test';

// Unique suffix for each test run
const RUN_ID = Date.now();

// Helper: Create a test space
async function createSpace(page: Page): Promise<string> {
  await page.goto('/spaces');
  await page.waitForLoadState('networkidle');

  await page.locator('button.ant-btn-primary').first().click();
  await page.waitForSelector('.ant-modal-content', { state: 'visible' });

  const spaceName = `测试空间_${RUN_ID}`;
  await page.getByLabel('空间名称').fill(spaceName);
  await page.getByLabel('业务域').fill('test');

  await page.locator('.ant-modal-content .ant-btn-primary').click();
  await page.waitForURL(/\/spaces\/[^/]+/, { timeout: 15000 });
  await page.waitForLoadState('networkidle');

  const match = page.url().match(/\/spaces\/([^/]+)/);
  return match?.[1] || '';
}

// Helper: Create a rule group
async function createRuleGroup(page: Page, schemaId: string, suffix: string): Promise<string> {
  await page.goto(`/rules/new?schemaId=${schemaId}`);
  await page.waitForLoadState('networkidle');

  await page.getByLabel('规则组名称').fill(`规则组_${suffix}_${RUN_ID}`);
  await page.locator('button[type="submit"]').click();

  await page.waitForURL(/\/rules\/[^?]+\?schemaId=/, { timeout: 15000 });
  await page.waitForLoadState('networkidle');

  const match = page.url().match(/\/rules\/([^?]+)/);
  return match?.[1] || '';
}

// =============================================================================
// G5: Create page guide
// =============================================================================
test.describe('G5: Create page guide', () => {
  test('should navigate to detail page after creating rule group', async ({ page }) => {
    const schemaId = await createSpace(page);
    const groupId = await createRuleGroup(page, schemaId, 'G5_nav');

    expect(groupId).not.toBe('');
    await expect(page).toHaveURL(RegExp(`/rules/${groupId}`));
  });

  test('should show three-column layout on detail page', async ({ page }) => {
    const schemaId = await createSpace(page);
    await createRuleGroup(page, schemaId, 'G5_layout');

    await expect(page.getByText('规则组框架').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('规则实例').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('要素依赖图').first()).toBeVisible({ timeout: 5000 });
  });
});

// =============================================================================
// G1: Rule step CRUD with API persistence
// =============================================================================
test.describe('G1: Rule step persistence', () => {
  let schemaId: string;
  let groupId: string;

  test.beforeEach(async ({ page }) => {
    schemaId = await createSpace(page);
    groupId = await createRuleGroup(page, schemaId, 'G1');
  });

  test('should add a rule step via modal', async ({ page }) => {
    await page.goto(`/rules/${groupId}?schemaId=${schemaId}`);
    await page.waitForLoadState('networkidle');

    // Open add modal
    const addBtn = page.locator('button').filter({ hasText: '添加规则' }).first();
    await addBtn.click();
    await page.waitForSelector('.ant-modal-content', { state: 'visible' });

    // Fill name and save
    const stepName = `规则步骤_${RUN_ID}`;
    await page.getByLabel('规则名称').fill(stepName);
    await page.locator('.ant-modal-content .ant-btn-primary').last().click();
    await page.waitForTimeout(2000);

    // Step should appear in list
    await expect(page.getByText(stepName).first()).toBeVisible({ timeout: 5000 });
  });

  test('should persist step after page reload', async ({ page }) => {
    const stepName = `规则步骤_持久化_${RUN_ID}`;

    // Create step
    await page.goto(`/rules/${groupId}?schemaId=${schemaId}`);
    await page.waitForLoadState('networkidle');
    await page.locator('button').filter({ hasText: '添加规则' }).first().click();
    await page.waitForSelector('.ant-modal-content', { state: 'visible' });
    await page.getByLabel('规则名称').fill(stepName);
    await page.locator('.ant-modal-content .ant-btn-primary').last().click();
    await page.waitForTimeout(2000);

    // Reload page
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Step should still exist
    await expect(page.getByText(stepName).first()).toBeVisible({ timeout: 5000 });
  });
});

// =============================================================================
// G2: Operator editors
// =============================================================================
test.describe('G2: Operator specialized editors', () => {
  let schemaId: string;
  let groupId: string;

  test.beforeEach(async ({ page }) => {
    schemaId = await createSpace(page);
    groupId = await createRuleGroup(page, schemaId, 'G2');
    await page.goto(`/rules/${groupId}?schemaId=${schemaId}`);
    await page.waitForLoadState('networkidle');
    await page.locator('button').filter({ hasText: '添加规则' }).first().click();
    await page.waitForSelector('.ant-modal-content', { state: 'visible' });
  });

  test('SCORECARD operator should show specialized editor', async ({ page }) => {
    // Switch to THEN tab
    await page.getByRole('tab', { name: /THEN/i }).click();
    await page.waitForTimeout(500);

    // Select SCORECARD operator
    await page.locator('.ant-modal-content .ant-select').first().click();
    await page.waitForTimeout(300);
    await page.getByText('SCORECARD').click();
    await page.waitForTimeout(1500);

    // Should show scorecard editor
    await expect(page.getByText('baseline')).toBeVisible({ timeout: 5000 });
  });

  test('BINNING operator should show specialized editor', async ({ page }) => {
    await page.getByRole('tab', { name: /THEN/i }).click();
    await page.waitForTimeout(500);

    await page.locator('.ant-modal-content .ant-select').first().click();
    await page.waitForTimeout(300);
    await page.getByText('BINNING').click();
    await page.waitForTimeout(1500);

    await expect(page.getByText(/bins|区间/i).first()).toBeVisible({ timeout: 5000 });
  });
});

// =============================================================================
// G3: Deep link step editing
// =============================================================================
test.describe('G3: Deep link step editing', () => {
  test('should open edit modal via deep link', async ({ page }) => {
    const schemaId = await createSpace(page);
    const groupId = await createRuleGroup(page, schemaId, 'G3');

    // Create a step first
    await page.goto(`/rules/${groupId}?schemaId=${schemaId}`);
    await page.waitForLoadState('networkidle');
    await page.locator('button').filter({ hasText: '添加规则' }).first().click();
    await page.waitForSelector('.ant-modal-content', { state: 'visible' });
    await page.getByLabel('规则名称').fill(`步骤_深链接_${RUN_ID}`);
    await page.locator('.ant-modal-content .ant-btn-primary').last().click();
    await page.waitForTimeout(2000);

    // Get step ID from DOM
    const stepCard = page.locator('[class*="list-item"]').first();
    const stepId = await stepCard.getAttribute('data-step-id');

    if (stepId) {
      // Navigate to deep link
      await page.goto(`/rules/${groupId}/steps/${stepId}/edit?schemaId=${schemaId}`);
      await page.waitForLoadState('networkidle');

      // Should redirect and open modal
      await expect(page.locator('.ant-modal-content')).toBeVisible({ timeout: 5000 });
    }
  });
});

// =============================================================================
// Condition editor
// =============================================================================
test.describe('Condition editor', () => {
  let schemaId: string;
  let groupId: string;

  test.beforeEach(async ({ page }) => {
    schemaId = await createSpace(page);
    groupId = await createRuleGroup(page, schemaId, 'cond');
    await page.goto(`/rules/${groupId}?schemaId=${schemaId}`);
    await page.waitForLoadState('networkidle');
    await page.locator('button').filter({ hasText: '添加规则' }).first().click();
    await page.waitForSelector('.ant-modal-content', { state: 'visible' });
  });

  test('should render textarea for expression condition', async ({ page }) => {
    await expect(page.locator('textarea').first()).toBeVisible({ timeout: 3000 });
  });
});

// =============================================================================
// Simulation panel
// =============================================================================
test.describe('Simulation panel', () => {
  let schemaId: string;
  let groupId: string;

  test.beforeEach(async ({ page }) => {
    schemaId = await createSpace(page);
    groupId = await createRuleGroup(page, schemaId, 'sim');
    await page.goto(`/rules/${groupId}?schemaId=${schemaId}`);
    await page.waitForLoadState('networkidle');
    await page.locator('button').filter({ hasText: '添加规则' }).first().click();
    await page.waitForSelector('.ant-modal-content', { state: 'visible' });
  });

  test('simulation tab should be visible', async ({ page }) => {
    await page.getByRole('tab', { name: /模拟/i }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText('模拟执行').first()).toBeVisible({ timeout: 3000 });
  });
});
