import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Bell, ChevronDown, LogOut, Menu, Search, UserCog, X } from "lucide-react";
import clsx from "clsx";
import { PORTAL_HOME, useAuth } from "../../lib/auth";
import { NAV, ROLE_META } from "../../lib/nav";
import { useApi } from "../../lib/hooks";
import { api } from "../../lib/api";
import { Avatar } from "../ui";
import { useToast } from "../ui/Toast";

export default function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { push } = useToast();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const { data: notifications, reload } = useApi<any[]>("/notifications");

  const role = user!.role;
  const sections = NAV[role];
  const meta0 = ROLE_META[role];
  const unread = useMemo(() => (notifications || []).filter((n) => !n.is_read).length, [notifications]);

  useEffect(() => {
    setMobileOpen(false);
    setMenuOpen(false);
    setNotifOpen(false);
  }, [location.pathname]);

  async function handleLogout() {
    await logout();
    push("Signed out.", "info");
    navigate("/login", { replace: true });
  }

  async function markAllRead() {
    await api.post("/notifications/read-all");
    reload();
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {mobileOpen && <div className="fixed inset-0 z-40 bg-slate-900/40 lg:hidden" onClick={() => setMobileOpen(false)} />}

      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-slate-200 bg-white transition-transform lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <Link to={PORTAL_HOME[role]} className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-white">
              <meta0.icon className="h-5 w-5" />
            </div>
            <div className="leading-tight">
              <p className="text-sm font-semibold text-slate-900">Elite Portal</p>
              <p className="text-[11px] text-slate-400">FXEC · Batch 2029</p>
            </div>
          </Link>
          <button className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 lg:hidden" onClick={() => setMobileOpen(false)}>
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-6 scrollbar-thin">
          {sections.map((section, i) => (
            <div key={i}>
              {section.title && (
                <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  {section.title}
                </p>
              )}
              <div className="space-y-0.5">
                {section.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) => clsx("sidebar-link", isActive && "sidebar-link-active")}
                  >
                    <item.icon className="h-[18px] w-[18px]" />
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-slate-100 p-3">
          <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3">
            <Avatar name={user!.name} src={user!.avatar_url} size={38} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-800">{user!.name}</p>
              <p className="truncate text-xs text-slate-400">{meta0.label}</p>
            </div>
          </div>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/80 px-4 backdrop-blur sm:px-6">
          <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden" onClick={() => setMobileOpen(true)}>
            <Menu className="h-5 w-5" />
          </button>

          <div className="hidden flex-1 items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 sm:flex sm:max-w-sm">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              placeholder="Search…"
              className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400"
              onKeyDown={(e) => {
                if (e.key === "Enter") push("Global search is coming soon.", "info");
              }}
            />
          </div>

          <div className="ml-auto flex items-center gap-1">
            <div className="relative">
              <button
                className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100"
                onClick={() => setNotifOpen((v) => !v)}
              >
                <Bell className="h-5 w-5" />
                {unread > 0 && (
                  <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
                    {unread}
                  </span>
                )}
              </button>
              {notifOpen && (
                <div className="absolute right-0 mt-2 w-80 card shadow-soft">
                  <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                    <p className="text-sm font-semibold text-slate-800">Notifications</p>
                    {unread > 0 && (
                      <button className="text-xs text-brand-600 hover:underline" onClick={markAllRead}>
                        Mark all read
                      </button>
                    )}
                  </div>
                  <div className="max-h-80 overflow-y-auto scrollbar-thin">
                    {(notifications || []).length === 0 && <p className="p-4 text-sm text-slate-400">No notifications yet.</p>}
                    {(notifications || []).slice(0, 8).map((n) => (
                      <button
                        key={n.id}
                        className={clsx("block w-full border-b border-slate-50 px-4 py-3 text-left hover:bg-slate-50", !n.is_read && "bg-brand-50/40")}
                        onClick={() => {
                          api.post(`/notifications/${n.id}/read`).then(reload);
                          setNotifOpen(false);
                          if (n.link_url?.startsWith("/")) navigate(n.link_url);
                        }}
                      >
                        <p className="text-sm font-medium text-slate-800">{n.title}</p>
                        <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{n.message}</p>
                      </button>
                    ))}
                  </div>
                  <Link to="/notifications" className="block border-t border-slate-100 px-4 py-2.5 text-center text-sm text-brand-600">
                    View all
                  </Link>
                </div>
              )}
            </div>

            <div className="relative">
              <button
                className="flex items-center gap-2 rounded-xl p-1.5 pr-2 hover:bg-slate-100"
                onClick={() => setMenuOpen((v) => !v)}
              >
                <Avatar name={user!.name} src={user!.avatar_url} size={32} />
                <ChevronDown className="h-4 w-4 text-slate-400" />
              </button>
              {menuOpen && (
                <div className="absolute right-0 mt-2 w-56 card shadow-soft">
                  <div className="border-b border-slate-100 px-4 py-3">
                    <p className="truncate text-sm font-medium text-slate-800">{user!.name}</p>
                    <p className="truncate text-xs text-slate-400">{user!.email}</p>
                  </div>
                  <Link to="/profile" className="flex items-center gap-2 px-4 py-2.5 text-sm text-slate-600 hover:bg-slate-50">
                    <UserCog className="h-4 w-4" /> My profile
                  </Link>
                  <button onClick={handleLogout} className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50">
                    <LogOut className="h-4 w-4" /> Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
