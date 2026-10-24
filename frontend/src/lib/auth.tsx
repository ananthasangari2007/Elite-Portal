import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, clearCsrf, ensureCsrf, setCsrfToken } from "./api";

export type Role = "student" | "coordinator" | "faculty" | "admin";

export type User = {
  id: number;
  name: string;
  email: string;
  role: Role;
  phone?: string | null;
  roll_number?: string | null;
  register_number?: string | null;
  department?: string | null;
  year?: number | null;
  section?: string | null;
  designation?: string | null;
  employee_id?: string | null;
  avatar_url?: string | null;
  approval_status?: string;
  is_active?: boolean;
};

type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, portal: Role) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setUser: (user: User | null) => void;
  hasRole: (...roles: Role[]) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export const PORTAL_HOME: Record<Role, string> = {
  student: "/student",
  coordinator: "/coordinator",
  faculty: "/faculty",
  admin: "/admin",
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await api.get<{ user: User; csrf_token?: string } | null>("/auth/me");
      if (res?.csrf_token) {
        setCsrfToken(res.csrf_token);
      } else {
        await ensureCsrf();
      }
      setUser(res?.user ?? null);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  useEffect(() => {
    const handler = () => {
      clearCsrf();
      setUser(null);
    };
    window.addEventListener("elite:unauthorized", handler);
    return () => window.removeEventListener("elite:unauthorized", handler);
  }, []);

  const login = useCallback(async (email: string, password: string, portal: Role) => {
    const data = await api.post<{ user: User; csrf_token?: string }>("/auth/login", { email, password, portal });
    if (data.csrf_token) {
      setCsrfToken(data.csrf_token);
    } else {
      await ensureCsrf(true);
    }
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      const data = await api.post<{ csrf_token?: string }>("/auth/logout");
      if (data?.csrf_token) {
        setCsrfToken(data.csrf_token);
      } else {
        clearCsrf();
      }
    } catch {
      clearCsrf();
    } finally {
      setUser(null);
    }
  }, []);

  const hasRole = useCallback((...roles: Role[]) => !!user && roles.includes(user.role), [user]);

  const value = useMemo(
    () => ({ user, loading, login, logout, refresh, setUser, hasRole }),
    [user, loading, login, logout, refresh, hasRole]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
