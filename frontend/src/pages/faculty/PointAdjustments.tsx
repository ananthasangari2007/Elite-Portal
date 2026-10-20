import { useMemo, useState } from "react";
import { Coins, Plus, Search, SlidersHorizontal, TrendingDown, TrendingUp } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import {
  Avatar,
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

const REQUEST_TYPES = [
  "assessment_correction",
  "task_recount",
  "bonus",
  "penalty_reversal",
  "other",
];

export default function PointAdjustments() {
  const [tab, setTab] = useState("pending");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [review, setReview] = useState<any>(null);

  const params = useMemo(() => ({ status: tab, page }), [tab, page]);
  const { data, meta, loading, error, reload } = useApi<any[]>("/faculty/point-adjustments", params);
  const rows = data || [];

  return (
    <div>
      <PageHeader
        title="Point Adjustments"
        subtitle="Request and review corrections to student point totals."
        actions={
          <button className="btn-primary" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> New adjustment
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
          <PageLoader label="Loading adjustments" />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !rows.length ? (
          <EmptyState icon={<SlidersHorizontal className="h-6 w-6" />} title="No adjustments here" description="Point adjustment requests will appear in this list." />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Type</th>
                    <th>Current</th>
                    <th>Requested</th>
                    <th>Delta</th>
                    <th>Reason</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r: any) => (
                    <tr key={r.id}>
                      <td>
                        <p className="font-medium text-slate-800">{r.student}</p>
                        <p className="text-xs text-slate-400">{r.register_number}</p>
                      </td>
                      <td><Badge tone="blue">{humanize(r.request_type)}</Badge></td>
                      <td className="text-slate-600">{r.current_points}</td>
                      <td className="text-slate-600">{r.requested_points}</td>
                      <td>
                        <span className={r.delta >= 0 ? "font-semibold text-emerald-600" : "font-semibold text-red-600"}>
                          {r.delta >= 0 ? "+" : ""}{r.delta}
                        </span>
                      </td>
                      <td className="max-w-xs">
                        <p className="line-clamp-2 text-xs text-slate-500">{r.reason}</p>
                      </td>
                      <td><StatusBadge status={r.status} /></td>
                      <td className="text-right">
                        {r.status === "pending" ? (
                          <button className="btn-secondary !px-3 !py-1.5" onClick={() => setReview(r)}>
                            Review
                          </button>
                        ) : (
                          <span className="text-xs text-slate-400">{r.reviewed_by || "Reviewed"}</span>
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

      {createOpen && (
        <NewAdjustmentModal
          onClose={() => setCreateOpen(false)}
          onDone={() => {
            setCreateOpen(false);
            reload();
          }}
        />
      )}

      {review && (
        <ReviewModal
          adjustment={review}
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

function NewAdjustmentModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { push } = useToast();
  const [search, setSearch] = useState("");
  const [student, setStudent] = useState<any>(null);
  const [requestType, setRequestType] = useState(REQUEST_TYPES[0]);
  const [reason, setReason] = useState("");
  const [requestedPoints, setRequestedPoints] = useState("");
  const [busy, setBusy] = useState(false);

  const params = useMemo(() => ({ search, per_page: 20 }), [search]);
  const { data, loading } = useApi<any[]>("/coordinator/students", params);
  const students = data || [];

  async function submit() {
    if (!student) return push("Select a student first.", "error");
    setBusy(true);
    try {
      await api.post("/faculty/point-adjustments", {
        student_id: student.id,
        request_type: requestType,
        reason,
        requested_points: Number(requestedPoints),
      });
      push("Point adjustment requested.", "success");
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
      title="New point adjustment"
      subtitle="Adjust a student's total points with a documented reason."
      size="lg"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn-primary" onClick={submit} disabled={busy || !student || reason.trim().length < 5 || requestedPoints === ""}>
            Submit request
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {student ? (
          <div className="flex items-center gap-3 rounded-xl border border-brand-200 bg-brand-50/50 p-3">
            <Avatar name={student.name} size={40} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-800">{student.name}</p>
              <p className="text-xs text-slate-500">
                {student.register_number} · {student.department || "—"} · {student.total ?? 0} pts
              </p>
            </div>
            <button className="btn-secondary !px-3 !py-1.5" onClick={() => setStudent(null)}>
              Change
            </button>
          </div>
        ) : (
          <Field label="Student">
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3">
              <Search className="h-4 w-4 text-slate-400" />
              <input
                className="input border-0 focus:ring-0"
                placeholder="Search by name, register number or email…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="mt-2 max-h-56 overflow-y-auto rounded-xl border border-slate-200 scrollbar-thin">
              {loading ? (
                <PageLoader label="Searching" />
              ) : !students.length ? (
                <p className="p-4 text-sm text-slate-400">No students found.</p>
              ) : (
                students.map((s: any) => (
                  <button
                    key={s.id}
                    className="flex w-full items-center gap-3 border-b border-slate-50 px-3 py-2.5 text-left last:border-0 hover:bg-slate-50"
                    onClick={() => setStudent(s)}
                  >
                    <Avatar name={s.name} size={32} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-slate-700">{s.name}</p>
                      <p className="truncate text-xs text-slate-400">{s.register_number} · {s.department || "—"}</p>
                    </div>
                    <span className="text-xs text-slate-400">{s.total ?? 0} pts</span>
                  </button>
                ))
              )}
            </div>
          </Field>
        )}

        <Field label="Request type">
          <select className="input" value={requestType} onChange={(e) => setRequestType(e.target.value)}>
            {REQUEST_TYPES.map((t) => (
              <option key={t} value={t}>{humanize(t)}</option>
            ))}
          </select>
        </Field>

        <Field label="Requested total points" hint="The student's new total after the adjustment.">
          <input className="input" type="number" min={0} value={requestedPoints} onChange={(e) => setRequestedPoints(e.target.value)} />
        </Field>

        <Field label="Reason" hint="Minimum 5 characters.">
          <textarea className="input min-h-24" value={reason} onChange={(e) => setReason(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

function ReviewModal({ adjustment, onClose, onDone }: { adjustment: any; onClose: () => void; onDone: () => void }) {
  const { push } = useToast();
  const [decision, setDecision] = useState<"approved" | "rejected">("approved");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await api.post(`/faculty/point-adjustments/${adjustment.id}/review`, {
        decision,
        review_notes: notes,
      });
      push(`Adjustment ${decision}.`, "success");
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
      title="Review adjustment"
      subtitle={`${adjustment.student} · ${humanize(adjustment.request_type)}`}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className={decision === "approved" ? "btn-primary" : "btn-danger"} onClick={submit} disabled={busy}>
            {decision === "approved" ? "Approve" : "Reject"}
          </button>
        </>
      }
    >
      <div className="space-y-5">
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl bg-slate-50 p-3 text-center">
            <p className="text-sm font-semibold text-slate-800">{adjustment.current_points}</p>
            <p className="text-xs text-slate-500">Current</p>
          </div>
          <div className="rounded-xl bg-slate-50 p-3 text-center">
            <p className="text-sm font-semibold text-slate-800">{adjustment.requested_points}</p>
            <p className="text-xs text-slate-500">Requested</p>
          </div>
          <div className="rounded-xl bg-slate-50 p-3 text-center">
            <p className={`text-sm font-semibold ${adjustment.delta >= 0 ? "text-emerald-600" : "text-red-600"}`}>
              {adjustment.delta >= 0 ? "+" : ""}{adjustment.delta}
            </p>
            <p className="text-xs text-slate-500">Delta</p>
          </div>
        </div>

        <div className="rounded-xl bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase text-slate-400">Reason</p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{adjustment.reason}</p>
          <p className="mt-2 text-xs text-slate-400">
            Requested by {adjustment.requested_by || "—"} · {adjustment.created_at ? formatDateTime(adjustment.created_at) : ""}
          </p>
        </div>

        <Field label="Decision">
          <div className="flex gap-2">
            <button
              className={`btn-secondary flex-1 ${decision === "approved" ? "!border-emerald-500 !text-emerald-700" : ""}`}
              onClick={() => setDecision("approved")}
            >
              <TrendingUp className="h-4 w-4" /> Approve
            </button>
            <button
              className={`btn-secondary flex-1 ${decision === "rejected" ? "!border-red-500 !text-red-700" : ""}`}
              onClick={() => setDecision("rejected")}
            >
              <TrendingDown className="h-4 w-4" /> Reject
            </button>
          </div>
        </Field>

        <Field label="Review notes">
          <textarea className="input min-h-20" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Coins className="h-4 w-4" /> Approving applies the delta to the student's ledger.
        </div>
      </div>
    </Modal>
  );
}
