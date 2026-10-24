import { useState } from "react";
import { AlertTriangle, Info, Scale } from "lucide-react";
import { useApi } from "../../lib/hooks";
import { api } from "../../lib/api";
import { formatDate, humanize } from "../../lib/format";
import { Card, EmptyState, Field, Modal, PageHeader, PageLoader, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function MyAppeals() {
  const { data, loading, reload } = useApi<any[]>("/student/appeals");
  const { data: attempts } = useApi<any[]>("/student/assessments");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ attempt_id: "", reason: "", supporting_info: "" });
  const [busy, setBusy] = useState(false);
  const { push } = useToast();

  const eligibleAttempts = (attempts || []).flatMap((a: any) => (a.latest_attempt && a.latest_attempt.status === "graded" ? [{ id: a.latest_attempt.id, label: `${a.title} · score ${a.latest_attempt.score}/${a.latest_attempt.total_marks}` }] : []));

  async function submit() {
    setBusy(true);
    try {
      await api.post("/student/appeals", {
        attempt_id: form.attempt_id ? Number(form.attempt_id) : undefined,
        reason: form.reason,
        supporting_info: form.supporting_info,
      });
      push("Appeal submitted for review.", "success");
      setOpen(false);
      setForm({ attempt_id: "", reason: "", supporting_info: "" });
      reload();
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  const assignedAlerts = (data || []).filter(
    (a: any) => a.instruction_message || (a.status === "in_review" && a.assigned_reviewer)
  );

  return (
    <div>
      <PageHeader
        title="My Appeals"
        subtitle="Raise an appeal if you believe a score or points decision is incorrect."
        actions={<button className="btn-primary" onClick={() => setOpen(true)}>New appeal</button>}
      />

      {/* Prominent Faculty Instruction Alert Banner */}
      {assignedAlerts.map((a: any) => (
        <div
          key={`alert-${a.id}`}
          className="mb-6 rounded-2xl border border-amber-300 bg-amber-50/90 p-4 text-amber-900 flex items-start gap-3.5 shadow-sm"
        >
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-bold text-sm text-amber-950">
              Notice: You are instructed to meet the faculty
            </p>
            <p className="text-xs text-amber-900 leading-relaxed">
              Regarding your appeal for <strong>{a.assessment || "Assessment"}</strong>: Please meet faculty member{" "}
              <strong>{a.assigned_reviewer}</strong> {a.assigned_reviewer_email && `(${a.assigned_reviewer_email})`} in person for verification and resolution.
            </p>
          </div>
        </div>
      ))}

      <Card pad={false}>
        {loading ? (
          <PageLoader />
        ) : !data?.length ? (
          <EmptyState icon={<Scale className="h-6 w-6" />} title="No appeals" description="You haven't raised any appeals." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Assessment</th>
                  <th>Reason</th>
                  <th>Original</th>
                  <th>New</th>
                  <th>Status</th>
                  <th>Faculty Instruction / Remarks</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {data.map((a: any) => (
                  <tr key={a.id}>
                    <td className="font-medium text-slate-800">{a.assessment || "Task evidence"}</td>
                    <td className="max-w-xs truncate text-slate-500">{a.reason}</td>
                    <td>{a.original_score ?? "—"}</td>
                    <td>{a.new_score ?? "—"}</td>
                    <td><StatusBadge status={a.status} /></td>
                    <td className="max-w-sm text-xs">
                      {a.instruction_message ? (
                        <span className="inline-flex items-center gap-1.5 font-semibold text-amber-800 bg-amber-100/80 px-2 py-0.5 rounded-md border border-amber-200">
                          <AlertTriangle className="h-3 w-3 shrink-0 text-amber-600" />
                          You are instructed to meet the faculty ({a.assigned_reviewer})
                        </span>
                      ) : a.review_comments ? (
                        <span className="text-slate-600">{a.review_comments}</span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="text-slate-500">{formatDate(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Raise an appeal"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" onClick={submit} disabled={busy || form.reason.length < 10}>Submit appeal</button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Graded assessment">
            <select className="input" value={form.attempt_id} onChange={(e) => setForm({ ...form, attempt_id: e.target.value })}>
              <option value="">Select an assessment (optional)</option>
              {eligibleAttempts.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            </select>
          </Field>
          <Field label="Reason" hint="Explain clearly why the decision should be reviewed (min 10 characters).">
            <textarea className="input min-h-28" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          </Field>
          <Field label="Supporting information" hint="Optional links or references.">
            <textarea className="input min-h-20" value={form.supporting_info} onChange={(e) => setForm({ ...form, supporting_info: e.target.value })} />
          </Field>
        </div>
      </Modal>
    </div>
  );
}
