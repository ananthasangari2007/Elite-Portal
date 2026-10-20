import { useState, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import { Card, EmptyState, Field, PageHeader, PageLoader, Pagination, StatusBadge } from "../../components/ui";

export default function CoordinatorSubmissions() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState(searchParams.get("status") || "");
  const [domainId, setDomainId] = useState(searchParams.get("domain_id") || "");
  const [assessmentId, setAssessmentId] = useState(searchParams.get("assessment_id") || "");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const params = useMemo(() => ({
    status: status || undefined,
    domain_id: domainId || undefined,
    assessment_id: assessmentId || undefined,
    student: search || undefined,
    page,
  }), [status, domainId, assessmentId, search, page]);

  const { data, meta, loading } = useApi<any[]>("/coordinator/submissions", params);
  const { data: domains } = useApi<any[]>("/coordinator/domains");

  return (
    <div>
      <PageHeader title="Submissions" subtitle="Review and grade assessment submissions" />

      <Card className="mb-4">
        <div className="grid gap-3 md:grid-cols-4">
          <Field label="Status">
            <select className="input" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
              <option value="">All</option>
              <option value="submitted">Submitted</option>
              <option value="graded">Graded</option>
            </select>
          </Field>
          <Field label="Domain">
            <select className="input" value={domainId} onChange={(e) => { setPage(1); setDomainId(e.target.value); }}>
              <option value="">All domains</option>
              {domains?.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Student">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input className="input pl-9" value={search} onChange={(e) => { setPage(1); setSearch(e.target.value); }} placeholder="Name, reg no" />
            </div>
          </Field>
        </div>
      </Card>

      {loading ? (
        <PageLoader />
      ) : !data?.length ? (
        <Card><EmptyState title="No submissions found" /></Card>
      ) : (
        <Card pad={false}>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Assessment</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Score</th>
                  <th>Submitted</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.map((s: any) => (
                  <tr key={s.id}>
                    <td className="text-slate-700">{s.student} {s.register_number ? `(${s.register_number})` : ""}</td>
                    <td className="text-slate-500">{s.assessment}</td>
                    <td className="text-slate-500">{humanize(s.assessment_type)}</td>
                    <td><StatusBadge status={s.status} /></td>
                    <td className="text-slate-500">{s.score != null ? `${s.score}/${s.total_marks || 0}` : "—"}</td>
                    <td className="text-slate-500">{s.submitted_at ? formatDateTime(s.submitted_at) : "—"}</td>
                    <td className="text-right">
                      <button className="btn-secondary !px-3 !py-1.5" onClick={() => navigate(`/coordinator/submissions/${s.id}`)}>
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={meta?.page || 1} pages={meta?.pages || 1} total={meta?.total} onPage={setPage} />
        </Card>
      )}
    </div>
  );
}