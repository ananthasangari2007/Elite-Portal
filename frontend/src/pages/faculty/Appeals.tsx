import { useMemo, useState } from "react";
import { Gavel, Scale, UserCheck } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
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
  { key: "open", label: "Open" },
  { key: "in_review", label: "In review" },
  { key: "resolved", label: "Resolved" },
  { key: "rejected", label: "Rejected" },
  { key: "all", label: "All" },
];

export default function AppealsQueue() {
  const [tab, setTab] = useState("open");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<any>(null);

  const params = useMemo(() => {
    const base: Record<string, any> = { page };
    if (tab !== "all") base.status = tab;
    return base;
  }, [tab, page]);

  const { data, meta, loading, error, reload } = useApi<any[]>("/faculty/appeals", params);
  const rows = data || [];

  return (
    <div>
      <PageHeader
        title="Appeals"
        subtitle="Review student appeals on assessment scores and task points."
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
          <PageLoader label="Loading appeals" />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !rows.length ? (
          <EmptyState icon={<Scale className="h-6 w-6" />} title="No appeals here" description="Appeals raised by students will appear in this queue." />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Reference</th>
                    <th>Original</th>
                    <th>Reason</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((a: any) => (
                    <tr key={a.id}>
                      <td>
                        <p className="font-medium text-slate-800">{a.student}</p>
                        <p className="text-xs text-slate-400">{a.register_number}</p>
                      </td>
                      <td>
                        <p className="text-slate-700">{a.reference || "—"}</p>
                        <Badge tone="slate">{humanize(a.reference_type)}</Badge>
                      </td>
                      <td className="text-slate-600">{a.original_score ?? "—"}</td>
                      <td className="max-w-xs">
                        <p className="line-clamp-2 text-xs text-slate-500">{a.reason}</p>
                      </td>
                      <td><StatusBadge status={a.status} /></td>
                      <td className="whitespace-nowrap text-slate-500">{a.created_at ? formatDateTime(a.created_at) : "—"}</td>
                      <td className="text-right">
                        <button className="btn-secondary !px-3 !py-1.5" onClick={() => setSelected(a)}>
                          Open
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

      {selected && (
        <AppealModal
          appeal={selected}
          onClose={() => setSelected(null)}
          onDone={() => {
            setSelected(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

function AppealModal({ appeal, onClose, onDone }: { appeal: any; onClose: () => void; onDone: () => void }) {
  const { push } = useToast();
  const [assigning, setAssigning] = useState(false);
  const [action, setAction] = useState<"overturn" | "partial" | "reject">("overturn");
  const [newScore, setNewScore] = useState(String(appeal.original_score ?? 0));
  const [comments, setComments] = useState("");
  const [busy, setBusy] = useState(false);

  const closed = appeal.status === "resolved" || appeal.status === "rejected";

  async function assign() {
    setAssigning(true);
    try {
      await api.post(`/faculty/appeals/${appeal.id}/assign`, { assign: true });
      push("Appeal assigned to you.", "success");
      onDone();
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setAssigning(false);
    }
  }

  async function decide() {
    setBusy(true);
    try {
      await api.post(`/faculty/appeals/${appeal.id}/decision`, {
        action,
        review_comments: comments,
        new_score: action === "reject" ? undefined : Number(newScore),
      });
      push("Appeal decision recorded.", "success");
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
      title={appeal.reference || "Appeal"}
      subtitle={`${appeal.student} · ${humanize(appeal.reference_type)} · ${appeal.register_number || ""}`}
      size="lg"
      footer={
        closed ? (
          <button className="btn-secondary" onClick={onClose}>
            Close
          </button>
        ) : (
          <>
            <button className="btn-secondary" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            {!appeal.assigned_to && (
              <button className="btn-secondary" onClick={assign} disabled={assigning}>
                <UserCheck className="h-4 w-4" /> Assign to me
              </button>
            )}
            <button className={action === "reject" ? "btn-danger" : "btn-primary"} onClick={decide} disabled={busy}>
              <Gavel className="h-4 w-4" /> Record decision
            </button>
          </>
        )
      }
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={appeal.status} />
          {appeal.decision && <Badge tone="violet">Decision: {humanize(appeal.decision)}</Badge>}
          <span className="text-xs text-slate-400">Raised {appeal.created_at ? formatDateTime(appeal.created_at) : "—"}</span>
          {appeal.assigned_reviewer && <span className="text-xs text-slate-500">Assigned to {appeal.assigned_reviewer}</span>}
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Info label="Original score" value={appeal.original_score ?? "—"} />
          <Info label="New score" value={appeal.new_score ?? "—"} />
          <Info label="Reference" value={humanize(appeal.reference_type)} />
          <Info label="Decision" value={appeal.decision ? humanize(appeal.decision) : "Pending"} />
        </div>

        <div className="rounded-xl bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase text-slate-400">Reason</p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{appeal.reason || "—"}</p>
        </div>

        {appeal.supporting_info && (
          <div className="rounded-xl border border-slate-200 p-4">
            <p className="text-xs font-semibold uppercase text-slate-400">Supporting information</p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{appeal.supporting_info}</p>
          </div>
        )}

        {appeal.review_comments && (
          <div className="rounded-xl bg-brand-50 p-4">
            <p className="text-xs font-semibold uppercase text-brand-500">Review comments</p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{appeal.review_comments}</p>
          </div>
        )}

        {!closed && (
          <div className="space-y-4 border-t border-slate-100 pt-4">
            <Field label="Decision">
              <select className="input" value={action} onChange={(e) => setAction(e.target.value as any)}>
                <option value="overturn">Approve — overturn score</option>
                <option value="partial">Partial approval</option>
                <option value="reject">Reject appeal</option>
              </select>
            </Field>

            {action !== "reject" && (
              <Field label="New score" hint="The awarded score will be updated automatically.">
                <input className="input" type="number" min={0} value={newScore} onChange={(e) => setNewScore(e.target.value)} />
              </Field>
            )}

            <Field label="Comments">
              <textarea className="input min-h-24" value={comments} onChange={(e) => setComments(e.target.value)} />
            </Field>
          </div>
        )}
      </div>
    </Modal>
  );
}

function Info({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3 text-center">
      <p className="text-sm font-semibold text-slate-800">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}
