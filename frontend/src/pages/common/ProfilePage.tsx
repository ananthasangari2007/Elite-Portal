import { useEffect, useRef, useState } from "react";
import { Github, KeyRound, Linkedin, Save, Upload, User as UserIcon } from "lucide-react";
import { useAuth } from "../../lib/auth";
import { api } from "../../lib/api";
import { formatDateTime, humanize } from "../../lib/format";
import { Avatar, Card, Field, PageHeader, Spinner } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function ProfilePage() {
  const { user, setUser } = useAuth();
  const { push } = useToast();
  const [me, setMe] = useState<any>(null);
  const [form, setForm] = useState<any>({});
  const [busy, setBusy] = useState(false);
  const [pwBusy, setPwBusy] = useState(false);
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.get<any>("/auth/me").then((res) => {
      setMe(res.user);
      setForm({
        name: res.user.name || "",
        phone: res.user.phone || "",
        bio: res.user.bio || "",
        linkedin_url: res.user.linkedin_url || "",
        github_url: res.user.github_url || "",
        leetcode_url: res.user.leetcode_url || "",
      });
    });
  }, []);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function save() {
    setBusy(true);
    try {
      const updated = await api.patch<any>("/auth/profile", form);
      setMe(updated);
      setUser({ ...user!, ...updated });
      push("Profile updated.", "success");
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function changePassword() {
    if (pw.new_password !== pw.confirm) return push("New passwords do not match.", "error");
    setPwBusy(true);
    try {
      await api.post("/auth/change-password", { current_password: pw.current_password, new_password: pw.new_password });
      setPw({ current_password: "", new_password: "", confirm: "" });
      push("Password changed.", "success");
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setPwBusy(false);
    }
  }

  async function uploadAvatar(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("folder", "avatars");
    try {
      const meta = await api.upload<any>("/uploads", fd);
      const updated = await api.patch<any>("/auth/profile", { avatar_url: meta.preview_url });
      setMe(updated);
      setUser({ ...user!, ...updated });
      push("Profile photo updated.", "success");
    } catch (err: any) {
      push(err.message, "error");
    }
  }

  if (!me) return <Spinner />;

  return (
    <div>
      <PageHeader title="My Profile" subtitle="Manage your personal information and account security." />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <div className="flex flex-col items-center text-center">
            <div className="relative">
              <Avatar name={me.name} src={me.avatar_url} size={96} />
              <button
                className="absolute -bottom-1 -right-1 flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-white shadow-sm hover:bg-brand-700"
                onClick={() => fileRef.current?.click()}
              >
                <Upload className="h-4 w-4" />
              </button>
              <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={uploadAvatar} />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-slate-900">{me.name}</h3>
            <p className="text-sm text-slate-500">{me.email}</p>
            <span className="badge-blue mt-2">{humanize(me.role)}</span>
            <div className="mt-5 w-full space-y-2 border-t border-slate-100 pt-4 text-left text-sm">
              <Row label="Register No." value={me.register_number} />
              <Row label="Department" value={me.department} />
              <Row label="Year / Section" value={me.year ? `${me.year}${me.section ? " · " + me.section : ""}` : null} />
              <Row label="Last login" value={formatDateTime(me.last_login)} />
            </div>
          </div>
        </Card>

        <div className="space-y-6 lg:col-span-2">
          <Card title="Personal information">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Full name"><input className="input" value={form.name} onChange={set("name")} /></Field>
              <Field label="Phone"><input className="input" value={form.phone} onChange={set("phone")} placeholder="+91…" /></Field>
              <Field label="LinkedIn">
                <div className="relative">
                  <Linkedin className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input className="input pl-9" value={form.linkedin_url} onChange={set("linkedin_url")} placeholder="https://linkedin.com/in/…" />
                </div>
              </Field>
              <Field label="GitHub">
                <div className="relative">
                  <Github className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input className="input pl-9" value={form.github_url} onChange={set("github_url")} placeholder="https://github.com/…" />
                </div>
              </Field>
              <div className="sm:col-span-2">
                <Field label="LeetCode / Portfolio"><input className="input" value={form.leetcode_url} onChange={set("leetcode_url")} /></Field>
              </div>
              <div className="sm:col-span-2">
                <Field label="About you"><textarea className="input min-h-24" value={form.bio} onChange={set("bio")} placeholder="A short bio…" /></Field>
              </div>
            </div>
            <div className="mt-5 flex justify-end">
              <button className="btn-primary" onClick={save} disabled={busy}>
                {busy ? <Spinner className="text-white" /> : <><Save className="h-4 w-4" /> Save changes</>}
              </button>
            </div>
          </Card>

          <Card title="Change password">
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Current password"><input type="password" className="input" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
              <Field label="New password"><input type="password" className="input" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
              <Field label="Confirm new"><input type="password" className="input" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /></Field>
            </div>
            <div className="mt-5 flex justify-end">
              <button className="btn-secondary" onClick={changePassword} disabled={pwBusy || !pw.current_password || !pw.new_password}>
                {pwBusy ? <Spinner /> : <><KeyRound className="h-4 w-4" /> Update password</>}
              </button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value?: any }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-400">{label}</span>
      <span className="font-medium text-slate-700">{value || "—"}</span>
    </div>
  );
}
