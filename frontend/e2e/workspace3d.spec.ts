import { expect, Page, test } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

/** Analysis Workspace 3D graph against the running backend (:8000) and frontend (E2E_BASE_URL). */
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

test('workspace shows the event graph in 3D, highlights a pathway, and can switch to 2D', async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto('/workspace');
  const select = page.locator('#event-picker');
  await expect(select.locator('option').first()).toBeAttached({ timeout: 30_000 });
  const label = (await select.locator('option').allTextContents()).find((t) => /^Sensex and Nifty/.test(t));
  if (label) await select.selectOption({ label });
  await expect(page.getByText(/Top impact pathways/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole('button', { name: /3D graph/ })).toHaveAttribute('aria-pressed', 'true');
  const canvas = page.locator('canvas').first();
  await expect(canvas).toBeVisible();
  expect((await canvas.boundingBox())!.width).toBeGreaterThan(300);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(ART, 'workspace_3d.png'), fullPage: true });

  const firstPath = page.getByTitle('Highlight this pathway in the 3D graph').first();
  if (await firstPath.count()) {
    await firstPath.click();
    await expect(page.getByText(/Highlighting path #1/)).toBeVisible();
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(ART, 'workspace_3d_path.png'), fullPage: true });
  }

  await page.getByRole('button', { name: /2D graph/ }).click();
  await expect(page.getByRole('button', { name: /2D graph/ })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('canvas').first()).toBeVisible();
  expect(errors).toEqual([]);
});
