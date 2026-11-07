import { useRef, useState } from "react";
import { CalendarClock, CheckCircle2, Clock, Link as LinkIcon, Target, Upload } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, formatBytes, humanize } from "../../lib/format";
import { Badge, Card, EmptyState, Field, Modal, PageHeader, PageLoader } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function StudentTasks() {
  const { data, loading, reload } = useApi<any>("/student/tasks");
  const [task, setTask] = useState<any>(null);
  const { push } = useToast();
  const tasks = data?.tasks || [];

  return (
    <div>
      <PageHeader
        title="Elite Tasks"
        subtitle={`Submit daily evidence for your assigned tasks. One submission allowed per task each day (${data?.business_date || "today"}).`}
      />

      {loading ? (
        <PageLoader />
      ) : !tasks.length ? (
        <Card><EmptyState icon={<Target className="h-6 w-6" />} title="No tasks yet" description="Elite Tasks will appear here when assigned." /></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {tasks.map((t: any) => (
            <Card key={t.id} className="flex flex-col">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-50 text-violet-600">
                    <Target className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-medium text-slate-800">{t.title}</p>
                    <p className="text-xs text-slate-400">{t.domain || "All domains"} · {humanize(t.category)}</p>
                  </div>
                </div>
                <Badge tone={t.state === "completed" ? "green" : t.state === "available" ? "blue" : "slate"}>{humanize(t.state)}</Badge>
              </div>

              <p className="mt-3 line-clamp-2 text-sm text-slate-500">{t.description}</p>

              <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
                <span className="inline-flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {t.potential_points} pts</span>
                {t.due_date && <span className="inline-flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" /> due {formatDateTime(t.due_date)}</span>}
              </div>

              {t.submission && (
                <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Submission</span>
                    <Badge tone={t.submission.status === "approved" ? "green" : t.submission.status === "rejected" ? "red" : "amber"}>{humanize(t.submission.status)}</Badge>
                  </div>
                  {t.submission.points_awarded != null && <p className="mt-1 text-xs text-slate-500">Points awarded: {t.submission.points_awarded}</p>}
                  {t.submission.reviewer_feedback && <p className="mt-1 text-xs text-slate-500">{t.submission.reviewer_feedback}</p>}
                </div>
              )}

              <div className="mt-auto flex items-center justify-between pt-4">
                {t.submitted_today ? (
                  <Badge tone="green">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Submitted Today
                  </Badge>
                ) : (
                  <span className="text-xs text-slate-400">Due today</span>
                )}

                {t.can_submit ? (
                  <button className="btn-primary" onClick={() => setTask(t)}>
                    Submit evidence
                  </button>
                ) : t.submitted_today ? (
                  <span className="text-xs font-semibold text-emerald-600">Daily limit reached for this task</span>
                ) : t.state === "upcoming" ? (
                  <span className="text-xs text-slate-400">Not yet available</span>
                ) : (
                  <span className="text-xs text-slate-400">Closed</span>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {task && <SubmitTaskModal task={task} onClose={() => setTask(null)} onDone={() => { setTask(null); reload(); }} />}
    </div>
  );
}

function SubmitTaskModal({ task, onClose, onDone }: { task: any; onClose: () => void; onDone: () => void }) {
  const formats: string[] = task.allowed_evidence_formats || ["link"];
  const [mode, setMode] = useState<string>(formats.includes("link") ? "link" : formats[0]);
  const [linkUrl, setLinkUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [upload, setUpload] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const { push } = useToast();

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("folder", "evidence");
    try {
      const meta = await api.upload<any>("/uploads", fd);
      setUpload(meta);
    } catch (err: any) {
      push(err.message, "error");
    }
  }

  async function submit() {
    setBusy(true);
    try {
      if (mode === "link") {
        await api.post(`/student/tasks/${task.id}/submit`, { evidence_type: "link", link_url: linkUrl, notes });
      } else {
        if (!upload) return push("Upload a file first.", "error");
        await api.post(`/student/tasks/${task.id}/submit`, {
          evidence_type: "file",
          file_key: upload.file_key,
          file_name: upload.file_name,
          file_size: upload.file_size,
          file_type: upload.file_type,
          notes,
        });
      }
      push("Task submitted for review.", "success");
      onDone();
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
      title={task.title}
      subtitle={`${task.potential_points} points · ${task.domain || "All domains"}`}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={submit} disabled={busy || (mode === "link" ? !linkUrl : !upload)}>Submit</button>
        </>
      }
    >
      <div className="space-y-4">
        {task.instructions && (
          <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
            <p className="text-xs font-semibold uppercase text-slate-400">Instructions</p>
            <p className="mt-1 whitespace-pre-wrap">{task.instructions}</p>
          </div>
        )}

        <Field label="Evidence type">
          <div className="flex gap-2">
            {formats.includes("link") && (
              <button className={`btn-secondary flex-1 ${mode === "link" ? "!border-brand-500 !text-brand-700" : ""}`} onClick={() => setMode("link")}>
                <LinkIcon className="h-4 w-4" /> Link
              </button>
            )}
            {formats.filter((f) => f !== "link").length > 0 && (
              <button className={`btn-secondary flex-1 ${mode !== "link" ? "!border-brand-500 !text-brand-700" : ""}`} onClick={() => setMode("file")}>
                <Upload className="h-4 w-4" /> File
              </button>
            )}
          </div>
        </Field>

        {mode === "link" ? (
          <Field label="Evidence link">
            <input className="input" placeholder="https://…" value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)} />
          </Field>
        ) : (
          <Field label="Upload file" hint={formats.filter((f) => f !== "link").join(", ")}>
            <div className="flex items-center gap-3">
              <button className="btn-secondary" onClick={() => fileRef.current?.click()}><Upload className="h-4 w-4" /> Choose file</button>
              {upload && <span className="text-sm text-slate-600">{upload.file_name} ({formatBytes(upload.file_size)})</span>}
              <input ref={fileRef} type="file" className="hidden" onChange={handleFile} />
            </div>
          </Field>
        )}

        <Field label="Notes" hint="Optional context for your reviewer.">
          <textarea className="input min-h-24" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
