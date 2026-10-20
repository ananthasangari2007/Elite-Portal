import { useState } from "react";
import { CalendarClock, Pencil, Plus, Target } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, EmptyState, ErrorState, Field, Modal, PageHeader, Pagination, PageLoader, Spinner, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

const STATUSES = ["draft", "active", "upcoming", "completed"];
const FORMATS = ["pdf", "image", "zip", "link"];

export default function AdminTasks() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editTask, setEditTask] = useState<any>(null);
  const { push } = useToast();

  const params: any = { page, per_page: 25 };
  if (status) params.status = status;

  const { data, meta, loading, error, reload } = useApi<any[]>("/admin/tasks", params);

  return (
    <div>
      <PageHeader
        title="Elite Tasks"
        subtitle="Create and manage daily Elite Tasks and their evidence requirements."
        actions={
          <button className="btn-primary" onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" /> New task
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
          <EmptyState icon={<Target className="h-6 w-6" />} title="No tasks found" description="Create your first Elite Task." />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Task</th>
                    <th>Domain</th>
                    <th>Category</th>
                    <th>Points</th>
                    <th>Due</th>
                    <th>Submissions</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <p className="font-medium text-slate-800">{t.title}</p>
                        <p className="mt-0.5 line-clamp-1 text-xs text-slate-400">{t.description}</p>
                      </td>
                      <td className="text-slate-700">{t.domain || "All domains"}</td>
                      <td><Badge tone="blue">{humanize(t.category)}</Badge></td>
                      <td className="font-semibold text-slate-700">{t.potential_points}</td>
                      <td className="whitespace-nowrap text-xs text-slate-500">
                        {t.due_date ? <span className="inline-flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" /> {formatDateTime(t.due_date)}</span> : "—"}
                      </td>
                      <td className="text-slate-500">{t.submission_count ?? 0}</td>
                      <td><StatusBadge status={t.status} /></td>
                      <td className="text-right">
                        <button className="btn-secondary !px-3 !py-1.5" onClick={() => setEditTask(t)}>
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
        <TaskForm
          onClose={() => setFormOpen(false)}
          onSaved={() => { setFormOpen(false); push("Task created.", "success"); reload(); }}
        />
      )}
      {editTask && (
        <TaskForm
          task={editTask}
          onClose={() => setEditTask(null)}
          onSaved={() => { setEditTask(null); push("Task updated.", "success"); reload(); }}
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

function TaskForm({ task, onClose, onSaved }: { task?: any; onClose: () => void; onSaved: () => void }) {
  const editing = !!task;
  const { data: domains } = useApi<any[]>("/domains");
  const { push } = useToast();
  const [form, setForm] = useState<any>({
    title: task?.title || "",
    description: task?.description || "",
    instructions: task?.instructions || "",
    domain_id: task?.domain_id ?? "",
    category: task?.category || "general",
    potential_points: task?.potential_points ?? 100,
    allowed_evidence_formats: task?.allowed_evidence_formats || ["pdf", "image", "zip", "link"],
    status: task?.status || "draft",
    due_date: toLocalInput(task?.due_date),
    publish_at: toLocalInput(task?.publish_at),
  });
  const [busy, setBusy] = useState(false);

  function set(key: string, value: any) {
    setForm((prev: any) => ({ ...prev, [key]: value }));
  }

  function toggleFormat(f: string) {
    set("allowed_evidence_formats", form.allowed_evidence_formats.includes(f)
      ? form.allowed_evidence_formats.filter((x: string) => x !== f)
      : [...form.allowed_evidence_formats, f]);
  }

  async function submit() {
    setBusy(true);
    try {
      const payload = {
        title: form.title,
        description: form.description,
        instructions: form.instructions || null,
        domain_id: form.domain_id === "" ? null : Number(form.domain_id),
        category: form.category || "general",
        potential_points: Number(form.potential_points) || 0,
        allowed_evidence_formats: form.allowed_evidence_formats,
        status: form.status,
        due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
        publish_at: form.publish_at ? new Date(form.publish_at).toISOString() : null,
      };
      if (editing) await api.patch(`/admin/tasks/${task.id}`, payload);
      else await api.post("/admin/tasks", payload);
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
      title={editing ? "Edit task" : "New Elite Task"}
      size="lg"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn-primary" onClick={submit} disabled={busy || form.title.trim().length < 3 || form.description.trim().length < 5}>
            {busy ? <Spinner className="text-white" /> : editing ? "Save changes" : "Create task"}
          </button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Field label="Title"><input className="input" value={form.title} onChange={(e) => set("title", e.target.value)} /></Field>
        </div>
        <div className="sm:col-span-2">
          <Field label="Description"><textarea className="input min-h-24" value={form.description} onChange={(e) => set("description", e.target.value)} /></Field>
        </div>
        <div className="sm:col-span-2">
          <Field label="Instructions"><textarea className="input min-h-24" value={form.instructions} onChange={(e) => set("instructions", e.target.value)} /></Field>
        </div>
        <Field label="Domain">
          <select className="input" value={form.domain_id} onChange={(e) => set("domain_id", e.target.value)}>
            <option value="">All domains</option>
            {(domains || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <Field label="Category"><input className="input" value={form.category} onChange={(e) => set("category", e.target.value)} placeholder="e.g. coding, quiz" /></Field>
        <Field label="Potential points"><input type="number" className="input" value={form.potential_points} onChange={(e) => set("potential_points", e.target.value)} /></Field>
        <Field label="Status">
          <select className="input" value={form.status} onChange={(e) => set("status", e.target.value)}>
            {STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
          </select>
        </Field>
        <Field label="Due date"><input type="datetime-local" className="input" value={form.due_date} onChange={(e) => set("due_date", e.target.value)} /></Field>
        <Field label="Publish at"><input type="datetime-local" className="input" value={form.publish_at} onChange={(e) => set("publish_at", e.target.value)} /></Field>
      </div>

      <div className="mt-4">
        <p className="label">Allowed evidence formats</p>
        <div className="flex flex-wrap gap-3">
          {FORMATS.map((f) => (
            <label key={f} className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={form.allowed_evidence_formats.includes(f)} onChange={() => toggleFormat(f)} /> {humanize(f)}
            </label>
          ))}
        </div>
      </div>
    </Modal>
  );
}
