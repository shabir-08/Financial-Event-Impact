import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { AuthProvider } from './context/AuthContext';
import { AppShell } from './components/layout/AppShell';

import { LandingPage } from './pages/LandingPage';
import { OverviewPage } from './pages/OverviewPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { PropagationPathPage } from './pages/PropagationPathPage';
import { EventLineagePage } from './pages/EventLineagePage';
import { MarketAnalysisPage } from './pages/MarketAnalysisPage';
import { EvidencePage } from './pages/EvidencePage';
import { SavedAnalysesPage } from './pages/SavedAnalysesPage';
import { DemoOverviewPage } from './pages/demo/DemoOverviewPage';
import { DemoWorkspacePage } from './pages/demo/DemoWorkspacePage';
import { DemoPropagationPathPage } from './pages/demo/DemoPropagationPathPage';
import { DemoMarketAnalysisPage } from './pages/demo/DemoMarketAnalysisPage';
import { DemoEvidencePage } from './pages/demo/DemoEvidencePage';
import { DemoSavedAnalysesPage } from './pages/demo/DemoSavedAnalysesPage';
import { useApp } from './context/AppContext';
import { ReportPage, ReportsListPage } from './pages/ReportPage';
import { SettingsPage } from './pages/SettingsPage';
import { BlackSwanSimulatorPage } from './pages/BlackSwanSimulatorPage';

/** Live page by default; the labelled demo page only when Demo mode is switched on. */
const Mode: React.FC<{ live: React.ReactElement; demo: React.ReactElement }> = ({ live, demo }) => (useApp().demoMode ? demo : live);

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppProvider>
          <Routes>
            {/* Public Landing Page */}
            <Route path="/" element={<LandingPage />} />

            {/* Authenticated Global Shell */}
            <Route element={<AppShell />}>
              <Route path="/overview" element={<Mode live={<OverviewPage />} demo={<DemoOverviewPage />} />} />
              <Route path="/workspace" element={<Mode live={<WorkspacePage />} demo={<DemoWorkspacePage />} />} />
              <Route path="/black-swan" element={<BlackSwanSimulatorPage />} />
              <Route path="/propagation-path" element={<Mode live={<PropagationPathPage />} demo={<DemoPropagationPathPage />} />} />
              <Route path="/lineage" element={<EventLineagePage />} />
              <Route path="/market-analysis" element={<Mode live={<MarketAnalysisPage />} demo={<DemoMarketAnalysisPage />} />} />
              <Route path="/evidence" element={<Mode live={<EvidencePage />} demo={<DemoEvidencePage />} />} />
              <Route path="/saved-analyses" element={<Mode live={<SavedAnalysesPage />} demo={<DemoSavedAnalysesPage />} />} />
              <Route path="/reports" element={<ReportsListPage />} />
              <Route path="/reports/:reportId" element={<ReportPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppProvider>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
