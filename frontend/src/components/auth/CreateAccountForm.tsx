import React, { useState } from 'react';
import { User, Mail, Lock, Loader2 } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

interface CreateAccountFormProps {
  onSwitchToLogin: () => void;
}

export const CreateAccountForm: React.FC<CreateAccountFormProps> = ({ onSwitchToLogin }) => {
  const { register, redirectTarget, pendingEventId, closeAuthModal } = useAuth();
  const { setSelectedEventId } = useApp();
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const res = await register(username, email, password);
      if (res.success) {
        if (pendingEventId) {
          setSelectedEventId(pendingEventId);
        }
        closeAuthModal();

        // Exact Case A redirect: redirect to Overview page after registration
        if (redirectTarget) {
          navigate(redirectTarget);
        } else {
          navigate('/overview');
        }
      } else {
        setError(res.error || 'Failed to create account.');
      }
    } catch {
      setError('An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="mb-5">
        <span className="font-black text-2xl tracking-tight text-gray-950 font-sans">XYZ</span>
        <h2 className="text-2xl font-bold text-gray-900 mt-2">Create your account.</h2>
        <p className="text-xs text-gray-500 mt-1">
          Turn the global briefing into your own intelligence.
        </p>
      </div>

      {error && (
        <div className="mb-4 p-2.5 bg-red-50 border border-red-200 rounded-md text-xs text-red-600">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-3.5">
        {/* Username */}
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            Username
          </label>
          <div className="relative">
            <User className="absolute left-3 top-2.5 text-gray-400" size={16} />
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Choose a username"
              required
              className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all placeholder:text-gray-400"
            />
          </div>
        </div>

        {/* Email */}
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            Email
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-2.5 text-gray-400" size={16} />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all placeholder:text-gray-400"
            />
          </div>
        </div>

        {/* Password */}
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            Password
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-2.5 text-gray-400" size={16} />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Create a password"
              required
              className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all placeholder:text-gray-400"
            />
          </div>
        </div>

        {/* Confirm Password */}
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            Confirm Password
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-2.5 text-gray-400" size={16} />
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter your password"
              required
              className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all placeholder:text-gray-400"
            />
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={onSwitchToLogin}
            className="text-xs font-medium text-blue-600 hover:text-blue-800 transition-colors"
          >
            Already have an account? Sign in
          </button>

          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-md shadow-sm transition-colors flex items-center space-x-1.5 disabled:opacity-50"
          >
            {loading && <Loader2 size={13} className="animate-spin" />}
            <span>Submit</span>
          </button>
        </div>
      </form>

      <div className="mt-6 pt-3 border-t border-gray-100 text-[11px] text-gray-400 text-center leading-relaxed">
        By creating an account, you agree to the Terms of Service and Privacy Policy.
      </div>
    </div>
  );
};
