export interface UserProfile {
  id: string;
  username: string;
  name: string;
  email: string;
  role: string;
  organization?: string;
  avatarUrl?: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  user: UserProfile | null;
  token?: string;
  isBackendConnected: boolean;
}
