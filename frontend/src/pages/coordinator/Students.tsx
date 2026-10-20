import { useState } from "react";
import { Search, Users } from "lucide-react";
import { useApi } from "../../lib/hooks";
import { formatPoints, humanize } from "../../lib/format";
import { Card, EmptyState, Field, Modal, PageHeader, PageLoader, Pagination, ProgressBar } from "../../components/ui";
import { api } from "../../lib/api";

export default function CoordinatorStudents() {
  const [search, setSearch] = useState("");
  const [domainId, setDomainId] = useState<string>("");
  const [page, setPage] = useState(1);
  const params = { search, domain_id: domainId || undefined, page };
  const { data, meta, loading } = useApi<any[]>("/coordinator/students", params);
  const { data: domains } = useApi<any[]>("/coordinator/domains");
  const [detail, setDetail] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  async function openDetail(id: number) {
    setLoadingDetail(true);
    setDetail(null);
    try {
      const res = await api.get<any>(`/coordinator/students/${id}`);
      setDetail(res);
    } finally {
      setLoadingDetail(false);
    }
  }

  return (
    <div>
      <PageHeader title="Students" subtitle="Track enrolments, progress and points" />

      <Card className="mb-4">
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="Search">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                className="input pl-9"
                value={search}
                onChange={(e) => {
                  setPage(1);
                  setSearch(e.target.value);
                }}
                placeholder="Name, reg no, email"
              />
            </div>
          </Field>
          <Field label="Domain">
            <select
              className="input"
              value={domainId}
              onChange={(e) => {
                setPage(1);
                setDomainId(e.target.value);
              }}
            >
              <option value="">All domains</option>
              {domains?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </Card>

      {loading ? (
        <PageLoader />
      ) : !data?.length ? (
        <Card>
          <EmptyState icon={<Users className="h-6 w-6" />} title="No students found" />
        </Card>
      ) : (
        <Card pad={false}>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Register No</th>
                  <th>Department</th>
                  <th>Status</th>
                  <th>Completion</th>
                  <th>Total Points</th>
                  <th>Assessment Attempts</th>
                </tr>
              </thead>
              <tbody>
                {data.map((s: any) => (
                  <tr key={s.id} className="cursor-pointer hover:bg-slate-50" onClick={() => openDetail(s.id)}>
                    <td className="font-medium text-slate-800">{s.name}</td>
                    <td className="text-slate-500">{s.register_number}</td>
                    <td className="text-slate-500">{s.department || "—"}</td>
                    <td className="text-slate-500">{humanize(s.status)}</td>
                    <td className="text-slate-500">{s.completion_percent}%</td>
                    <td className="text-slate-500">{formatPoints(s.total)}</td>
                    <td className="text-slate-500">{s.assessment_attempts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={meta?.page || 1} pages={meta?.pages || 1} total={meta?.total} onPage={setPage} />
        </Card>
      )}

      <Modal open={!!detail || loadingDetail} onClose={() => setDetail(null)} title="Student Details" size="lg">
        {loadingDetail && <PageLoader />}
        {detail && (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="text-sm font-medium text-slate-800">{detail.student.name}</p>
                <p className="text-xs text-slate-500">{detail.student.register_number} · {detail.student.email}</p>
                <p className="text-xs text-slate-500">{detail.student.department || "—"} {detail.student.year ? "· " + detail.student.year : ""}</p>
              </div>
            </div>

            {detail.domains?.length > 0 && (
              <div>
                <p className="mb-2 text-sm font-semibold text-slate-800">Domain Progress</p>
                <div className="space-y-2">
                  {detail.domains.map((d: any) => (
                    <div key={d.domain_id} className="rounded-xl border border-slate-200 p-3">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-slate-800">{d.domain}</p>
                        <span className="text-xs text-slate-500">{d.completed_days}/{d.published_days} ({d.percent}%)</span>
                      </div>
                      <ProgressBar value={d.percent} className="mt-2" tone="brand" />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {detail.points && (
              <div>
                <p className="mb-2 text-sm font-semibold text-slate-800">Points Breakdown</p>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Total</p><p className="text-lg font-semibold text-slate-800">{formatPoints(detail.points.total)}</p></div>
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Tasks</p><p className="text-lg font-semibold text-slate-800">{formatPoints(detail.points.tasks)}</p></div>
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Assessments</p><p className="text-lg font-semibold text-slate-800">{formatPoints(detail.points.assessments)}</p></div>
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Betting</p><p className="text-lg font-semibold text-slate-800">{formatPoints(detail.points.betting)}</p></div>
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Adjustments</p><p className="text-lg font-semibold text-slate-800">{formatPoints(detail.points.adjustments)}</p></div>
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Bonus</p><p className="text-lg font-semibold text-slate-800">{formatPoints(detail.points.bonus)}</p></div>
                </div>
              </div>
            )}

            {detail.assessments?.length > 0 && (
              <div>
                <p className="mb-2 text-sm font-semibold text-slate-800">Recent Assessment Attempts</p>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Assessment</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.assessments.map((a: any) => (
                        <tr key={a.id}>
                          <td className="text-slate-700">{a.assessment}</td>
                          <td className="text-slate-500">{humanize(a.assessment_type)}</td>
                          <td className="text-slate-500">{humanize(a.status)}</td>
                          <td className="text-slate-500">{a.score ?? 0}/{a.total_marks ?? 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}