import { expect, test } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const ART = path.join(path.dirname(fileURLToPath(import.meta.url)), 'artifacts');

test('overview offers publisher RSS sources and lists live (non-simulated) events', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('xyz_demo_mode', 'false'));
  await page.goto('/overview');
  await expect(page.getByRole('button', { name: /Publisher RSS feeds/ })).toBeVisible();
  for (const name of ['Hindustan Times - India', 'BBC News - Business', 'Bloomberg - Markets', 'Economic Times - Markets']) {
    await expect(page.getByLabel(name)).toBeChecked();
  }
  await expect(page.getByText('FII Selloff in Indian Equities Intensifies').first()).toBeVisible();
  await page.screenshot({ path: path.join(ART, 'overview_rss.png'), fullPage: false });
});
