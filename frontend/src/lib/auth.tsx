import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, clearCsrf, ensureCsrf, hasSessionCandidate, setCsrfToken, setStoredToken } from "./api";
import { invalidateCache } from "./hooks";

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
  /** Set when the session could not be verified because of a network/server problem (not a 401). */
  authError: string | null;
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

// Shared across StrictMode double-mounts so only one /auth/me request is in flight.
let activeRefresh: Promise<{ user: User | null; error: string | null }> | null = null;

function checkSession(): Promise<{ user: User | null; error: string | null }> {
  if (activeRefresh) return activeRefresh;
  activeRefresh = (async () => {
    // Signed-out visitors: skip the probe entirely (previously every visit logged a 401).
    if (!hasSessionCandidate()) return { user: null, error: null };
    try {
      const res = await api.get<{ user: User; csrf_token?: string }>("/auth/me");
      if (res?.csrf_token) setCsrfToken(res.csrf_token);
      return { user: res?.user ?? null, error: null };
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        // Genuinely signed out / deactivated: clear client state once; no retry loop.
        setStoredToken(null);
        clearCsrf();
        return { user: null, error: null };
      }
      // Network failure, timeout or 5xx: keep the stored session and let the user retry.
      return { user: null, error: err instanceof ApiError ? err.message : "Could not verify your session." };
    } finally {
      activeRefresh = null;
    }
  })();
  return activeRefresh;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    const result = await checkSession();
    setUser(result.user);
    setAuthError(result.error);
    setLoading(false);
  }, []);

  useEffect(() => {
    let active = true;
    checkSession().then((result) => {
      if (!active) return;
      setUser(result.user);
      setAuthError(result.error);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const handler = () => {
      clearCsrf();
      setStoredToken(null);
      invalidateCache();
      setUser(null);
    };
    window.addEventListener("elite:unauthorized", handler);
    return () => window.removeEventListener("elite:unauthorized", handler);
  }, []);

  const login = useCallback(async (email: string, password: string, portal: Role) => {
    const data = await api.post<{ user: User; csrf_token?: string; token?: string }>("/auth/login", { email, password, portal });
    invalidateCache();
    setStoredToken(data.token ?? null);
    if (data.csrf_token) {
      setCsrfToken(data.csrf_token);
    } else {
      await ensureCsrf(true);
    }
    setAuthError(null);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      const data = await api.post<{ csrf_token?: string }>("/auth/logout");
      if (data?.csrf_token) setCsrfToken(data.csrf_token);
      else clearCsrf();
    } catch {
      clearCsrf();
    } finally {
      setStoredToken(null);
      invalidateCache();
      setUser(null);
    }
  }, []);

  const hasRole = useCallback((...roles: Role[]) => !!user && roles.includes(user.role), [user]);

  const value = useMemo(
    () => ({ user, loading, authError, login, logout, refresh, setUser, hasRole }),
    [user, loading, authError, login, logout, refresh, hasRole]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
