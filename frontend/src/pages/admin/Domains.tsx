import { useState } from "react";
import { BookOpen, CalendarClock, Pencil, Plus, Power, Users } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDate } from "../../lib/format";
import { Badge, Card, EmptyState, ErrorState, Field, Modal, PageHeader, PageLoader, Spinner } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

const ICONS = ["book", "code", "cpu", "database", "globe", "shield", "sparkles", "brain", "cloud", "lock"];

export default function AdminDomains() {
  const { data, loading, error, reload } = useApi<any[]>("/admin/domains");
  const [formOpen, setFormOpen] = useState(false);
  const [editDomain, setEditDomain] = useState<any>(null);
  const { push } = useToast();

  async function toggleActive(d: any) {
    try {
      await api.post(`/admin/domains/${d.id}/toggle-active`);
      push(d.is_active ? "Domain archived." : "Domain activated.", "success");
      reload();
    } catch (err: any) {
      push(err.message, "error");
    }
  }

  return (
    <div>
      <PageHeader
        title="Domains"
        subtitle="Learning domains, enrollment and their content footprint."
        actions={
          <button className="btn-primary" onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" /> New domain
          </button>
        }
      />

      {loading ? (
        <PageLoader />
      ) : error ? (
        <Card><ErrorState message={error} onRetry={reload} /></Card>
      ) : !data?.length ? (
        <Card><EmptyState icon={<BookOpen className="h-6 w-6" />} title="No domains yet" description="Create your first learning domain." /></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.map((d) => (
            <Card key={d.id} className="flex flex-col">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl text-white" style={{ backgroundColor: d.color || "#4f46e5" }}>
                    <BookOpen className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-800">{d.name}</p>
                    <p className="text-xs text-slate-400">{d.code}</p>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  {d.is_compulsory ? <Badge tone="violet">Compulsory</Badge> : <Badge tone="slate">Optional</Badge>}
                  {d.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Archived</Badge>}
                </div>
              </div>

              <p className="mt-3 line-clamp-2 text-sm text-slate-500">{d.description || "No description provided."}</p>

              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-xl bg-slate-50 py-2">
                  <p className="text-lg font-semibold text-slate-800">{d.student_count ?? 0}</p>
                  <p className="text-[11px] text-slate-400">Students</p>
                </div>
                <div className="rounded-xl bg-slate-50 py-2">
                  <p className="text-lg font-semibold text-slate-800">{d.published_days ?? 0}</p>
                  <p className="text-[11px] text-slate-400">Days</p>
                </div>
                <div className="rounded-xl bg-slate-50 py-2">
                  <p className="text-lg font-semibold text-slate-800">{d.assessment_count ?? 0}</p>
                  <p className="text-[11px] text-slate-400">Assessments</p>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-400">
                <span className="inline-flex items-center gap-1"><Users className="h-3.5 w-3.5" /> Limit {d.enrollment_limit ?? "∞"}</span>
                {d.domain_change_allowed_until && (
                  <span className="inline-flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" /> Changes until {formatDate(d.domain_change_allowed_until)}</span>
                )}
              </div>

              <div className="mt-auto flex justify-end gap-2 pt-4">
                <button className="btn-secondary !px-3 !py-1.5" onClick={() => setEditDomain(d)}>
                  <Pencil className="h-4 w-4" /> Edit
                </button>
                <button className={d.is_active ? "btn-secondary !px-3 !py-1.5" : "btn-primary !px-3 !py-1.5"} onClick={() => toggleActive(d)}>
                  <Power className="h-4 w-4" /> {d.is_active ? "Archive" : "Activate"}
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {formOpen && (
        <DomainForm
          onClose={() => setFormOpen(false)}
          onSaved={() => { setFormOpen(false); push("Domain created.", "success"); reload(); }}
        />
      )}
      {editDomain && (
        <DomainForm
          domain={editDomain}
          onClose={() => setEditDomain(null)}
          onSaved={() => { setEditDomain(null); push("Domain updated.", "success"); reload(); }}
        />
      )}
    </div>
  );
}

function DomainForm({ domain, onClose, onSaved }: { domain?: any; onClose: () => void; onSaved: () => void }) {
  const editing = !!domain;
  const { push } = useToast();
  const [form, setForm] = useState<any>({
    code: domain?.code || "",
    name: domain?.name || "",
    description: domain?.description || "",
    icon: domain?.icon || "book",
    color: domain?.color || "#4f46e5",
    is_compulsory: domain?.is_compulsory ?? false,
    is_active: domain?.is_active ?? true,
    enrollment_limit: domain?.enrollment_limit ?? "",
  });
  const [busy, setBusy] = useState(false);

  function set(key: string, value: any) {
    setForm((prev: any) => ({ ...prev, [key]: value }));
  }

  async function submit() {
    setBusy(true);
    try {
      const payload = {
        code: form.code.toUpperCase(),
        name: form.name,
        description: form.description || null,
        icon: form.icon,
        color: form.color,
        is_compulsory: form.is_compulsory,
        is_active: form.is_active,
        enrollment_limit: form.enrollment_limit === "" ? null : Number(form.enrollment_limit),
      };
      if (editing) await api.patch(`/admin/domains/${domain.id}`, payload);
      else await api.post("/admin/domains", payload);
      onSaved();
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
      title={editing ? "Edit domain" : "New domain"}
      size="lg"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn-primary" onClick={submit} disabled={busy || form.code.trim().length < 2 || form.name.trim().length < 3}>
            {busy ? <Spinner className="text-white" /> : editing ? "Save changes" : "Create domain"}
          </button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Code"><input className="input uppercase" value={form.code} onChange={(e) => set("code", e.target.value)} placeholder="e.g. WEB" /></Field>
        <Field label="Name"><input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} /></Field>
        <div className="sm:col-span-2">
          <Field label="Description"><textarea className="input min-h-24" value={form.description} onChange={(e) => set("description", e.target.value)} /></Field>
        </div>
        <Field label="Icon">
          <select className="input" value={form.icon} onChange={(e) => set("icon", e.target.value)}>
            {ICONS.map((i) => <option key={i} value={i}>{i}</option>)}
          </select>
        </Field>
        <Field label="Color">
          <div className="flex items-center gap-3">
            <input type="color" className="h-10 w-12 cursor-pointer rounded-lg border border-slate-200" value={form.color} onChange={(e) => set("color", e.target.value)} />
            <input className="input" value={form.color} onChange={(e) => set("color", e.target.value)} />
          </div>
        </Field>
        <Field label="Enrollment limit" hint="Leave blank for unlimited.">
          <input type="number" className="input" value={form.enrollment_limit} onChange={(e) => set("enrollment_limit", e.target.value)} />
        </Field>
      </div>

      <div className="mt-4 flex flex-wrap gap-6">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={form.is_compulsory} onChange={(e) => set("is_compulsory", e.target.checked)} /> Compulsory domain
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} /> Active
        </label>
      </div>
    </Modal>
  );
}
