import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useApp } from '../../context/AppContext';
import { AuthModal } from '../auth/AuthModal';

export const AppShell: React.FC = () => {
  const { sidebarCollapsed, toastMessage } = useApp();

  return (
    <div className="min-h-screen bg-[#F9FAFB] flex flex-col">
      {/* Collapsible Left Sidebar */}
      <Sidebar />

      {/* Main Content Area that reclaims horizontal space */}
      <div
        className={`flex-1 flex flex-col transition-all duration-300 ${
          sidebarCollapsed ? 'ml-16' : 'ml-64'
        }`}
      >
        <main className="flex-1 flex flex-col min-w-0">
          <Outlet />
        </main>
      </div>

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-5 right-5 z-50 bg-gray-900 text-white px-4 py-2.5 rounded-lg shadow-xl text-xs font-medium flex items-center space-x-2 animate-in fade-in slide-in-from-bottom-2">
          <span className="w-2 h-2 rounded-full bg-blue-400"></span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Global Auth Modal */}
      <AuthModal />
    </div>
  );
};
