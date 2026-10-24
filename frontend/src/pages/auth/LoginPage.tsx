import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, GraduationCap, Library, ShieldCheck, Sparkles, UserCog } from "lucide-react";
import { PORTAL_HOME, useAuth, type Role } from "../../lib/auth";
import { api } from "../../lib/api";
import { Spinner } from "../../components/ui";

const PORTALS: { key: Role; label: string; order: number; icon: any; color: string; blurb: string }[] = [
  {
    key: "student",
    label: "Student Login",
    order: 1,
    icon: GraduationCap,
    color: "from-brand-500 to-brand-700",
    blurb: "Learning path, assessments, tasks & rewards",
  },
  {
    key: "coordinator",
    label: "Domain Coordinator Login",
    order: 2,
    icon: Library,
    color: "from-sky-500 to-sky-700",
    blurb: "Content, assessments & grading",
  },
  {
    key: "faculty",
    label: "Faculty Coordinator Login",
    order: 3,
    icon: ShieldCheck,
    color: "from-violet-500 to-violet-700",
    blurb: "Evidence review, appeals & approvals",
  },
  {
    key: "admin",
    label: "Admin Login",
    order: 4,
    icon: UserCog,
    color: "from-teal-500 to-teal-700",
    blurb: "Users, domains, settings & audit",
  },
];

export default function LoginPage() {
  const [portal, setPortal] = useState<Role | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [branding, setBranding] = useState<any>(null);
  const { login, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/public/config").then(setBranding).catch(() => {});
  }, []);

  useEffect(() => {
    if (user) navigate(PORTAL_HOME[user.role], { replace: true });
  }, [user, navigate]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!portal) return;
    setBusy(true);
    setError(null);
    try {
      const loggedIn = await login(email, password, portal);
      navigate(PORTAL_HOME[loggedIn.role], { replace: true });
    } catch (err: any) {
      setError(err.message || "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative min-h-screen flex flex-col justify-center items-center px-4 py-12 bg-gradient-to-b from-slate-50 via-brand-50/25 to-slate-100 overflow-hidden">
      {/* Background ambient accents */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 h-96 w-96 rounded-full bg-brand-400/15 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 right-1/4 h-80 w-80 rounded-full bg-violet-400/15 blur-3xl" />

      {/* Opening Animation Header: Logo & Branding */}
      <div className="relative z-10 animate-float-in mb-8 flex flex-col items-center text-center">
        <div className="relative mb-3.5 flex h-16 w-16 items-center justify-center rounded-3xl bg-gradient-to-tr from-brand-600 via-brand-500 to-indigo-600 text-white shadow-xl shadow-brand-500/25 ring-4 ring-brand-100 animate-pulse-glow">
          <GraduationCap className="h-9 w-9 drop-shadow" />
          <span className="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 ring-2 ring-white text-[10px] font-bold text-white shadow-sm">
            ✓
          </span>
        </div>

        <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Elite Portal
        </h1>
        <p className="mt-1 text-sm font-semibold text-brand-700">
          {branding?.institution || "Francis Xavier Engineering College"}
        </p>
        <div className="mt-2.5 inline-flex items-center gap-1.5 rounded-full bg-white/90 border border-brand-200/80 px-3 py-1 text-xs font-semibold text-brand-700 shadow-sm">
          <Sparkles className="h-3.5 w-3.5 text-brand-500" />
          <span>{branding?.batch || "Elite Batch 2025–2029"}</span>
        </div>
      </div>

      {/* Centered Login Card */}
      <div className="relative z-10 w-full max-w-md animate-card-in">
        <div className="rounded-3xl bg-white p-7 sm:p-9 shadow-xl border border-slate-200/80 backdrop-blur-sm transition-all duration-300">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-slate-900">Welcome back</h2>
            <p className="mt-1 text-sm text-slate-500">
              {portal ? "Enter your credentials to continue." : "Choose your portal to sign in."}
            </p>
          </div>

          {!portal ? (
            <div className="space-y-3">
              {PORTALS.map((p) => (
                <button
                  key={p.key}
                  onClick={() => {
                    setPortal(p.key);
                    setError(null);
                  }}
                  className="group flex w-full items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-card transition-all duration-200 hover:border-brand-400 hover:shadow-soft hover:-translate-y-0.5 active:translate-y-0"
                >
                  <div
                    className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${p.color} text-white shadow-md shadow-slate-200`}
                  >
                    <p.icon className="h-6 w-6" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-slate-900 group-hover:text-brand-700 transition">
                      {p.label}
                    </p>
                    <p className="text-xs text-slate-500 truncate">{p.blurb}</p>
                  </div>
                  <ArrowRight className="h-5 w-5 text-slate-300 transition-transform duration-200 group-hover:translate-x-1 group-hover:text-brand-600" />
                </button>
              ))}
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div className="flex items-center gap-3 rounded-2xl bg-slate-50 p-3 border border-slate-100">
                {(() => {
                  const p = PORTALS.find((x) => x.key === portal)!;
                  return (
                    <>
                      <div
                        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${p.color} text-white shadow-sm`}
                      >
                        <p.icon className="h-5 w-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-slate-400 uppercase font-semibold">Active Portal</p>
                        <p className="text-sm font-semibold text-slate-800 truncate">{p.label}</p>
                      </div>
                      <button
                        type="button"
                        className="rounded-lg px-2.5 py-1 text-xs font-semibold text-brand-600 hover:bg-brand-50 transition"
                        onClick={() => setPortal(null)}
                      >
                        Change
                      </button>
                    </>
                  );
                })()}
              </div>

              {error && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs font-medium text-red-700">
                  {error}
                </div>
              )}

              <div>
                <label className="label">Email address</label>
                <input
                  type="email"
                  className="input"
                  placeholder="you@fxec.ac.in"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  autoFocus
                />
              </div>

              <div>
                <label className="label">Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="input pr-11"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1"
                    onClick={() => setShowPassword((v) => !v)}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs">
                <label className="flex items-center gap-2 text-slate-600 cursor-pointer">
                  <input type="checkbox" className="rounded border-slate-300 text-brand-600 focus:ring-brand-500" defaultChecked />
                  <span>Remember me</span>
                </label>
                <Link to="/forgot-password" className="font-semibold text-brand-600 hover:underline">
                  Forgot password?
                </Link>
              </div>

              <button type="submit" className="btn-primary w-full py-3 font-semibold shadow-md" disabled={busy}>
                {busy ? <Spinner className="text-white" /> : <>Sign in <ArrowRight className="h-4 w-4" /></>}
              </button>

              <p className="text-center text-xs text-slate-500 pt-1">
                New student?{" "}
                <Link to="/register" className="font-semibold text-brand-600 hover:underline">
                  Create an account
                </Link>
              </p>
            </form>
          )}

          <div className="mt-8 pt-5 border-t border-slate-100 text-center space-y-1.5">
            <p className="text-[11px] font-medium text-slate-400">
              Protected area · Authorised users only. All activity is audited.
            </p>
            <p className="text-[11px] text-slate-400">
              © {new Date().getFullYear()} {branding?.institution || "Francis Xavier Engineering College"}. All rights reserved.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
