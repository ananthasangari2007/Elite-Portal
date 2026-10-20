import { useState } from "react";
import { MessageSquarePlus, Send } from "lucide-react";
import clsx from "clsx";
import { useAuth } from "../../lib/auth";
import { useApi } from "../../lib/hooks";
import { api } from "../../lib/api";
import { formatDateTime, humanize, relativeTime } from "../../lib/format";
import { Card, EmptyState, Field, Modal, PageHeader, PageLoader, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

const CATEGORIES = ["assessment_reeval", "content_access", "technical", "point_discrepancy", "general"];

export default function RequestsPage() {
  const { user } = useAuth();
  const isStudent = user!.role === "student";
  const listPath = isStudent ? "/student/requests" : "/faculty/requests";
  const { data, loading, reload } = useApi<any[]>(listPath);
  const [createOpen, setCreateOpen] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const { push } = useToast();

  return (
    <div>
      <PageHeader
        title="Support Requests"
        subtitle={isStudent ? "Raise a request and track replies from faculty." : "Review and respond to student requests."}
        actions={
          isStudent && (
            <button className="btn-primary" onClick={() => setCreateOpen(true)}>
              <MessageSquarePlus className="h-4 w-4" /> New request
            </button>
          )
        }
      />

      <Card pad={false}>
        {loading ? (
          <PageLoader />
        ) : !data || data.length === 0 ? (
          <EmptyState
            title="No requests yet"
            description={isStudent ? "Create a request and we'll get back to you." : "Student requests will appear here."}
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Subject</th>
                  {!isStudent && <th>Student</th>}
                  <th>Category</th>
                  <th>Status</th>
                  <th>Handler</th>
                  <th>Updated</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.id}>
                    <td className="font-medium text-slate-800">{r.subject}</td>
                    {!isStudent && (
                      <td>
                        <p className="text-slate-700">{r.student}</p>
                        <p className="text-xs text-slate-400">{r.register_number}</p>
                      </td>
                    )}
                    <td>{humanize(r.category)}</td>
                    <td><StatusBadge status={r.status} /></td>
                    <td>{r.handler || "—"}</td>
                    <td className="text-slate-500">{relativeTime(r.updated_at || r.created_at)}</td>
                    <td className="text-right">
                      <button className="btn-secondary !px-3 !py-1.5" onClick={() => setOpenId(r.id)}>
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <CreateRequestModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          reload();
          push("Request submitted.", "success");
        }}
      />

      {openId != null && <RequestThread id={openId} onClose={() => { setOpenId(null); reload(); }} />}
    </div>
  );
}

function CreateRequestModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const [category, setCategory] = useState("general");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await api.post("/student/requests", { category, subject, message });
      setSubject("");
      setMessage("");
      onCreated();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New support request"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={submit} disabled={busy || subject.length < 3 || message.length < 5}>
            Submit request
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Category">
          <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{humanize(c)}</option>
            ))}
          </select>
        </Field>
        <Field label="Subject">
          <input className="input" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Brief summary" />
        </Field>
        <Field label="Describe your request" hint="At least 5 characters.">
          <textarea className="input min-h-32" value={message} onChange={(e) => setMessage(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

function RequestThread({ id, onClose }: { id: number; onClose: () => void }) {
  const { user } = useAuth();
  const { data, loading, reload } = useApi<any>(`/requests/${id}`);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [internal, setInternal] = useState(false);
  const { push } = useToast();
  const isStaff = user!.role !== "student";

  async function send() {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await api.post(`/requests/${id}/messages`, { message: text, is_internal: internal });
      setText("");
      reload();
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(status: string) {
    await api.patch(`/requests/${id}/status`, { status });
    reload();
  }

  return (
    <Modal open onClose={onClose} title={data?.subject || "Request"} subtitle={data ? `#${data.id} · ${humanize(data.category)}` : ""} size="lg" footer={
      <>
        {isStaff && (
          <div className="mr-auto flex gap-2">
            {["in_progress", "resolved", "closed"].map((s) => (
              <button key={s} className="btn-secondary !px-3 !py-1.5" onClick={() => setStatus(s)}>
                Mark {humanize(s)}
              </button>
            ))}
          </div>
        )}
        <button className="btn-secondary" onClick={onClose}>Close</button>
      </>
    }>
      {loading || !data ? (
        <PageLoader />
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">{data.student} · {data.register_number}</p>
              <p className="text-xs text-slate-400">Opened {formatDateTime(data.created_at)}</p>
            </div>
            <StatusBadge status={data.status} />
          </div>

          <div className="space-y-3">
            {(data.messages || []).map((m: any) => (
              <div
                key={m.id}
                className={clsx(
                  "rounded-2xl px-4 py-3",
                  m.sender_role === "student" ? "bg-slate-100" : "bg-brand-50",
                  m.is_internal && "border border-amber-200 bg-amber-50"
                )}
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-800">
                    {m.sender} <span className="text-xs font-normal text-slate-400">· {humanize(m.sender_role)}</span>
                    {m.is_internal && <span className="ml-2 text-xs font-medium text-amber-700">internal</span>}
                  </p>
                  <p className="text-xs text-slate-400">{relativeTime(m.created_at)}</p>
                </div>
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{m.message}</p>
              </div>
            ))}
          </div>

          <div className="rounded-2xl border border-slate-200 p-3">
            <textarea
              className="input min-h-24 border-0 focus:ring-0"
              placeholder={isStaff ? "Write a reply…" : "Add a message…"}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <div className="flex items-center justify-between pt-2">
              {isStaff ? (
                <label className="flex items-center gap-2 text-xs text-slate-500">
                  <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} /> Internal note (visible to staff only)
                </label>
              ) : <span />}
              <button className="btn-primary" onClick={send} disabled={busy || !text.trim()}>
                <Send className="h-4 w-4" /> Send
              </button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
