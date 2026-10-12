import { expect, Page, test } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

/** "Save" in the workspace header -> Stored Analyses (live backend). Removes its own entry at the end. */
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

test('save an analysis from the workspace, see it in Stored Analyses with its report, then remove it', async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto('/workspace');
  const select = page.locator('#event-picker');
  await expect(select.locator('option').first()).toBeAttached({ timeout: 30_000 });
  const label = (await select.locator('option').allTextContents()).find((t) => /^Sensex and Nifty/.test(t));
  if (label) await select.selectOption({ label });
  const title = (label ?? (await select.locator('option:checked').textContent()) ?? '').replace(' [simulated]', '');

  const save = page.getByRole('button', { name: /^(Save|Saved)$/ });
  await expect(save).toBeVisible({ timeout: 30_000 });
  await expect(save).toBeEnabled({ timeout: 30_000 });  // saved status loaded
  if ((await save.getAttribute('aria-pressed')) === 'true') {  // leftover from an earlier run: start clean
    await save.click();
    await expect(save).toHaveAttribute('aria-pressed', 'false', { timeout: 30_000 });
  }
  await save.click();
  await expect(save).toHaveAttribute('aria-pressed', 'true', { timeout: 60_000 });
  await expect(save).toHaveText('Saved');
  await page.screenshot({ path: path.join(ART, 'save_button.png') });

  await page.goto('/saved-analyses');
  await expect(page.getByRole('heading', { name: 'Saved analyses' })).toBeVisible();
  const card = page.locator('div.rounded-xl', { hasText: title }).filter({ has: page.getByText('Open in workspace') }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card.getByText('View saved report')).toBeVisible();
  await page.screenshot({ path: path.join(ART, 'stored_analyses.png'), fullPage: true });

  await card.getByText('View saved report').click();
  await expect(page).toHaveURL(/\/reports\/rep_/);
  await expect(page.getByText('Executive Summary').first()).toBeVisible({ timeout: 30_000 });

  await page.goto('/saved-analyses');
  await page.locator('div.rounded-xl', { hasText: title }).getByTitle('Remove from saved').first().click();
  await expect(page.getByText(/Nothing saved yet/)).toBeVisible({ timeout: 30_000 });
  expect(errors).toEqual([]);
});
