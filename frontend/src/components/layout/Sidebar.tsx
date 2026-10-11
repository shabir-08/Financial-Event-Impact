import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Network,
  Activity,
  GitFork,
  LineChart,
  BookOpen,
  BookmarkCheck,
  Settings,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  FileText,
  GitMerge,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';

export const Sidebar: React.FC = () => {
  const { sidebarCollapsed, toggleSidebar, demoMode } = useApp();
  const { user } = useAuth();
  const location = useLocation();

  const navItems = [
    { name: 'Overview', path: '/overview', icon: LayoutDashboard },
    { name: 'Analysis Workspace', path: '/workspace', icon: Network },
    { name: 'Black Swan Simulator', path: '/black-swan', icon: Activity },
    { name: 'Propagation Path', path: '/propagation-path', icon: GitFork },
    { name: 'Event Lineage', path: '/lineage', icon: GitMerge },
    { name: 'Market Analysis', path: '/market-analysis', icon: LineChart },
    { name: 'Evidence & Sources', path: '/evidence', icon: BookOpen },
    { name: 'Stored Analyses', path: '/saved-analyses', icon: BookmarkCheck },
    { name: 'Reports', path: '/reports', icon: FileText },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <aside
      className={`fixed top-0 left-0 bottom-0 z-30 flex flex-col bg-white border-r border-gray-200 transition-all duration-300 select-none ${
        sidebarCollapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="h-16 px-4 flex items-center justify-between border-b border-gray-100">
        {!sidebarCollapsed ? (
          <NavLink to="/" className="flex flex-col hover:opacity-80 transition-opacity">
            <div className="flex items-center space-x-2">
              <span className="font-extrabold text-2xl tracking-tight text-gray-950 font-sans">XYZ</span>
            </div>
            <span className="text-[9px] font-semibold tracking-wider text-gray-500 uppercase -mt-1">
              INTELLIGENCE PLATFORM
            </span>
          </NavLink>
        ) : (
          <NavLink to="/" className="font-extrabold text-xl tracking-tight text-gray-950 mx-auto hover:opacity-80 transition-opacity">
            XYZ
          </NavLink>
        )}

        <button
          onClick={toggleSidebar}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="p-1.5 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
        >
          {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {demoMode && !sidebarCollapsed && (
        <NavLink to="/settings" className="mx-3 mt-3 px-2 py-1.5 rounded-md border border-amber-300 bg-amber-50 text-amber-900 text-[11px] font-bold text-center">
          DEMO MODE: fictional data
        </NavLink>
      )}
      {/* Navigation List */}
      <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path || (item.path === '/workspace' && location.pathname === '/');

          return (
            <NavLink
              key={item.name}
              to={item.path}
              title={sidebarCollapsed ? item.name : undefined}
              className={({ isActive: navActive }) => {
                const active = navActive || isActive;
                return `group relative flex items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  active
                    ? 'bg-blue-50 text-blue-700 font-semibold border-l-4 border-blue-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-950 hover:bg-gray-50'
                } ${sidebarCollapsed ? 'justify-center px-0' : ''}`;
              }}
            >
              <Icon
                size={18}
                className={`flex-shrink-0 transition-colors ${
                  isActive ? 'text-blue-600' : 'text-gray-400 group-hover:text-gray-700'
                } ${!sidebarCollapsed ? 'mr-3' : ''}`}
              />

              {!sidebarCollapsed && <span className="truncate">{item.name}</span>}

              {/* Hover Tooltip when collapsed */}
              {sidebarCollapsed && (
                <div className="absolute left-full ml-3 px-2.5 py-1 bg-gray-900 text-white text-xs rounded-md shadow-md opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity">
                  {item.name}
                </div>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Bottom Profile */}
      <div className="p-3 border-t border-gray-100 bg-gray-50/50">
        {!sidebarCollapsed ? (
          <div className="flex items-center space-x-3 px-2 py-1">
            <div className="w-8 h-8 rounded-full bg-blue-100 border border-blue-200 text-blue-700 font-bold text-xs flex items-center justify-center flex-shrink-0">
              {user?.username?.slice(0, 2).toUpperCase() || '?'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-gray-900 truncate">
                {user?.name || user?.username || 'Guest'}
              </p>
              <p className="text-[11px] text-gray-500 truncate">
                {user?.role || 'Not signed in'}
              </p>
            </div>
          </div>
        ) : (
          <div className="flex justify-center group relative">
            <div className="w-8 h-8 rounded-full bg-blue-100 border border-blue-200 text-blue-700 font-bold text-xs flex items-center justify-center">
              {user?.username?.slice(0, 2).toUpperCase() || 'AL'}
            </div>
            <div className="absolute left-full ml-3 px-2.5 py-1 bg-gray-900 text-white text-xs rounded-md shadow-md opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity">
              {user?.name || 'Alex Lee'} · Research team
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
