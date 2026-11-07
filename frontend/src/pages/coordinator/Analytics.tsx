import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from "recharts";
import {
  BarChart as BarIcon,
  ChevronLeft,
  ChevronRight,
  Download,
  Search,
  TrendingUp,
  UserCheck,
  Users,
} from "lucide-react";
import { useApi } from "../../lib/hooks";
import { Card, EmptyState, MetricCard, PageHeader, PageLoader, ProgressBar } from "../../components/ui";
import { api } from "../../lib/api";
import { formatPoints } from "../../lib/format";

export default function CoordinatorAnalytics() {
  const { data, loading } = useApi<any>("/coordinator/analytics");
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [dept, setDept] = useState("all");

  const progressParams = { page, per_page: 15, q: query || undefined, department: dept !== "all" ? dept : undefined };
  const {
    data: studentsData,
    meta: studentsMeta,
    loading: studentsLoading,
  } = useApi<any[]>("/coordinator/students/progress", progressParams);

  async function downloadStudents() {
    try {
      await api.download("/coordinator/exports/students.csv", "students.csv");
    } catch (e) {}
  }

  async function downloadSubmissions() {
    try {
      await api.download("/coordinator/exports/submissions.csv", "submissions.csv");
    } catch (e) {}
  }

  if (loading) return <PageLoader />;
  if (!data) return <EmptyState title="Could not load analytics" />;

  const totals = data.totals || {};
  const learning = data.learning || [];
  const status = data.status_counts || {};
  const scoreDist = data.score_distribution || data.grading_workload || [];
  const studentList = studentsData || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics & Student Performance"
        subtitle="Holistic learning completion, assessment insights and per-student progress explorer."
        actions={
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={downloadStudents}>
              <Download className="h-4 w-4" /> Students CSV
            </button>
            <button className="btn-secondary" onClick={downloadSubmissions}>
              <Download className="h-4 w-4" /> Submissions CSV
            </button>
          </div>
        }
      />

      {/* KPI Metric Cards */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Enrolled Students" value={totals.students} icon={<Users className="h-5 w-5" />} tone="brand" />
        <MetricCard label="Assessments Authored" value={totals.assessments} icon={<BarIcon className="h-5 w-5" />} tone="violet" />
        <MetricCard label="Total Submissions" value={totals.submissions} icon={<TrendingUp className="h-5 w-5" />} tone="green" />
        <MetricCard label="Average Score" value={`${totals.average_score_percent}%`} icon={<TrendingUp className="h-5 w-5" />} tone="amber" />
      </div>

      {/* Charts Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Curriculum Completion by Domain" pad={false}>
          {!learning.length ? (
            <EmptyState title="No learning data" />
          ) : (
            <div className="px-5 py-4">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={learning}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="domain" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} unit="%" tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(val: any) => [`${val}%`, "Completion"]} />
                    <Bar dataKey="completion_percent" fill="#4F46E5" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </Card>

        <Card title="Assessment Submission Status" pad={false}>
          {!Object.keys(status).length ? (
            <EmptyState title="No submissions" />
          ) : (
            <div className="px-5 py-4">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={Object.entries(status).map(([k, v]) => ({ name: k === "graded" ? "Graded" : "Submitted / In Review", value: v }))}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#10B981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </Card>
      </div>

      {scoreDist.length > 0 && (
        <Card title="Grading Workload by Domain" pad={false}>
          <div className="px-5 py-4">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={scoreDist}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="domain" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="pending" stroke="#F59E0B" name="Pending Grading" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Card>
      )}

      {/* Per-Student Progress Explorer */}
      <Card title="Per-Student Progress Explorer" subtitle="Search and inspect individual student curriculum completion, assessment attempts and points." pad={false}>
        {/* Filter Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-2 flex-1 max-w-sm">
            <div className="relative w-full">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search by student name or register number..."
                className="input pl-9 !py-1.5 text-xs w-full"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(1);
                }}
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Department:</span>
            <select
              className="input !py-1 text-xs"
              value={dept}
              onChange={(e) => {
                setDept(e.target.value);
                setPage(1);
              }}
            >
              <option value="all">All Departments</option>
              <option value="CSE">CSE</option>
              <option value="IT">IT</option>
              <option value="AI&DS">AI & DS</option>
              <option value="ECE">ECE</option>
              <option value="EEE">EEE</option>
              <option value="MECH">MECH</option>
              <option value="CIVIL">CIVIL</option>
            </select>
          </div>
        </div>

        {studentsLoading ? (
          <div className="p-8 text-center"><PageLoader label="Loading student progress..." /></div>
        ) : !studentList.length ? (
          <EmptyState title="No students found" description="Try clearing your search query or department filter." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Department</th>
                  <th>Enrolled Domains</th>
                  <th>Learning Progress</th>
                  <th>Assessments</th>
                  <th className="text-right">Total Points</th>
                </tr>
              </thead>
              <tbody>
                {studentList.map((s: any) => (
                  <tr key={s.id}>
                    <td>
                      <p className="font-medium text-slate-800">{s.name}</p>
                      <p className="text-xs text-slate-400">{s.register_number || s.email}</p>
                    </td>
                    <td>
                      <span className="badge-slate text-xs">{s.department || "General"}</span>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1 max-w-xs">
                        {s.domains?.map((d: string) => (
                          <span key={d} className="rounded bg-brand-50 px-2 py-0.5 text-[11px] text-brand-700 font-medium">
                            {d}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="min-w-[180px]">
                      <div className="flex items-center justify-between text-xs text-slate-600 mb-1">
                        <span>{s.completed_days}/{s.total_days} days</span>
                        <span className="font-semibold">{s.completion_percent}%</span>
                      </div>
                      <ProgressBar value={s.completion_percent} tone="brand" />
                    </td>
                    <td>
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700 font-medium">
                        {s.assessments_taken} taken
                      </span>
                    </td>
                    <td className="text-right font-bold text-brand-600">
                      {formatPoints(s.total_points)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination controls */}
        {studentsMeta && studentsMeta.pages > 1 && (
          <div className="flex items-center justify-between p-4 border-t border-slate-100 text-xs text-slate-500">
            <span>
              Showing page {studentsMeta.page} of {studentsMeta.pages} ({studentsMeta.total} total students)
            </span>
            <div className="flex gap-2">
              <button
                className="btn-secondary !py-1 !px-2.5 text-xs"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="h-3.5 w-3.5" /> Previous
              </button>
              <button
                className="btn-secondary !py-1 !px-2.5 text-xs"
                disabled={page >= studentsMeta.pages}
                onClick={() => setPage((p) => Math.min(studentsMeta.pages, p + 1))}
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
