import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, setTokens, type Tokens } from '../lib/api';

export type User = {
  id: number;
  email: string;
  username: string;
  full_name?: string | null;
  is_active: boolean;
  is_admin: boolean;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: { email: string; username: string; password: string; full_name?: string }) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const me = await api<User>('/api/auth/me');
      setUser(me);
    } catch {
      setUser(null);
      setTokens(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        await refreshUser();
      } finally {
        setLoading(false);
      }
    })();
  }, [refreshUser]);

  const login = async (email: string, password: string) => {
    const tokens = await api<Tokens>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }, false);
    setTokens(tokens);
    await refreshUser();
  };

  const register = async (payload: { email: string; username: string; password: string; full_name?: string }) => {
    await api('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) }, false);
    await login(payload.email, payload.password);
  };

  const logout = () => {
    setTokens(null);
    setUser(null);
  };

  const value = useMemo(
    () => ({ user, loading, login, register, logout, refreshUser }),
    [user, loading, refreshUser],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth requires AuthProvider');
  return ctx;
}
