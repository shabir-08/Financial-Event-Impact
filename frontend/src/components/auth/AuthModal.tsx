import React from 'react';
import { X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { LoginForm } from './LoginForm';
import { CreateAccountForm } from './CreateAccountForm';

export const AuthModal: React.FC = () => {
  const { authModalOpen, authModalMode, closeAuthModal, openRegisterModal, openLoginModal } = useAuth();

  if (!authModalOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Blurred & Dimmed Backdrop (Preserving background view as seen in reference screenshots) */}
      <div
        className="fixed inset-0 bg-slate-900/60 backdrop-blur-md transition-opacity"
        onClick={closeAuthModal}
      />

      {/* Modal Dialog Card */}
      <div className="relative z-10 w-full max-w-md bg-white rounded-xl shadow-2xl border border-gray-200 p-8 transform transition-all animate-in fade-in zoom-in-95">
        <button
          onClick={closeAuthModal}
          aria-label="Close modal"
          className="absolute right-5 top-5 p-1 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
        >
          <X size={18} />
        </button>

        {authModalMode === 'login' ? (
          <LoginForm onSwitchToRegister={() => openRegisterModal()} />
        ) : (
          <CreateAccountForm onSwitchToLogin={() => openLoginModal()} />
        )}
      </div>
    </div>
  );
};
