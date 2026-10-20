import { useMemo, useState } from "react";
import {
  CheckCircle2,
  FileText,
  Link as LinkIcon,
  Target,
  XCircle,
} from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatBytes, formatDateTime, humanize } from "../../lib/format";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Modal,
  PageHeader,
  PageLoader,
  Pagination,
  StatusBadge,
  Tabs,
} from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

const TABS = [
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
];

export default function TaskEvidenceQueue() {
  const [tab, setTab] = useState("pending");
  const [page, setPage] = useState(1);
  const [review, setReview] = useState<any>(null);

  const params = useMemo(() => ({ status: tab, page }), [tab, page]);
  const { data, meta, loading, error, reload } = useApi<any[]>("/faculty/task-evidence", params);
  const rows = data || [];

  return (
    <div>
      <PageHeader
        title="Task Evidence"
        subtitle="Approve or reject student evidence submitted for Elite Tasks."
        actions={
          <button className="btn-secondary" onClick={reload}>
            Refresh
          </button>
        }
      />

      <Tabs
        tabs={TABS}
        active={tab}
        onChange={(key) => {
          setTab(key);
          setPage(1);
        }}
      />

      <Card className="mt-6" pad={false}>
        {loading ? (
          <PageLoader label="Loading evidence" />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !rows.length ? (
          <EmptyState icon={<Target className="h-6 w-6" />} title="No evidence here" description="Evidence submissions will appear here as students upload them." />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Task</th>
                    <th>Evidence</th>
                    <th>Notes</th>
                    <th>Submitted</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((e: any) => (
                    <tr key={e.id}>
                      <td>
                        <p className="font-medium text-slate-800">{e.student}</p>
                        <p className="text-xs text-slate-400">{e.register_number}</p>
                      </td>
                      <td className="text-slate-700">{e.task}</td>
                      <td>
                        <EvidenceLink evidence={e} />
                      </td>
                      <td className="max-w-xs">
                        <p className="line-clamp-2 text-xs text-slate-500">{e.notes || "—"}</p>
                      </td>
                      <td className="whitespace-nowrap text-slate-500">{e.submitted_at ? formatDateTime(e.submitted_at) : "—"}</td>
                      <td><StatusBadge status={e.status} /></td>
                      <td className="text-right">
                        {e.status === "pending" ? (
                          <button className="btn-primary !px-3 !py-1.5" onClick={() => setReview(e)}>
                            Review
                          </button>
                        ) : (
                          <span className="text-xs text-slate-400">{e.points_awarded != null ? `${e.points_awarded} pts` : "Reviewed"}</span>
                        )}
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

      {review && (
        <ReviewModal
          evidence={review}
          onClose={() => setReview(null)}
          onDone={() => {
            setReview(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

function EvidenceLink({ evidence }: { evidence: any }) {
  if (evidence.link_url) {
    return (
      <a href={evidence.link_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm text-brand-600 hover:underline">
        <LinkIcon className="h-4 w-4" /> Open link
      </a>
    );
  }
  if (evidence.file_key) {
    return (
      <a
        href={`/api/v1/files/${evidence.file_key}`}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 text-sm text-brand-600 hover:underline"
      >
        <FileText className="h-4 w-4" /> {evidence.file_name || "Download file"}
        {evidence.file_size ? <span className="text-xs text-slate-400">({formatBytes(evidence.file_size)})</span> : null}
      </a>
    );
  }
  return <span className="text-xs text-slate-400">{humanize(evidence.evidence_type || "none")}</span>;
}

function ReviewModal({ evidence, onClose, onDone }: { evidence: any; onClose: () => void; onDone: () => void }) {
  const { push } = useToast();
  const [decision, setDecision] = useState<"approved" | "rejected">("approved");
  const [points, setPoints] = useState(String(evidence.points_awarded ?? 0));
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await api.post(`/faculty/task-evidence/${evidence.id}/review`, {
        decision,
        points: decision === "approved" ? Number(points) : undefined,
        feedback,
      });
      push(decision === "approved" ? "Evidence approved." : "Evidence rejected.", "success");
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
      title={evidence.task || "Task evidence"}
      subtitle={`${evidence.student} · submitted ${evidence.submitted_at ? formatDateTime(evidence.submitted_at) : "—"}`}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            className={decision === "approved" ? "btn-primary" : "btn-danger"}
            onClick={submit}
            disabled={busy}
          >
            {decision === "approved" ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
            {decision === "approved" ? "Approve" : "Reject"}
          </button>
        </>
      }
    >
      <div className="space-y-5">
        <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-slate-400">Evidence</span>
            <EvidenceLink evidence={evidence} />
          </div>
          {evidence.notes && <p className="mt-2 whitespace-pre-wrap">{evidence.notes}</p>}
        </div>

        <Field label="Decision">
          <div className="flex gap-2">
            <button
              className={`btn-secondary flex-1 ${decision === "approved" ? "!border-emerald-500 !text-emerald-700" : ""}`}
              onClick={() => setDecision("approved")}
            >
              <CheckCircle2 className="h-4 w-4" /> Approve
            </button>
            <button
              className={`btn-secondary flex-1 ${decision === "rejected" ? "!border-red-500 !text-red-700" : ""}`}
              onClick={() => setDecision("rejected")}
            >
              <XCircle className="h-4 w-4" /> Reject
            </button>
          </div>
        </Field>

        {decision === "approved" && (
          <Field label="Points to award" hint="Cannot exceed the task's potential points.">
            <input className="input" type="number" min={0} value={points} onChange={(e) => setPoints(e.target.value)} />
          </Field>
        )}

        <Field label="Feedback" hint={decision === "rejected" ? "Explain why the evidence was rejected." : "Optional note for the student."}>
          <textarea className="input min-h-24" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
        </Field>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Badge tone="slate">{humanize(evidence.evidence_type)}</Badge>
          {evidence.submission_date && <span>Submission date: {evidence.submission_date}</span>}
        </div>
      </div>
    </Modal>
  );
}
