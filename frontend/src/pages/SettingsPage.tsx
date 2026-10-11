import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Mail, Lock, AlertTriangle, ShieldCheck, CheckCircle2, Loader2, X, LogOut } from 'lucide-react';
import { Header } from '../components/layout/Header';
import { useAuth } from '../context/AuthContext';
import { useApp } from '../context/AppContext';
import { apiClient } from '../services/apiClient';

export const SettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, updateProfile, logout } = useAuth();
  const { showToast, demoMode, setDemoMode } = useApp();

  const [username, setUsername] = useState(user?.username || '');
  const [email, setEmail] = useState(user?.email || 'harshad.patankar@xyz.finance');
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [confirmPassword, setConfirmPassword] = useState('');
  const [resetError, setResetError] = useState<string | null>(null);
  const [isResetting, setIsResetting] = useState(false);

  const handleLogout = () => {
    logout();
    showToast('Logged out successfully.');
    navigate('/');
  };

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    updateProfile({ username, email });
    showToast('Account details updated successfully.');
  };

  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetError(null);

    if (!confirmPassword) {
      setResetError('Please enter your current password to confirm.');
      return;
    }

    setIsResetting(true);
    try {
      const result = await apiClient.resetUserCredentials(confirmPassword);
      if (result.success) {
        showToast(result.message);
        setIsResetModalOpen(false);
        setConfirmPassword('');
      } else {
        setResetError(result.message);
      }
    } catch {
      setResetError('Failed to verify password with backend.');
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB]">
      <Header
        title="Account Settings"
        tag="USER PROFILE & PREFERENCES"
        subtitle="Manage authenticated identity, credentials, and scenario research preferences"
        showActions={false}
      />

      <div className="p-6 max-w-2xl mx-auto w-full">
        <div className="mb-5 bg-white border border-gray-200 rounded-2xl p-5 text-xs space-y-2">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-extrabold text-gray-950">Demo mode</p>
              <p className="text-gray-500">Shows fictional demo events, graphs and prices for presentations, labelled DEMO DATA on every page. Off = live backend data only.</p>
            </div>
            <button onClick={() => setDemoMode(!demoMode)} role="switch" aria-checked={demoMode}
                    className={`px-3 py-1.5 rounded-lg border font-bold cursor-pointer ${demoMode ? 'bg-amber-50 border-amber-300 text-amber-900' : 'bg-white border-gray-300 text-gray-700'}`}>
              {demoMode ? 'Demo mode ON' : 'Demo mode OFF'}
            </button>
          </div>
        </div>
        {/* Account Settings Card (faithfully matching hand-drawn sketch media_1791703262931.png) */}
        <div className="bg-white border border-gray-200 rounded-2xl p-8 shadow-2xs space-y-6">
          <div className="flex items-center space-x-3 pb-4 border-b border-gray-100">
            <div className="w-12 h-12 rounded-full bg-blue-100 border border-blue-200 text-blue-700 font-extrabold text-base flex items-center justify-center">
              {username.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <h2 className="text-xl font-extrabold text-gray-950 tracking-tight">Account Settings</h2>
              <p className="text-xs text-gray-500">Identity and authentication credentials</p>
            </div>
          </div>

          <form onSubmit={handleSaveProfile} className="space-y-5">
            {/* Username with User Icon */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                Username
              </label>
              <div className="relative">
                <User className="absolute left-3.5 top-2.5 text-gray-400" size={17} />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Username"
                  required
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-xs font-medium focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                />
              </div>
            </div>

            {/* Email with Mail Icon */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-2.5 text-gray-400" size={17} />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Email"
                  required
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-xs font-medium focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                />
              </div>
            </div>

            {/* Password (Masked with Lock Icon) */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-2.5 text-gray-400" size={17} />
                <input
                  type="password"
                  value="••••••••••••"
                  disabled
                  readOnly
                  className="w-full pl-10 pr-4 py-2 border border-gray-200 bg-gray-50/70 rounded-lg text-xs font-mono text-gray-500 cursor-not-allowed"
                />
              </div>
              <span className="text-[11px] text-gray-400 mt-1 block">
                Existing password is encrypted and never transmitted in plaintext.
              </span>
            </div>

            {/* Action Buttons: Save on left, Reset Button on right (matching sketch) */}
            <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
              <button
                type="submit"
                className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-2xs transition-colors cursor-pointer"
              >
                Save Changes
              </button>

              <button
                type="button"
                onClick={() => setIsResetModalOpen(true)}
                className="px-5 py-2 border border-red-200 text-red-600 hover:bg-red-50 text-xs font-bold rounded-lg transition-colors shadow-2xs cursor-pointer"
              >
                Reset
              </button>
            </div>

            {/* Log Out button below Save Changes */}
            <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
              <button
                type="button"
                onClick={handleLogout}
                className="flex items-center space-x-2 px-5 py-2 border border-red-300 bg-red-50/50 hover:bg-red-100/70 text-red-600 rounded-lg text-xs font-bold transition-colors shadow-2xs cursor-pointer"
              >
                <LogOut size={14} />
                <span>Log out</span>
              </button>
              <span className="text-[11px] text-gray-400">
                End active session on this device
              </span>
            </div>
          </form>
        </div>
      </div>

      {/* Mandatory Password Confirmation Modal for Reset Operation (Section 17) */}
      {isResetModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
            onClick={() => setIsResetModalOpen(false)}
          />

          <div className="relative z-10 w-full max-w-md bg-white rounded-xl shadow-2xl border border-gray-200 p-6 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100 mb-4">
              <div className="flex items-center space-x-2 text-red-600 font-bold text-sm">
                <AlertTriangle size={18} />
                <span>Confirm Reset Action</span>
              </div>
              <button
                onClick={() => setIsResetModalOpen(false)}
                className="p-1 rounded text-gray-400 hover:text-gray-700"
              >
                <X size={16} />
              </button>
            </div>

            <p className="text-xs text-gray-600 leading-relaxed mb-4">
              Resetting credentials will clear local authorization sessions and reset demo research cache. To confirm this action, please enter your current password below.
            </p>

            {resetError && (
              <div className="mb-4 p-2.5 bg-red-50 border border-red-200 rounded-md text-xs text-red-600 font-medium">
                {resetError}
              </div>
            )}

            <form onSubmit={handleConfirmReset} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Current Password
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Enter current password"
                  required
                  autoFocus
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-red-500 focus:border-red-500 outline-none"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsResetModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-gray-600 hover:text-gray-900"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isResetting}
                  className="px-5 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-md shadow-2xs transition-colors flex items-center space-x-1.5 disabled:opacity-50"
                >
                  {isResetting && <Loader2 size={13} className="animate-spin" />}
                  <span>Confirm Reset</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
