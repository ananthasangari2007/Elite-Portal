import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, MailCheck } from "lucide-react";
import { api } from "../../lib/api";
import { Spinner } from "../../components/ui";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<any>("/auth/forgot-password", { email });
      setSent(res);
    } catch (err: any) {
      setError(err.message || "Could not process your request.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-violet-50 px-4 py-10">
      <div className="w-full max-w-md card card-pad">
        <Link to="/login" className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700">
          <ArrowLeft className="h-4 w-4" /> Back to sign in
        </Link>

        {sent ? (
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
              <MailCheck className="h-7 w-7" />
            </div>
            <h2 className="text-xl font-semibold text-slate-900">Check your inbox</h2>
            <p className="mt-2 text-sm text-slate-500">
              If an account exists for <span className="font-medium text-slate-700">{email}</span>, a reset link has been sent.
            </p>
            {sent.dev_reset_path && (
              <div className="mt-4 rounded-xl bg-amber-50 p-3 text-left text-xs text-amber-800">
                <p className="font-medium">Development mode</p>
                <p className="mt-1">Email delivery is not configured. Use this link to reset:</p>
                <Link to={sent.dev_reset_path} className="mt-1 inline-block break-all font-medium text-brand-700 underline">
                  {sent.dev_reset_path}
                </Link>
              </div>
            )}
          </div>
        ) : (
          <>
            <h2 className="text-xl font-semibold text-slate-900">Reset your password</h2>
            <p className="mt-1 text-sm text-slate-500">We'll email you a secure link to create a new password.</p>
            <form onSubmit={submit} className="mt-5 space-y-4">
              {error && <div className="rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>}
              <div>
                <label className="label">Email address</label>
                <input type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>
              <button className="btn-primary w-full" disabled={busy}>
                {busy ? <Spinner className="text-white" /> : "Send reset link"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
