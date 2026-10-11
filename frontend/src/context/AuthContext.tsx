import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { UserProfile } from '../types/auth';
import { apiClient } from '../services/apiClient';

interface AuthContextType {
  isAuthenticated: boolean;
  user: UserProfile | null;
  isBackendConnected: boolean;
  authModalOpen: boolean;
  authModalMode: 'login' | 'register';
  redirectTarget: string | null;
  pendingEventId: string | null;
  openLoginModal: (redirectTarget?: string, pendingEventId?: string) => void;
  openRegisterModal: (redirectTarget?: string, pendingEventId?: string) => void;
  closeAuthModal: () => void;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (username: string, email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  updateProfile: (updated: Partial<UserProfile>) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// The backend has no account service: login is a local, browser-only session (labelled as such in the UI).
const USER_KEY = 'xyz_local_user';
const localUser = (email: string, name?: string): UserProfile => ({
  id: 'local', username: name || email.split('@')[0], name: name || email.split('@')[0], email,
  role: 'Local session (no backend accounts)',
});
const readUser = (): UserProfile | null => {
  try { const v = localStorage.getItem(USER_KEY); return v ? JSON.parse(v) : null; } catch { return null; }
};
const storeUser = (u: UserProfile) => { try { localStorage.setItem(USER_KEY, JSON.stringify(u)); } catch { /* session only */ } };

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return localStorage.getItem('xyz_auth_token') !== null;
  });
  const [user, setUser] = useState<UserProfile | null>(readUser);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [authModalOpen, setAuthModalOpen] = useState<boolean>(false);
  const [authModalMode, setAuthModalMode] = useState<'login' | 'register'>('login');
  const [redirectTarget, setRedirectTarget] = useState<string | null>(null);
  const [pendingEventId, setPendingEventId] = useState<string | null>(null);

  useEffect(() => {
    // Check backend health
    apiClient.checkHealth().then((connected) => {
      setIsBackendConnected(connected);
    });

  }, []);

  const openLoginModal = (target?: string, eventId?: string) => {
    setAuthModalMode('login');
    if (target) setRedirectTarget(target);
    if (eventId) setPendingEventId(eventId);
    setAuthModalOpen(true);
  };

  const openRegisterModal = (target?: string, eventId?: string) => {
    setAuthModalMode('register');
    if (target) setRedirectTarget(target);
    if (eventId) setPendingEventId(eventId);
    setAuthModalOpen(true);
  };

  const closeAuthModal = () => {
    setAuthModalOpen(false);
  };

  const login = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    if (!email || !password) {
      return { success: false, error: 'Please enter both email and password.' };
    }
    // Validation
    if (!email.includes('@')) {
      return { success: false, error: 'Please enter a valid email address.' };
    }

    localStorage.setItem('xyz_auth_token', 'demo_jwt_token_' + Date.now());
    setIsAuthenticated(true);
    setAuthModalOpen(false);

    const u = localUser(email);
    storeUser(u);
    setUser(u);

    return { success: true };
  };

  const register = async (username: string, email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    if (!username || !email || !password) {
      return { success: false, error: 'All fields are required.' };
    }
    if (password.length < 6) {
      return { success: false, error: 'Password must be at least 6 characters.' };
    }

    localStorage.setItem('xyz_auth_token', 'demo_jwt_token_' + Date.now());
    setIsAuthenticated(true);
    setAuthModalOpen(false);

    const u = localUser(email, username);
    storeUser(u);
    setUser(u);

    return { success: true };
  };

  const logout = () => {
    localStorage.removeItem('xyz_auth_token');
    setIsAuthenticated(false);
  };

  const updateProfile = (updated: Partial<UserProfile>) => {
    if (user) {
      setUser({ ...user, ...updated });
    }
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        user,
        isBackendConnected,
        authModalOpen,
        authModalMode,
        redirectTarget,
        pendingEventId,
        openLoginModal,
        openRegisterModal,
        closeAuthModal,
        login,
        register,
        logout,
        updateProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
