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
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-brand-700 via-brand-600 to-violet-700 p-12 text-white lg:flex">
        <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-white/10 blur-2xl" />
        <div className="absolute -bottom-32 -left-16 h-80 w-80 rounded-full bg-violet-400/20 blur-3xl" />
        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/15 backdrop-blur">
              <GraduationCap className="h-6 w-6" />
            </div>
            <div>
              <p className="text-lg font-semibold">Elite Portal</p>
              <p className="text-sm text-white/70">Francis Xavier Engineering College</p>
            </div>
          </div>
        </div>

        <div className="relative max-w-md">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium backdrop-blur">
            <Sparkles className="h-3.5 w-3.5" /> Elite Batch 2025–2029
          </div>
          <h1 className="text-3xl font-semibold leading-tight">
            One portal for learning, assessment and recognition.
          </h1>
          <p className="mt-4 text-white/80">
            Track your learning path across domains, attempt assessments, submit daily Elite Tasks and climb the
            leaderboard — all in real time.
          </p>
          <div className="mt-8 grid grid-cols-3 gap-4 text-center">
            {[
              { label: "Domains", value: "4" },
              { label: "Role Portals", value: "4" },
              { label: "Live Points", value: "24/7" },
            ].map((s) => (
              <div key={s.label} className="rounded-2xl bg-white/10 px-3 py-4 backdrop-blur">
                <p className="text-xl font-semibold">{s.value}</p>
                <p className="text-xs text-white/70">{s.label}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-xs text-white/60">
          © {new Date().getFullYear()} {branding?.institution || "Francis Xavier Engineering College"}. All rights reserved.
        </p>
      </div>

      <div className="flex flex-col justify-center px-5 py-10 sm:px-10 lg:px-16">
        <div className="mx-auto w-full max-w-md">
          <div className="lg:hidden mb-8 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-600 text-white">
              <GraduationCap className="h-6 w-6" />
            </div>
            <div>
              <p className="font-semibold text-slate-900">Elite Portal</p>
              <p className="text-xs text-slate-400">FXEC · Batch 2025–2029</p>
            </div>
          </div>

          <h2 className="text-2xl font-semibold text-slate-900">Welcome back</h2>
          <p className="mt-1 text-sm text-slate-500">
            {portal ? "Enter your credentials to continue." : "Choose your portal to sign in."}
          </p>

          {!portal ? (
            <div className="mt-6 space-y-3">
              {PORTALS.map((p) => (
                <button
                  key={p.key}
                  onClick={() => {
                    setPortal(p.key);
                    setError(null);
                  }}
                  className="group flex w-full items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-card transition hover:border-brand-300 hover:shadow-soft"
                >
                  <div className={`flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${p.color} text-white`}>
                    <p.icon className="h-6 w-6" />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-slate-800">{p.label}</p>
                    <p className="text-xs text-slate-500">{p.blurb}</p>
                  </div>
                  <ArrowRight className="h-5 w-5 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-brand-500" />
                </button>
              ))}
            </div>
          ) : (
            <form onSubmit={submit} className="mt-6 space-y-4">
              <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3">
                {(() => {
                  const p = PORTALS.find((x) => x.key === portal)!;
                  return (
                    <>
                      <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${p.color} text-white`}>
                        <p.icon className="h-5 w-5" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-slate-800">{p.label}</p>
                      </div>
                      <button type="button" className="text-xs font-medium text-brand-600 hover:underline" onClick={() => setPortal(null)}>
                        Change
                      </button>
                    </>
                  );
                })()}
              </div>

              {error && (
                <div className="rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>
              )}

              <div>
                <label className="label">Email address</label>
                <input
                  type="email"
                  className="input"
                  placeholder="you@fxecedu.in"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
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
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    onClick={() => setShowPassword((v) => !v)}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between text-sm">
                <label className="flex items-center gap-2 text-slate-600">
                  <input type="checkbox" className="rounded border-slate-300" defaultChecked /> Remember me
                </label>
                <Link to="/forgot-password" className="font-medium text-brand-600 hover:underline">
                  Forgot password?
                </Link>
              </div>

              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? <Spinner className="text-white" /> : <>Sign in <ArrowRight className="h-4 w-4" /></>}
              </button>

              <p className="text-center text-sm text-slate-500">
                New student?{" "}
                <Link to="/register" className="font-medium text-brand-600 hover:underline">
                  Create an account
                </Link>
              </p>
            </form>
          )}

          <p className="mt-8 text-center text-xs text-slate-400">
            Protected area · Authorised users only. All activity is audited.
          </p>
        </div>
      </div>
    </div>
  );
}
