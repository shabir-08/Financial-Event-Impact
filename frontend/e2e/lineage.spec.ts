import { expect, Page, test } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

/** Event Lineage page against the running backend (:8000) and frontend (E2E_BASE_URL). */
const ART = path.join(path.dirname(fileURLToPath(import.meta.url)), 'artifacts');
fs.mkdirSync(ART, { recursive: true });

function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
  return errors;
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { localStorage.setItem('xyz_demo_mode', 'false'); });
});

async function pick(page: Page, re: RegExp) {
  const select = page.locator('#event-picker');
  await expect(select.locator('option').first()).toBeAttached({ timeout: 30_000 });
  const label = (await select.locator('option').allTextContents()).find((t) => re.test(t));
  expect(label, `no event matching ${re}`).toBeTruthy();
  await select.selectOption({ label: label! });
}

test('real analysed event shows its merged graph and an honest lineage status', async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto('/lineage');
  await expect(page.getByText('EVENT LINEAGE').first()).toBeVisible();
  await pick(page, /^Sensex and Nifty/);
  await expect(page.getByText('Merged event graph')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('lineage-graph').locator('canvas').first()).toBeAttached();
  await expect(page.getByText('Timeline')).toBeVisible();
  await expect(page.getByText(/Links do not establish causation/)).toBeVisible();
  // current data has no qualifying related events: the page must say so instead of inventing links
  await expect(page.getByText(/No related events found|Why these events are linked/).first()).toBeVisible();
  await page.screenshot({ path: path.join(ART, 'lineage_real.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('simulated event is reported as unavailable, not filled with demo data', async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto('/lineage');
  await pick(page, /\[simulated\]/);
  await expect(page.getByText(/simulated events are excluded from lineage/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Merged event graph')).toHaveCount(0);
  await page.screenshot({ path: path.join(ART, 'lineage_simulated.png'), fullPage: true });
  expect(errors).toEqual([]);
});
