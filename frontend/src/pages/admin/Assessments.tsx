import { useState } from "react";
import { ClipboardCheck, RotateCcw } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, EmptyState, ErrorState, Field, Modal, PageHeader, Pagination, PageLoader, Spinner, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

const STATUSES = ["draft", "scheduled", "published", "closed"];
const TYPES = ["mcq", "coding", "mixed"];

export default function AdminAssessments() {
  const [page, setPage] = useState(1);
  const [domainId, setDomainId] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [reopen, setReopen] = useState<any>(null);
  const { data: domains } = useApi<any[]>("/domains");

  const params: any = { page, per_page: 25 };
  if (domainId) params.domain_id = domainId;
  if (status) params.status = status;
  if (type) params.type = type;

  const { data, meta, loading, error, reload } = useApi<any[]>("/admin/assessments", params);

  function reset(next: () => void) {
    setPage(1);
    next();
  }

  return (
    <div>
      <PageHeader title="Assessments" subtitle="All assessments across domains. Reopen closed windows when required." />

      <Card className="mb-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Domain">
            <select className="input" value={domainId} onChange={(e) => reset(() => setDomainId(e.target.value))}>
              <option value="">All domains</option>
              {(domains || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
          <Field label="Status">
            <select className="input" value={status} onChange={(e) => reset(() => setStatus(e.target.value))}>
              <option value="">All statuses</option>
              {STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
            </select>
          </Field>
          <Field label="Type">
            <select className="input" value={type} onChange={(e) => reset(() => setType(e.target.value))}>
              <option value="">All types</option>
              {TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
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
          <EmptyState icon={<ClipboardCheck className="h-6 w-6" />} title="No assessments found" description="Try adjusting the filters." />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Domain</th>
                    <th>Type</th>
                    <th>Questions</th>
                    <th>Window</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((a) => (
                    <tr key={a.id}>
                      <td className="font-medium text-slate-800">{a.title}</td>
                      <td className="text-slate-700">{a.domain || "—"}</td>
                      <td><Badge tone="violet">{humanize(a.assessment_type)}</Badge></td>
                      <td className="text-slate-500">{a.question_count ?? 0} · {a.total_marks} marks</td>
                      <td className="whitespace-nowrap text-xs text-slate-500">
                        {a.scheduled_start ? formatDateTime(a.scheduled_start) : "Open"} → {a.scheduled_end ? formatDateTime(a.scheduled_end) : "—"}
                      </td>
                      <td><StatusBadge status={a.status} /></td>
                      <td className="text-right">
                        <button className="btn-secondary !px-3 !py-1.5" onClick={() => setReopen(a)}>
                          <RotateCcw className="h-4 w-4" /> Reopen
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

      {reopen && (
        <ReopenModal
          assessment={reopen}
          onClose={() => setReopen(null)}
          onSaved={() => { setReopen(null); reload(); }}
        />
      )}
    </div>
  );
}

function ReopenModal({ assessment, onClose, onSaved }: { assessment: any; onClose: () => void; onSaved: () => void }) {
  const [scheduledEnd, setScheduledEnd] = useState("");
  const [busy, setBusy] = useState(false);
  const { push } = useToast();

  async function submit() {
    setBusy(true);
    try {
      await api.post(`/admin/assessments/${assessment.id}/reopen`, {
        scheduled_end: scheduledEnd ? new Date(scheduledEnd).toISOString() : null,
      });
      push("Assessment reopened.", "success");
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
      title="Reopen assessment"
      subtitle={assessment.title}
      size="sm"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn-primary" onClick={submit} disabled={busy}>
            {busy ? <Spinner className="text-white" /> : "Reopen"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-slate-600">Reopening sets the assessment back to <strong>published</strong>. Optionally extend the closing window.</p>
        <Field label="New scheduled end" hint="Leave blank to keep the existing window.">
          <input type="datetime-local" className="input" value={scheduledEnd} onChange={(e) => setScheduledEnd(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
