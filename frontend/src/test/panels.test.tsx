import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HistoricalPatternsPanel } from '../components/black-swan/HistoricalPatternsPanel';
import { ModelEstimatesPanel } from '../components/black-swan/ModelEstimatesPanel';
import { toSimulation } from '../services/blackSwanApi';
import oil from './fixtures/simulation_oil.json';
import ood from './fixtures/simulation_out_of_domain.json';
import latest from './fixtures/latest_conditions.json';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('HistoricalPatternsPanel', () => {
  it('renders analogues as historical observations with sources of each matched value', () => {
    const sim = toSimulation(oil);
    render(<HistoricalPatternsPanel patterns={sim.historical_patterns} latest={latest as any} latestError={null} />);
    expect(screen.getByText('HISTORICAL OBSERVATIONS')).toBeTruthy();
    expect(screen.getAllByText(/your assumption/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/latest observed/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Comparable weeks/)).toBeTruthy();
    expect(screen.getByText(/not causation/)).toBeTruthy();
  });

  it('shows the withheld reason instead of statistics for small samples', () => {
    const p = { ...toSimulation(oil).historical_patterns!, sample_statistics: null,
                statistics_withheld_reason: 'only 3 analogue weeks in 1 independent cluster(s)' };
    render(<HistoricalPatternsPanel patterns={p} latest={null} latestError={null} />);
    expect(screen.getByText(/Sample statistics withheld/)).toBeTruthy();
  });

  it('shows unavailable and error states', () => {
    render(<HistoricalPatternsPanel patterns={{ status: 'unavailable', reason: 'No matchable shock parameters' }}
                                    latest={null} latestError="Cannot reach the backend" />);
    expect(screen.getByText(/No historical analogue search/)).toBeTruthy();
    expect(screen.getByText(/Could not load latest conditions/)).toBeTruthy();
  });

  it('shows an empty state before any simulation', () => {
    render(<HistoricalPatternsPanel latest={null} latestError={null} />);
    expect(screen.getByText(/Run a simulation/)).toBeTruthy();
  });
});

describe('ModelEstimatesPanel', () => {
  it('shows estimates when available', () => {
    const s = toSimulation(oil);
    render(<ModelEstimatesPanel status={s.model_status} predictions={s.predictions} disclaimer={s.prediction_disclaimer} />);
    expect(screen.getByText('MODEL ESTIMATE')).toBeTruthy();
    expect(screen.getByText('Estimates available')).toBeTruthy();
  });

  it('shows "unavailable" (not 0%) when the model declines', () => {
    const s = toSimulation(ood);
    render(<ModelEstimatesPanel status={s.model_status} predictions={s.predictions} />);
    expect(screen.getByText(/Declined: inputs outside the range/)).toBeTruthy();
    expect(screen.getAllByText('unavailable').length).toBe(18);
    expect(screen.queryByText('+0.00%')).toBeNull();
  });
});

describe('BlackSwanSimulatorPage', () => {
  it('shows an explicit error (no silent demo) when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    const { BlackSwanSimulatorPage } = await import('../pages/BlackSwanSimulatorPage');
    const { AppProvider } = await import('../context/AppContext');
    const { AuthProvider } = await import('../context/AuthContext');
    render(<MemoryRouter><AuthProvider><AppProvider><BlackSwanSimulatorPage /></AppProvider></AuthProvider></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/Live simulator unavailable/)).toBeTruthy());
    expect(screen.getByText(/Open labelled demo instead/)).toBeTruthy();
    expect(screen.queryByText(/DEMO DATA/)).toBeNull();
  }, 60000); // importing the page loads three.js, which is slow under load
});
