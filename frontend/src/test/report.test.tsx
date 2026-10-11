import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AppProvider } from '../context/AppContext';
import { AuthProvider } from '../context/AuthContext';
import { ReportView, ReportPage } from '../pages/ReportPage';
import { buildReportPdf, pdfSafe } from '../services/reportPdf';
import { Report } from '../types/report';
import eventReport from './fixtures/report_event.json';
import simReport from './fixtures/report_simulation.json';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const ev = eventReport as unknown as Report;
const sim = simReport as unknown as Report;

describe('report rendering', () => {
  it('renders all 12 sections with statuses and unavailable reasons', () => {
    render(<MemoryRouter><ReportView report={ev} /></MemoryRouter>);
    expect(document.querySelectorAll('section[data-section]').length).toBe(12);
    const unavailable = ev.sections.filter((s) => s.status === 'unavailable');
    expect(unavailable.length).toBeGreaterThan(0);
    unavailable.forEach((s) => expect(screen.getAllByText((t) => t.includes(s.unavailable_reason!.slice(0, 40))).length).toBeGreaterThan(0));
    expect(screen.getByText('SIMULATED')).toBeTruthy();
  });

  it('labels simulation reports as hypothetical and shows estimates or "unavailable"', () => {
    render(<MemoryRouter><ReportView report={sim} /></MemoryRouter>);
    expect(screen.getByText('HYPOTHETICAL SCENARIO')).toBeTruthy();
    const ml = sim.sections.find((s) => s.key === 'ml_predictions')!;
    if (ml.status !== 'unavailable') expect(screen.getAllByText(/Estimate \(5 trading days\)/).length).toBe(1);
  });

  it('report page loads a stored report by id and shows API errors explicitly', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => (String(url).includes('/api/reports/')
      ? { ok: true, status: 200, json: async () => ev } : { ok: true, status: 200, json: async () => ({ items: [] }) }) as unknown as Response));
    render(<MemoryRouter initialEntries={[`/reports/${ev.report_id}`]}><AuthProvider><AppProvider>
      <Routes><Route path="/reports/:reportId" element={<ReportPage />} /></Routes></AppProvider></AuthProvider></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('Export PDF')).toBeTruthy());
    cleanup();
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 404, json: async () => ({ error: { message: 'report rep_x not found' } }) }) as unknown as Response));
    render(<MemoryRouter initialEntries={['/reports/rep_x']}><AuthProvider><AppProvider>
      <Routes><Route path="/reports/:reportId" element={<ReportPage />} /></Routes></AppProvider></AuthProvider></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/report rep_x not found/)).toBeTruthy());
  });
});

describe('PDF export', () => {
  for (const [name, rep] of [['event', ev], ['simulation', sim]] as const) {
    it(`${name} PDF contains the report's own data and no demo constants`, () => {
      const out = buildReportPdf(rep).output();
      expect(out).toContain(pdfSafe(rep.report_id));
      rep.sections.forEach((s) => expect(out).toContain(pdfSafe(s.title).slice(0, 20)));
      rep.sections.filter((s) => s.status === 'unavailable')
        .forEach((s) => expect(out).toContain(pdfSafe(s.unavailable_reason!).slice(0, 30)));
      for (const demo of ['XYZ FINANCIAL INTELLIGENCE', 'Strait', 'CONFIDENTIAL RESEARCH', 'Bunker']) expect(out).not.toContain(demo);
    });
  }
});
