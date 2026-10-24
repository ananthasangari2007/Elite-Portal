import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Camera, Github, Globe, GraduationCap, Linkedin, Phone, User } from "lucide-react";
import { api } from "../../lib/api";
import { Spinner } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function RegisterPage() {
  const [form, setForm] = useState({
    name: "",
    email: "",
    register_number: "",
    phone_number: "",
    linkedin_url: "",
    github_url: "",
    leetcode_url: "",
    avatar_url: "",
    password: "",
    confirm: "",
  });
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const navigate = useNavigate();
  const { push } = useToast();

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [key]: e.target.value });

  async function handleAvatarSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    // Show local preview immediately
    const reader = new FileReader();
    reader.onload = (event) => {
      setAvatarPreview(event.target?.result as string);
    };
    reader.readAsDataURL(file);

    // Upload to server
    setUploadingAvatar(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await api.upload<any>("/auth/upload-avatar", fd);
      setForm((prev) => ({ ...prev, avatar_url: res.url || res.preview_url }));
      push("Profile picture uploaded successfully.", "success");
    } catch (err: any) {
      push(err.message || "Failed to upload profile picture.", "error");
    } finally {
      setUploadingAvatar(false);
    }
  }

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
        phone_number: form.phone_number,
        linkedin_url: form.linkedin_url,
        github_url: form.github_url,
        leetcode_url: form.leetcode_url,
        avatar_url: form.avatar_url,
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
      <div className="w-full max-w-lg">
        <div className="mb-6 flex items-center justify-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-600 text-white shadow-md">
            <GraduationCap className="h-6 w-6" />
          </div>
          <div>
            <p className="font-semibold text-slate-900">Elite Portal</p>
            <p className="text-xs text-slate-400">Francis Xavier Engineering College</p>
          </div>
        </div>

        <div className="card card-pad shadow-lg border border-slate-100">
          <h2 className="text-xl font-bold text-slate-900">Student Registration</h2>
          <p className="mt-1 text-sm text-slate-500">Create your Elite Batch profile. Requires administrative approval.</p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            {error && <div className="rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>}

            {/* Profile Picture Upload Avatar Section */}
            <div className="flex flex-col items-center justify-center pb-2">
              <div className="relative group cursor-pointer" onClick={() => fileInputRef.current?.click()}>
                <div className="h-20 w-20 rounded-full overflow-hidden border-2 border-brand-500 bg-brand-50 flex items-center justify-center shadow-md">
                  {avatarPreview ? (
                    <img src={avatarPreview} alt="Preview" className="h-full w-full object-cover" />
                  ) : form.avatar_url ? (
                    <img src={form.avatar_url} alt="Avatar" className="h-full w-full object-cover" />
                  ) : (
                    <User className="h-8 w-8 text-brand-400" />
                  )}
                </div>
                <div className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition duration-150">
                  <Camera className="h-5 w-5 text-white" />
                </div>
                {uploadingAvatar && (
                  <div className="absolute inset-0 rounded-full bg-black/60 flex items-center justify-center">
                    <Spinner className="h-5 w-5 text-white" />
                  </div>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleAvatarSelect}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="mt-2 text-xs font-semibold text-brand-600 hover:text-brand-700"
              >
                {avatarPreview ? "Change Photo" : "Upload Profile Picture"}
              </button>
            </div>

            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="label">Full Name *</label>
                <input className="input" value={form.name} onChange={set("name")} required placeholder="John Doe" />
              </div>
              <div>
                <label className="label">Register Number *</label>
                <input className="input" value={form.register_number} onChange={set("register_number")} required placeholder="e.g. 10122029" />
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="label">Email Address *</label>
                <input type="email" className="input" value={form.email} onChange={set("email")} required placeholder="you@fxecedu.in" />
              </div>
              <div>
                <label className="label flex items-center gap-1.5">
                  <Phone className="h-3.5 w-3.5 text-slate-400" /> Phone Number
                </label>
                <input type="tel" className="input" value={form.phone_number} onChange={set("phone_number")} placeholder="+91 9876543210" />
              </div>
            </div>

            {/* Social & Coding Profiles */}
            <div className="space-y-3 pt-1 border-t border-slate-100">
              <p className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Professional Profiles</p>
              
              <div>
                <label className="label flex items-center gap-1.5">
                  <Linkedin className="h-3.5 w-3.5 text-[#0A66C2]" /> LinkedIn URL
                </label>
                <input className="input text-xs" value={form.linkedin_url} onChange={set("linkedin_url")} placeholder="https://linkedin.com/in/username" />
              </div>

              <div className="grid sm:grid-cols-2 gap-3">
                <div>
                  <label className="label flex items-center gap-1.5">
                    <Github className="h-3.5 w-3.5 text-slate-800" /> GitHub URL
                  </label>
                  <input className="input text-xs" value={form.github_url} onChange={set("github_url")} placeholder="https://github.com/username" />
                </div>
                <div>
                  <label className="label flex items-center gap-1.5">
                    <Globe className="h-3.5 w-3.5 text-amber-600" /> LeetCode URL
                  </label>
                  <input className="input text-xs" value={form.leetcode_url} onChange={set("leetcode_url")} placeholder="https://leetcode.com/u/username" />
                </div>
              </div>
            </div>

            {/* Password Section */}
            <div className="grid grid-cols-2 gap-3 pt-1 border-t border-slate-100">
              <div>
                <label className="label">Password *</label>
                <input type="password" className="input" value={form.password} onChange={set("password")} required placeholder="Min 8 chars" />
              </div>
              <div>
                <label className="label">Confirm *</label>
                <input type="password" className="input" value={form.confirm} onChange={set("confirm")} required placeholder="Confirm" />
              </div>
            </div>

            <button className="btn-primary w-full shadow-md py-2.5 mt-2 font-semibold" disabled={busy || uploadingAvatar}>
              {busy ? <Spinner className="text-white" /> : "Complete Registration"}
            </button>
          </form>

          <p className="mt-5 text-center text-sm text-slate-500">
            Already registered?{" "}
            <Link to="/login" className="font-semibold text-brand-600 hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
