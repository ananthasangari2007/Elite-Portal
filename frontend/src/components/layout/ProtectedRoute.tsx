import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { PORTAL_HOME, useAuth, type Role } from "../../lib/auth";
import { PageLoader } from "../ui";

export function SessionError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-lg font-semibold text-slate-900">We couldn't check your session</h1>
      <p className="max-w-md text-sm text-slate-600">{message}</p>
      <button type="button" className="btn-primary" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

export function ProtectedRoute({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user, loading, authError, refresh } = useAuth();
  const location = useLocation();

  if (loading) return <PageLoader label="Checking your session" />;
  if (!user && authError) return <SessionError message={authError} onRetry={() => void refresh()} />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!roles.includes(user.role)) return <Navigate to={PORTAL_HOME[user.role]} replace />;

  return <>{children}</>;
}
