import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const UserMenu: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleAccountSettings = () => {
    setIsOpen(false);
    navigate('/settings');
  };

  const handleSignOut = () => {
    setIsOpen(false);
    logout();
    navigate('/');
  };

  return (
    <div className="relative" ref={menuRef}>
      {/* User Symbol Icon Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-center w-8 h-8 rounded-full border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors shadow-2xs focus:outline-none"
        aria-label="User account menu"
      >
        <User size={16} className="text-gray-600" />
      </button>

      {/* Dropdown Menu matching Image 4 */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-xl shadow-xl py-1.5 z-50 animate-in fade-in zoom-in-95">
          <div className="px-3.5 py-2 border-b border-gray-100">
            <p className="text-xs font-bold text-gray-900 truncate">
              {user?.username || user?.name || 'Guest'}
            </p>
            <p className="text-[11px] text-gray-500 truncate">
              {user?.email || 'harshad.patankar@xyz.finance'}
            </p>
          </div>

          <button
            onClick={handleAccountSettings}
            className="w-full flex items-center space-x-2.5 px-3.5 py-2.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors text-left"
          >
            <User size={15} className="text-gray-500" />
            <span>Account Settings</span>
          </button>

          <button
            onClick={handleSignOut}
            className="w-full flex items-center space-x-2.5 px-3.5 py-2.5 text-xs font-semibold text-red-600 hover:bg-red-50 transition-colors text-left"
          >
            <LogOut size={15} className="text-red-600" />
            <span>Sign out</span>
          </button>
        </div>
      )}
    </div>
  );
};
