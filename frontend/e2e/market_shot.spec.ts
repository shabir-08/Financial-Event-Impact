import { expect, test } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const ART = path.join(path.dirname(fileURLToPath(import.meta.url)), 'artifacts');

test('market analysis renders provider price charts when a provider is configured', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('xyz_demo_mode', 'false'));
  await page.goto('/overview');
  await page.getByText('Brent crude jumps 8% after OPEC+ announces surprise output cut').first().click();
  await page.goto('/market-analysis');
  await expect(page.getByText(/Market-data provider:/)).toBeVisible({ timeout: 60_000 }); // live provider fetch for several assets
  await expect(page.locator('.recharts-line').first()).toBeVisible({ timeout: 60_000 });
  await page.screenshot({ path: path.join(ART, 'market_live.png'), fullPage: false });
});
