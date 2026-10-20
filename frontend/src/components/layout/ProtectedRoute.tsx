import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { PORTAL_HOME, useAuth, type Role } from "../../lib/auth";
import { PageLoader } from "../ui";

export function ProtectedRoute({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <PageLoader label="Checking your session" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!roles.includes(user.role)) return <Navigate to={PORTAL_HOME[user.role]} replace />;

  return <>{children}</>;
}
