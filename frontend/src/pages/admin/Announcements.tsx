import { useState } from "react";
import { Megaphone, Pencil, Plus } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, EmptyState, ErrorState, Field, Modal, PageHeader, Pagination, PageLoader, Spinner, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

const AUDIENCES = ["all", "students", "coordinators", "faculty", "admin"];
const STATUSES = ["draft", "published", "archived"];

export default function AdminAnnouncements() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editRow, setEditRow] = useState<any>(null);
  const { push } = useToast();

  const params: any = { page, per_page: 25 };
  if (status) params.status = status;

  const { data, meta, loading, error, reload } = useApi<any[]>("/admin/announcements", params);

  return (
    <div>
      <PageHeader
        title="Announcements"
        subtitle="Broadcast information to students, staff and administrators."
        actions={
          <button className="btn-primary" onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" /> New announcement
          </button>
        }
      />

      <Card className="mb-4">
        <div className="max-w-xs">
          <Field label="Status">
            <select className="input" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
              <option value="">All statuses</option>
              {STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
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
          <EmptyState icon={<Megaphone className="h-6 w-6" />} title="No announcements" description="Create your first announcement." />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Audience</th>
                    <th>Domain</th>
                    <th>Category</th>
                    <th>Publish</th>
                    <th>Expires</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((a) => (
                    <tr key={a.id}>
                      <td>
                        <p className="font-medium text-slate-800">{a.title}</p>
                        <p className="mt-0.5 line-clamp-1 text-xs text-slate-400">{a.content}</p>
                      </td>
                      <td><Badge tone="blue">{humanize(a.target_audience)}</Badge></td>
                      <td className="text-slate-700">{a.target_domain || "All"}</td>
                      <td className="text-slate-500">{humanize(a.category)}</td>
                      <td className="whitespace-nowrap text-xs text-slate-500">{a.publish_at ? formatDateTime(a.publish_at) : "—"}</td>
                      <td className="whitespace-nowrap text-xs text-slate-500">{a.expires_at ? formatDateTime(a.expires_at) : "—"}</td>
                      <td><StatusBadge status={a.status} /></td>
                      <td className="text-right">
                        <button className="btn-secondary !px-3 !py-1.5" onClick={() => setEditRow(a)}>
                          <Pencil className="h-4 w-4" /> Edit
                        </button>
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

      {formOpen && (
        <AnnouncementForm
          onClose={() => setFormOpen(false)}
          onSaved={() => { setFormOpen(false); push("Announcement created.", "success"); reload(); }}
        />
      )}
      {editRow && (
        <AnnouncementForm
          row={editRow}
          onClose={() => setEditRow(null)}
          onSaved={() => { setEditRow(null); push("Announcement updated.", "success"); reload(); }}
        />
      )}
    </div>
  );
}

function toLocalInput(value?: string | null): string {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function AnnouncementForm({ row, onClose, onSaved }: { row?: any; onClose: () => void; onSaved: () => void }) {
  const editing = !!row;
  const { data: domains } = useApi<any[]>("/domains");
  const { push } = useToast();
  const [form, setForm] = useState<any>({
    title: row?.title || "",
    content: row?.content || "",
    target_audience: row?.target_audience || "all",
    category: row?.category || "general",
    target_domain_id: row?.target_domain_id ?? "",
    status: row?.status || "draft",
    publish_at: toLocalInput(row?.publish_at),
    expires_at: toLocalInput(row?.expires_at),
  });
  const [busy, setBusy] = useState(false);

  function set(key: string, value: any) {
    setForm((prev: any) => ({ ...prev, [key]: value }));
  }

  async function submit() {
    setBusy(true);
    try {
      const payload = {
        title: form.title,
        content: form.content,
        category: form.category || "general",
        target_audience: form.target_audience,
        target_domain_id: form.target_domain_id === "" ? null : Number(form.target_domain_id),
        status: form.status,
        publish_at: form.publish_at ? new Date(form.publish_at).toISOString() : null,
        expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
      };
      if (editing) await api.patch(`/admin/announcements/${row.id}`, payload);
      else await api.post("/admin/announcements", payload);
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
      title={editing ? "Edit announcement" : "New announcement"}
      size="lg"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn-primary" onClick={submit} disabled={busy || form.title.trim().length < 3 || form.content.trim().length < 5}>
            {busy ? <Spinner className="text-white" /> : editing ? "Save changes" : "Create announcement"}
          </button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Field label="Title"><input className="input" value={form.title} onChange={(e) => set("title", e.target.value)} /></Field>
        </div>
        <div className="sm:col-span-2">
          <Field label="Content"><textarea className="input min-h-32" value={form.content} onChange={(e) => set("content", e.target.value)} /></Field>
        </div>
        <Field label="Target audience">
          <select className="input" value={form.target_audience} onChange={(e) => set("target_audience", e.target.value)}>
            {AUDIENCES.map((a) => <option key={a} value={a}>{humanize(a)}</option>)}
          </select>
        </Field>
        <Field label="Category"><input className="input" value={form.category} onChange={(e) => set("category", e.target.value)} placeholder="e.g. general, event" /></Field>
        <Field label="Target domain">
          <select className="input" value={form.target_domain_id} onChange={(e) => set("target_domain_id", e.target.value)}>
            <option value="">All domains</option>
            {(domains || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select className="input" value={form.status} onChange={(e) => set("status", e.target.value)}>
            {STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
          </select>
        </Field>
        <Field label="Publish at"><input type="datetime-local" className="input" value={form.publish_at} onChange={(e) => set("publish_at", e.target.value)} /></Field>
        <Field label="Expires at"><input type="datetime-local" className="input" value={form.expires_at} onChange={(e) => set("expires_at", e.target.value)} /></Field>
      </div>
    </Modal>
  );
}
