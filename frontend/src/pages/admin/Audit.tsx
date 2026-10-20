import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, ScrollText, Search } from "lucide-react";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, EmptyState, ErrorState, Field, PageHeader, Pagination, PageLoader } from "../../components/ui";

export default function AdminAudit() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [actorId, setActorId] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const params: any = { page, per_page: 40 };
  if (action.trim()) params.action = action.trim();
  if (actorId.trim()) params.actor_id = actorId.trim();

  const { data, meta, loading, error, reload } = useApi<any[]>("/admin/audit-logs", params);

  function reset(next: () => void) {
    setPage(1);
    next();
  }

  return (
    <div>
      <PageHeader title="Audit Log" subtitle="A complete trail of administrative actions across the platform." />

      <Card className="mb-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Action">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input className="input pl-9" placeholder="e.g. user.update" value={action} onChange={(e) => reset(() => setAction(e.target.value))} />
            </div>
          </Field>
          <Field label="Actor ID">
            <input
              type="number"
              className="input"
              placeholder="Filter by actor user id"
              value={actorId}
              onChange={(e) => reset(() => setActorId(e.target.value))}
            />
          </Field>
        </div>
      </Card>

      <Card pad={false}>
        {loading ? (
          <PageLoader />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !data?.length ? (
          <EmptyState icon={<ScrollText className="h-6 w-6" />} title="No audit records" description="Try adjusting the filters." />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th className="w-8"></th>
                    <th>Time</th>
                    <th>Actor</th>
                    <th>Action</th>
                    <th>Target</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((r) => (
                    <Fragment key={r.id}>
                      <tr className="cursor-pointer hover:bg-slate-50" onClick={() => setExpanded(expanded === r.id ? null : r.id)}>
                        <td className="text-slate-400">
                          {expanded === r.id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </td>
                        <td className="whitespace-nowrap text-slate-500">{formatDateTime(r.created_at)}</td>
                        <td>
                          <p className="text-slate-800">{r.actor}</p>
                          {r.actor_role && <p className="text-xs text-slate-400">{humanize(r.actor_role)}</p>}
                        </td>
                        <td><Badge tone="blue">{r.action}</Badge></td>
                        <td className="text-slate-600">
                          {r.target_type ? `${r.target_type}${r.target_id ? ` #${r.target_id}` : ""}` : "—"}
                        </td>
                        <td className="text-slate-500">{r.description || "—"}</td>
                      </tr>
                      {expanded === r.id && (
                        <tr className="bg-slate-50">
                          <td></td>
                          <td colSpan={5}>
                            <div className="grid gap-3 py-2 sm:grid-cols-2">
                              <div>
                                <p className="mb-1 text-xs font-semibold uppercase text-slate-400">Old value</p>
                                <pre className="max-h-56 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100 scrollbar-thin">
                                  {r.old_value ? JSON.stringify(r.old_value, null, 2) : "—"}
                                </pre>
                              </div>
                              <div>
                                <p className="mb-1 text-xs font-semibold uppercase text-slate-400">New value</p>
                                <pre className="max-h-56 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100 scrollbar-thin">
                                  {r.new_value ? JSON.stringify(r.new_value, null, 2) : "—"}
                                </pre>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={meta?.page || 1} pages={meta?.pages || 1} total={meta?.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
