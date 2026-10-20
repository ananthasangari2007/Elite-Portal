import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { api } from "../../lib/api";
import { Spinner } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { push } = useToast();
  const token = params.get("token") || "";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) return setError("Passwords do not match.");
    if (password.length < 8) return setError("Password must be at least 8 characters.");
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/reset-password", { token, password });
      setDone(true);
      push("Password updated. Please sign in.", "success");
      setTimeout(() => navigate("/login"), 1600);
    } catch (err: any) {
      setError(err.message || "This reset link is invalid or has expired.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-violet-50 px-4 py-10">
      <div className="w-full max-w-md card card-pad">
        {done ? (
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
              <CheckCircle2 className="h-7 w-7" />
            </div>
            <h2 className="text-xl font-semibold text-slate-900">Password updated</h2>
            <p className="mt-2 text-sm text-slate-500">Redirecting you to sign in…</p>
          </div>
        ) : (
          <>
            <h2 className="text-xl font-semibold text-slate-900">Create a new password</h2>
            <p className="mt-1 text-sm text-slate-500">Choose a strong password you haven't used before.</p>
            {!token && (
              <div className="mt-4 rounded-xl border border-amber-100 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800">
                Missing reset token. Open the link from your email.
              </div>
            )}
            <form onSubmit={submit} className="mt-5 space-y-4">
              {error && <div className="rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>}
              <div>
                <label className="label">New password</label>
                <input type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} required disabled={!token} />
              </div>
              <div>
                <label className="label">Confirm password</label>
                <input type="password" className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} required disabled={!token} />
              </div>
              <button className="btn-primary w-full" disabled={busy || !token}>
                {busy ? <Spinner className="text-white" /> : "Update password"}
              </button>
            </form>
            <p className="mt-5 text-center text-sm text-slate-500">
              <Link to="/login" className="font-medium text-brand-600 hover:underline">
                Back to sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
