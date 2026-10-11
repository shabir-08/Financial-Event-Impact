import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  // testTimeout: page tests import whole pages (three.js, cytoscape), which can exceed 5s on a loaded machine
  test: { environment: 'jsdom', include: ['src/test/**/*.test.{ts,tsx}'], testTimeout: 30000 },
});
