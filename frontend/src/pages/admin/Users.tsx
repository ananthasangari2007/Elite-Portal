import { useState } from "react";
import { KeyRound, Pencil, Plus, Search, ShieldCheck, UserCheck, UserX } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import { Avatar, Badge, Card, EmptyState, ErrorState, Field, Modal, PageHeader, Pagination, PageLoader, Spinner, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

const ROLES = ["student", "coordinator", "faculty", "admin"];

export default function AdminUsers() {
  const [page, setPage] = useState(1);
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [editUser, setEditUser] = useState<any>(null);
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const { push } = useToast();

  const params: any = { page, per_page: 25 };
  if (role) params.role = role;
  if (status) params.status = status;
  if (search.trim()) params.search = search.trim();

  const { data, meta, loading, error, reload } = useApi<any[]>("/admin/users", params);

  function resetFilters(next: () => void) {
    setPage(1);
    next();
  }

  async function toggleActive(u: any) {
    try {
      await api.post(`/admin/users/${u.id}/toggle-active`);
      push(u.is_active_account ? "Account deactivated." : "Account activated.", "success");
      reload();
    } catch (err: any) {
      push(err.message, "error");
    }
  }

  async function approve(u: any) {
    try {
      await api.post(`/admin/users/${u.id}/approve`);
      push("Account approved.", "success");
      reload();
    } catch (err: any) {
      push(err.message, "error");
    }
  }

  async function resetPassword(u: any) {
    try {
      const res = await api.post<any>(`/admin/users/${u.id}/reset-password`);
      setTempPassword(res.temporary_password);
      reload();
    } catch (err: any) {
      push(err.message, "error");
    }
  }

  return (
    <div>
      <PageHeader
        title="Users"
        subtitle="Manage students, coordinators, faculty and administrators."
        actions={
          <button className="btn-primary" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4" /> Add user
          </button>
        }
      />

      <Card className="mb-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Search">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                className="input pl-9"
                placeholder="Name, email, register no."
                value={search}
                onChange={(e) => resetFilters(() => setSearch(e.target.value))}
              />
            </div>
          </Field>
          <Field label="Role">
            <select className="input" value={role} onChange={(e) => resetFilters(() => setRole(e.target.value))}>
              <option value="">All roles</option>
              {ROLES.map((r) => <option key={r} value={r}>{humanize(r)}</option>)}
            </select>
          </Field>
          <Field label="Status">
            <select className="input" value={status} onChange={(e) => resetFilters(() => setStatus(e.target.value))}>
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </Field>
        </div>
      </Card>

      <Card pad={false}>
        {loading ? (
          <PageLoader />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !data?.length ? (
          <EmptyState title="No users found" description="Try adjusting the filters." />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Role</th>
                    <th>Register / Dept</th>
                    <th>Approval</th>
                    <th>Active</th>
                    <th>Last login</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((u) => (
                    <tr key={u.id}>
                      <td>
                        <div className="flex items-center gap-3">
                          <Avatar name={u.name} src={u.avatar_url} size={36} />
                          <div className="min-w-0">
                            <p className="font-medium text-slate-800">{u.name}</p>
                            <p className="truncate text-xs text-slate-400">{u.email}</p>
                          </div>
                        </div>
                      </td>
                      <td><Badge tone={u.role === "admin" ? "violet" : u.role === "student" ? "blue" : "green"}>{humanize(u.role)}</Badge></td>
                      <td>
                        <p className="text-slate-700">{u.register_number || "—"}</p>
                        <p className="text-xs text-slate-400">{u.department || "—"}{u.year ? ` · Y${u.year}` : ""}</p>
                      </td>
                      <td><StatusBadge status={u.approval_status} /></td>
                      <td>
                        {u.is_active_account ? (
                          <Badge tone="green">Active</Badge>
                        ) : (
                          <Badge tone="red">Inactive</Badge>
                        )}
                      </td>
                      <td className="whitespace-nowrap text-slate-500">{u.last_login ? formatDateTime(u.last_login) : "Never"}</td>
                      <td>
                        <div className="flex items-center justify-end gap-1">
                          {u.approval_status === "pending" && (
                            <button className="btn-secondary !px-2.5 !py-1.5" title="Approve" onClick={() => approve(u)}>
                              <ShieldCheck className="h-4 w-4 text-emerald-600" />
                            </button>
                          )}
                          <button className="btn-secondary !px-2.5 !py-1.5" title="Edit" onClick={() => setEditUser(u)}>
                            <Pencil className="h-4 w-4" />
                          </button>
                          <button className="btn-secondary !px-2.5 !py-1.5" title="Reset password" onClick={() => resetPassword(u)}>
                            <KeyRound className="h-4 w-4" />
                          </button>
                          <button
                            className="btn-secondary !px-2.5 !py-1.5"
                            title={u.is_active_account ? "Deactivate" : "Activate"}
                            onClick={() => toggleActive(u)}
                          >
                            {u.is_active_account ? <UserX className="h-4 w-4 text-red-500" /> : <UserCheck className="h-4 w-4 text-emerald-600" />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={meta?.page || 1} pages={meta?.pages || 1} total={meta?.total} onPage={setPage} />
          </>
        )}
      </Card>

      {addOpen && (
        <UserForm
          onClose={() => setAddOpen(false)}
          onSaved={(temp) => {
            setAddOpen(false);
            if (temp) setTempPassword(temp);
            push("User created.", "success");
            reload();
          }}
        />
      )}

      {editUser && (
        <UserForm
          user={editUser}
          onClose={() => setEditUser(null)}
          onSaved={() => {
            setEditUser(null);
            push("User updated.", "success");
            reload();
          }}
        />
      )}

      {tempPassword && <TempPasswordModal password={tempPassword} onClose={() => setTempPassword(null)} />}
    </div>
  );
}

function UserForm({ user, onClose, onSaved }: { user?: any; onClose: () => void; onSaved: (temp?: string | null) => void }) {
  const editing = !!user;
  const { data: domains } = useApi<any[]>("/admin/domains");
  const { push } = useToast();
  const [form, setForm] = useState<any>({
    name: user?.name || "",
    email: user?.email || "",
    role: user?.role || "student",
    password: "",
    register_number: user?.register_number || "",
    department: user?.department || "",
    year: user?.year ?? "",
    section: user?.section || "",
    domain_ids: (user?.domains || []).map((d: any) => d.id),
  });
  const [busy, setBusy] = useState(false);

  function set(key: string, value: any) {
    setForm((prev: any) => ({ ...prev, [key]: value }));
  }

  const staffRole = form.role === "coordinator" || form.role === "faculty";

  function toggleDomain(id: number) {
    set("domain_ids", form.domain_ids.includes(id) ? form.domain_ids.filter((x: number) => x !== id) : [...form.domain_ids, id]);
  }

  async function submit() {
    setBusy(true);
    try {
      const payload: any = {
        name: form.name,
        role: form.role,
        register_number: form.register_number || null,
        department: form.department || null,
        year: form.year === "" ? null : Number(form.year),
        section: form.section || null,
        domain_ids: form.domain_ids,
      };
      if (!editing) {
        payload.email = form.email;
        if (form.password) payload.password = form.password;
      } else {
        payload.email = form.email;
      }
      if (editing) {
        await api.patch(`/admin/users/${user.id}`, payload);
        onSaved();
      } else {
        const res = await api.post<any>("/admin/users", payload);
        onSaved(res?.temporary_password || null);
      }
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={editing ? "Edit user" : "Add user"}
      size="lg"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn-primary" onClick={submit} disabled={busy || form.name.trim().length < 2 || !form.email.includes("@")}>
            {busy ? <Spinner className="text-white" /> : editing ? "Save changes" : "Create user"}
          </button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name"><input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} /></Field>
        <Field label="Email"><input className="input" value={form.email} onChange={(e) => set("email", e.target.value)} /></Field>
        <Field label="Role">
          <select className="input" value={form.role} onChange={(e) => set("role", e.target.value)}>
            {ROLES.map((r) => <option key={r} value={r}>{humanize(r)}</option>)}
          </select>
        </Field>
        {!editing && (
          <Field label="Password" hint="Leave blank to auto-generate a temporary password.">
            <input className="input" value={form.password} onChange={(e) => set("password", e.target.value)} placeholder="Optional" />
          </Field>
        )}
        <Field label="Register number"><input className="input" value={form.register_number} onChange={(e) => set("register_number", e.target.value)} /></Field>
        <Field label="Department"><input className="input" value={form.department} onChange={(e) => set("department", e.target.value)} /></Field>
        <Field label="Year"><input type="number" className="input" value={form.year} onChange={(e) => set("year", e.target.value)} /></Field>
        <Field label="Section"><input className="input" value={form.section} onChange={(e) => set("section", e.target.value)} /></Field>
      </div>

      {staffRole && (
        <div className="mt-4">
          <p className="label">Assigned domains</p>
          <div className="grid max-h-52 gap-2 overflow-y-auto rounded-xl border border-slate-200 p-3 sm:grid-cols-2">
            {(domains || []).map((d) => (
              <label key={d.id} className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={form.domain_ids.includes(d.id)} onChange={() => toggleDomain(d.id)} />
                <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: d.color || "#4f46e5" }} />
                {d.name}
              </label>
            ))}
            {!domains?.length && <p className="text-sm text-slate-400">No domains available.</p>}
          </div>
        </div>
      )}
    </Modal>
  );
}

function TempPasswordModal({ password, onClose }: { password: string; onClose: () => void }) {
  return (
    <Modal
      open
      onClose={onClose}
      title="Temporary password"
      subtitle="Share this with the user securely. It will not be shown again."
      footer={<button className="btn-primary" onClick={onClose}>Done</button>}
    >
      <div className="rounded-xl bg-slate-900 px-4 py-3 font-mono text-lg text-emerald-300">{password}</div>
    </Modal>
  );
}
