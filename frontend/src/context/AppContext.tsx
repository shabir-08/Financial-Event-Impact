import React, { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react';
import { EventSummary } from '../types/live';
import { eventsApi } from '../services/eventsApi';
import { errorMessage } from '../services/http';

type LoadState = 'idle' | 'loading' | 'ok' | 'error';

interface AppContextType {
  selectedEventId: string;
  setSelectedEventId: (id: string) => void;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  groundingLogicCollapsed: boolean;
  toggleGroundingLogic: () => void;
  selectedNodeId: string;
  setSelectedNodeId: (id: string) => void;
  selectedEdition: string;
  setSelectedEdition: (edition: string) => void;
  toastMessage: string | null;
  showToast: (msg: string) => void;
  /** Explicit, persisted demo mode: pages render labelled fictional data instead of backend responses. */
  demoMode: boolean;
  setDemoMode: (on: boolean) => void;
  /** Live events from GET /api/events (real ids). */
  events: EventSummary[];
  eventsState: LoadState;
  eventsError: string | null;
  reloadEvents: () => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);
const DEMO_KEY = 'xyz_demo_mode';
const DEMO_DEFAULT_EVENT = 'evt_strait_disruption';
const SELECTED_KEY = 'xyz_selected_event'; // live selection survives reloads / direct links

const readDemo = (): boolean => {
  try { return localStorage.getItem(DEMO_KEY) === 'true'; } catch { return false; }
};

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [demoMode, setDemoModeState] = useState<boolean>(readDemo);
  const [selectedEventId, setSelectedEventIdState] = useState<string>(() => {
    if (readDemo()) return DEMO_DEFAULT_EVENT;
    try { return localStorage.getItem(SELECTED_KEY) ?? ''; } catch { return ''; }
  });
  const setSelectedEventId = useCallback((id: string) => {
    setSelectedEventIdState(id);
    if (!readDemo()) { try { localStorage.setItem(SELECTED_KEY, id); } catch { /* session only */ } }
  }, []);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [groundingLogicCollapsed, setGroundingLogicCollapsed] = useState<boolean>(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string>('');
  const [selectedEdition, setSelectedEdition] = useState<string>('Global');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [eventsState, setEventsState] = useState<LoadState>('idle');
  const [eventsError, setEventsError] = useState<string | null>(null);

  const reloadEvents = useCallback(() => {
    // Background refreshes keep the current list visible (no flash back to "loading").
    setEventsState((st) => (st === 'ok' ? 'ok' : 'loading'));
    setEventsError(null);
    eventsApi.list()
      .then((items) => {
        setEvents(items);
        setEventsState('ok');
        // default selection: the first event that has an analysis run
        setSelectedEventIdState((cur) => (cur && items.some((e) => e.id === cur) ? cur
          : items.find((e) => e.latest_analysis_id)?.id ?? items[0]?.id ?? ''));
      })
      .catch((e) => {
        setEventsError(errorMessage(e));
        setEventsState((st) => (st === 'ok' ? 'ok' : 'error')); // a failed refresh keeps the last good list
      });
  }, []);

  useEffect(() => { if (!demoMode) reloadEvents(); }, [demoMode, reloadEvents]);

  const setDemoMode = (on: boolean) => {
    try { localStorage.setItem(DEMO_KEY, String(on)); } catch { /* storage unavailable: session only */ }
    setDemoModeState(on);
    setSelectedEventIdState(on ? DEMO_DEFAULT_EVENT : (() => { try { return localStorage.getItem(SELECTED_KEY) ?? ''; } catch { return ''; } })());
    setSelectedNodeId(on ? 'node_freight' : '');
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  return (
    <AppContext.Provider
      value={{
        selectedEventId,
        setSelectedEventId,
        sidebarCollapsed,
        toggleSidebar: () => setSidebarCollapsed((p) => !p),
        setSidebarCollapsed,
        groundingLogicCollapsed,
        toggleGroundingLogic: () => setGroundingLogicCollapsed((p) => !p),
        selectedNodeId,
        setSelectedNodeId,
        selectedEdition,
        setSelectedEdition,
        toastMessage,
        showToast,
        demoMode,
        setDemoMode,
        events,
        eventsState,
        eventsError,
        reloadEvents,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = (): AppContextType => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
