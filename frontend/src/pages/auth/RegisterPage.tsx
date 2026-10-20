import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GraduationCap } from "lucide-react";
import { api } from "../../lib/api";
import { Spinner } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function RegisterPage() {
  const [form, setForm] = useState({ name: "", email: "", register_number: "", password: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { push } = useToast();

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (form.password !== form.confirm) return setError("Passwords do not match.");
    if (form.password.length < 8) return setError("Password must be at least 8 characters.");
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/register", {
        name: form.name,
        email: form.email,
        register_number: form.register_number,
        password: form.password,
      });
      push("Account created. An administrator will approve your access shortly.", "success");
      navigate("/login");
    } catch (err: any) {
      setError(err.message || "Registration failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-violet-50 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-600 text-white">
            <GraduationCap className="h-6 w-6" />
          </div>
          <div>
            <p className="font-semibold text-slate-900">Elite Portal</p>
            <p className="text-xs text-slate-400">Student registration</p>
          </div>
        </div>

        <div className="card card-pad">
          <h2 className="text-xl font-semibold text-slate-900">Create your account</h2>
          <p className="mt-1 text-sm text-slate-500">Your account will require coordinator approval before access.</p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            {error && <div className="rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>}
            <div>
              <label className="label">Full name</label>
              <input className="input" value={form.name} onChange={set("name")} required placeholder="Your full name" />
            </div>
            <div>
              <label className="label">Email address</label>
              <input type="email" className="input" value={form.email} onChange={set("email")} required placeholder="you@fxecedu.in" />
            </div>
            <div>
              <label className="label">Register number</label>
              <input className="input" value={form.register_number} onChange={set("register_number")} required placeholder="e.g. 10122029" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Password</label>
                <input type="password" className="input" value={form.password} onChange={set("password")} required />
              </div>
              <div>
                <label className="label">Confirm</label>
                <input type="password" className="input" value={form.confirm} onChange={set("confirm")} required />
              </div>
            </div>
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? <Spinner className="text-white" /> : "Create account"}
            </button>
          </form>

          <p className="mt-5 text-center text-sm text-slate-500">
            Already registered?{" "}
            <Link to="/login" className="font-medium text-brand-600 hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
