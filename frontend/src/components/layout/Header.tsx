import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  ArrowLeft,
  Bookmark,
  Download,
  CheckCircle2,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { generateAnalysisPdf } from '../../services/pdfService';
import { UserMenu } from './UserMenu';
import {
  DEMO_EVENTS,
  DEMO_GRAPH_NODES,
  DEMO_GRAPH_EDGES,
  DEMO_GROUNDING_LOGIC,
  DEMO_PROPAGATION_PATHS,
  DEMO_EVIDENCE_RELATIONSHIPS,
  DEMO_MARKET_DATA
} from '../../services/demoData';

interface HeaderProps {
  title?: string;
  tag?: string;
  subtitle?: string;
  showActions?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  tag = 'GLOBAL TRADE / SCENARIO ANALYSIS',
  subtitle,
  showActions = true,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedEventId, showToast, demoMode, events } = useApp();
  const { isBackendConnected } = useAuth();
  const [isSaved, setIsSaved] = useState(() => {
    return localStorage.getItem(`xyz_saved_${selectedEventId}`) === 'true';
  });
  const [isExporting, setIsExporting] = useState(false);

  const currentEvent = DEMO_EVENTS.find(e => e.id === selectedEventId) || DEMO_EVENTS[0];
  const liveEvent = events.find((e) => e.id === selectedEventId);
  const displayTitle = title || (demoMode ? currentEvent.headline : liveEvent?.title ?? '');

  // Handle Back Navigation
  const handleBack = () => {
    if (window.history.length > 2 && location.pathname !== '/overview') {
      navigate(-1);
    } else {
      navigate('/overview');
    }
  };

  // Bookmark: stored only in this browser (the backend has no bookmark / saved-analysis storage).
  const handleSave = async () => {
    const nextSavedState = !isSaved;
    setIsSaved(nextSavedState);
    try { localStorage.setItem(`xyz_saved_${selectedEventId}`, String(nextSavedState)); } catch { /* ignore */ }
    showToast(nextSavedState ? 'Bookmarked in this browser only (not stored by the backend).' : 'Bookmark removed.');
  };

  // Demo-mode PDF of the fictional demo constants (labelled DEMO DATA). Live reports: see the Reports page.
  const handleExportPdf = async () => {
    setIsExporting(true);
    showToast('Compiling analysis report and generating PDF...');
    try {
      await generateAnalysisPdf({
        event: currentEvent,
        nodes: DEMO_GRAPH_NODES,
        edges: DEMO_GRAPH_EDGES,
        groundingLogic: DEMO_GROUNDING_LOGIC['node_freight'] || null,
        propagationPaths: DEMO_PROPAGATION_PATHS,
        evidence: DEMO_EVIDENCE_RELATIONSHIPS,
        marketData: DEMO_MARKET_DATA,
      });
      showToast('PDF downloaded successfully.');
    } catch (err) {
      console.error(err);
      showToast('Error generating PDF report.');
    } finally {
      setIsExporting(false);
    }
  };

  const editions = ['Global', 'India edition', 'USA edition', 'EU edition'];

  return (
    <header className="sticky top-0 z-20 bg-white/95 backdrop-blur-sm border-b border-gray-200 px-6 py-3 transition-all">
      <div className="flex items-center justify-between gap-4">
        {/* Left Side: Context Title */}
        <div className="flex items-start min-w-0">
          <div className="min-w-0">
            {tag && (
              <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block">
                {tag}
              </span>
            )}
            <h1 className="text-xl font-extrabold text-gray-950 tracking-tight truncate">
              {displayTitle}
            </h1>
            {subtitle && (
              <p className="text-xs text-gray-500 mt-0.5 font-medium">
                {subtitle}
              </p>
            )}
          </div>
        </div>

        {/* Right Side: User Menu and Action Buttons */}
        <div className="flex items-center space-x-3 flex-shrink-0">
          {/* User Menu Dropdown (matching image 4) */}
          <UserMenu />

          {/* Actions: Save & Export to PDF */}
          {showActions && !demoMode && liveEvent?.latest_analysis_id && (
            <button
              onClick={() => navigate(`/reports/new?kind=event&source=${liveEvent.latest_analysis_id}`)}
              className="flex items-center space-x-1.5 px-3.5 py-1.5 bg-white border border-gray-300 hover:border-gray-400 hover:bg-gray-50 text-gray-800 text-xs font-semibold rounded-lg shadow-2xs transition-all"
            >
              <Download size={14} className="text-gray-500" />
              <span>Generate report</span>
            </button>
          )}
          {showActions && demoMode && (
            <div className="flex items-center space-x-2">
              <button
                onClick={handleSave}

                title={isSaved ? 'Bookmarked in this browser (click to remove)' : 'Bookmark in this browser (not stored by the backend)'}
                className={`group relative p-2 rounded-lg border transition-all duration-300 cursor-pointer disabled:opacity-50 ${
                  isSaved
                    ? 'border-blue-400 bg-blue-50/60 shadow-2xs'
                    : 'border-gray-200 text-gray-500 hover:text-blue-600 hover:border-blue-300 hover:bg-blue-50/40'
                }`}
              >
                <div className="relative w-4 h-4 flex items-center justify-center overflow-hidden">
                  {/* Empty Icon Outline */}
                  <Bookmark
                    size={16}
                    className={`transition-colors duration-500 ${
                      isSaved ? 'text-[#2563EB]' : 'text-gray-500 group-hover:text-blue-600'
                    }`}
                  />

                  {/* Slowly / Smoothly Filling Blue Layer */}
                  <div
                    className="absolute inset-0 pointer-events-none transition-[clip-path] duration-700 ease-out"
                    style={{
                      clipPath: isSaved ? 'inset(0% 0% 0% 0%)' : 'inset(100% 0% 0% 0%)',
                    }}
                  >
                    <Bookmark
                      size={16}
                      className="text-[#2563EB] fill-[#2563EB]"
                    />
                  </div>
                </div>
              </button>

              <button
                onClick={handleExportPdf}
                disabled={isExporting}
                className="flex items-center space-x-1.5 px-3.5 py-1.5 bg-white border border-gray-300 hover:border-gray-400 hover:bg-gray-50 text-gray-800 text-xs font-semibold rounded-lg shadow-2xs transition-all disabled:opacity-50"
              >
                <Download size={14} className="text-gray-500" />
                <span>{isExporting ? 'Exporting...' : 'Export to PDF'}</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
