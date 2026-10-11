import { expect, Page, test } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

/**
 * Live integration: requires the backend on :8000 (with analysed events in its database) and the
 * frontend on :5173. Screenshots go to e2e/artifacts/ for visual inspection.
 */
const ART = path.join(path.dirname(fileURLToPath(import.meta.url)), 'artifacts');
fs.mkdirSync(ART, { recursive: true });

function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
  page.on('requestfailed', (r) => errors.push(`requestfailed: ${r.url()} ${r.failure()?.errorText}`));
  return errors;
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { localStorage.setItem('xyz_demo_mode', 'false'); });
});

test('overview lists real events from the backend', async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto('/overview');
  await expect(page.getByText('Brent crude jumps 8% after OPEC+ announces surprise output cut').first()).toBeVisible();
  await expect(page.getByText('SIMULATED').first()).toBeVisible();
  await expect(page.getByText(/DEMO DATA/)).toHaveCount(0);
  await page.screenshot({ path: path.join(ART, 'overview.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('workspace renders the actual event graph (Cytoscape)', async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto('/overview');
  await page.getByText('Brent crude jumps 8% after OPEC+ announces surprise output cut').first().click();
  await expect(page).toHaveURL(/workspace/);
  await expect(page.getByText(/Top impact pathways/)).toBeVisible();
  const canvases = page.locator('canvas');
  await expect(canvases.first()).toBeVisible();
  const box = await canvases.first().boundingBox();
  expect(box!.width).toBeGreaterThan(300);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(ART, 'workspace_graph.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('simulator: presets from /api/scenarios, simulation round-trip, 3D graph, panels, report and PDF', async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto('/black-swan');
  const preset = page.locator('select').first();
  await expect(preset).toContainText('Global Oil Supply Shock');
  const oil = page.locator('input[type="number"]').first();
  await oil.fill('15');
  const [simResp] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/api/simulations') && r.request().method() === 'POST'),
    page.getByRole('button', { name: /Run Simulation/ }).click(),
  ]);
  expect(simResp.status()).toBe(200);
  const body = JSON.parse(simResp.request().postData() || '{}');
  expect(body).toEqual({ scenario_id: 'global_oil_supply_shock', shocks: { oil_price_change_pct: 15 }, horizon_days: 5 });
  await expect(page.getByText('HISTORICAL OBSERVATIONS', { exact: true })).toBeVisible();
  await expect(page.getByText(/Estimates available|input in the outer 1% tail/).first()).toBeVisible();
  const canvas3d = page.locator('canvas').first();
  await expect(canvas3d).toBeVisible();
  expect((await canvas3d.boundingBox())!.height).toBeGreaterThan(300);
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(ART, 'simulator_live.png'), fullPage: true });

  await page.getByRole('button', { name: /Generate report/ }).click();
  await expect(page).toHaveURL(/\/reports\/rep_/, { timeout: 60_000 });
  await expect(page.locator('section[data-section]')).toHaveCount(12);
  await expect(page.getByText('HYPOTHETICAL SCENARIO').first()).toBeVisible();
  await page.screenshot({ path: path.join(ART, 'simulation_report.png'), fullPage: true });
  const reportId = page.url().split('/reports/')[1];
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: /Export PDF/ }).click()]);
  const pdfPath = path.join(ART, `${reportId}.pdf`);
  await download.saveAs(pdfPath);
  const pdf = fs.readFileSync(pdfPath, 'latin1');
  expect(pdf).toContain(reportId);
  expect(pdf).toContain('Quantitative ML Predictions');
  expect(pdf).not.toContain('XYZ FINANCIAL INTELLIGENCE');
  expect(errors).toEqual([]);
});

test('simulator: out-of-domain shock shows unavailable estimates, not zeros', async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto('/black-swan');
  await page.locator('input[type="number"]').first().fill('60');
  await page.getByRole('button', { name: /Run Simulation/ }).click();
  await expect(page.getByText(/Declined: inputs outside the range/)).toBeVisible();
  await expect(page.getByText('unavailable', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('+0.00%')).toHaveCount(0);
  await page.screenshot({ path: path.join(ART, 'simulator_out_of_domain.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('event report from the workspace header', async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto('/overview');
  await page.getByText('Brent crude jumps 8% after OPEC+ announces surprise output cut').first().click();
  await page.getByRole('button', { name: /Generate report/ }).click();
  await expect(page).toHaveURL(/\/reports\/rep_/, { timeout: 60_000 });
  await expect(page.locator('section[data-section]')).toHaveCount(12);
  // market section is either filled with provider data or explicitly unavailable with a reason (depends on configuration)
  const market = page.locator('section[data-section="historical_market_behaviour"]');
  await expect(market).toBeVisible();
  await expect(market.getByText(/AVAILABLE|PARTIAL|UNAVAILABLE/i).first()).toBeVisible();
  await page.screenshot({ path: path.join(ART, 'event_report.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('demo mode is explicit and labelled', async ({ page }) => {
  await page.addInitScript(() => { localStorage.setItem('xyz_demo_mode', 'true'); });
  await page.goto('/overview');
  await expect(page.getByText(/DEMO DATA/).first()).toBeVisible();
  await expect(page.getByText(/DEMO MODE: fictional data/)).toBeVisible();
});
