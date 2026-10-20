import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3, BookOpen, ClipboardCheck, Gauge, Users } from "lucide-react";
import { useApi } from "../../lib/hooks";
import { Card, EmptyState, MetricCard, PageHeader, PageLoader } from "../../components/ui";

const PIE_COLORS = ["#f59e0b", "#10b981", "#6366f1", "#ef4444", "#0ea5e9"];

export default function FacultyAnalytics() {
  const { data, loading } = useApi<any>("/coordinator/analytics");

  if (loading) return <PageLoader label="Loading analytics" />;
  if (!data) return <EmptyState title="Could not load analytics" />;

  const totals = data.totals || {};
  const learning: any[] = data.learning || [];
  const statusCounts: Record<string, number> = data.status_counts || {};
  const workload: any[] = data.grading_workload || [];
  const scoreDistribution: any[] = data.score_distribution || [];

  const statusData = Object.entries(statusCounts).map(([name, value]) => ({ name, value: Number(value) }));
  const scoreData = scoreDistribution.map((item: any) => ({
    name: item.label ?? item.range ?? item.bucket ?? item.name ?? "—",
    value: Number(item.count ?? item.value ?? item.students ?? 0),
  }));

  return (
    <div>
      <PageHeader title="Analytics" subtitle="Learning progress, grading status and score insights across your domains." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Students" value={totals.students ?? 0} icon={<Users className="h-5 w-5" />} tone="brand" />
        <MetricCard label="Assessments" value={totals.assessments ?? 0} icon={<ClipboardCheck className="h-5 w-5" />} tone="violet" />
        <MetricCard label="Submissions" value={totals.submissions ?? 0} icon={<BarChart3 className="h-5 w-5" />} tone="green" />
        <MetricCard label="Average score" value={`${totals.average_score_percent ?? 0}%`} icon={<Gauge className="h-5 w-5" />} tone="amber" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Learning completion" subtitle="Completion percentage per domain">
          {!learning.length ? (
            <EmptyState icon={<BookOpen className="h-6 w-6" />} title="No learning data" />
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={learning} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="domain" tick={{ fontSize: 12, fill: "#64748b" }} interval={0} angle={-15} textAnchor="end" height={64} />
                  <YAxis tick={{ fontSize: 12, fill: "#64748b" }} domain={[0, 100]} unit="%" />
                  <Tooltip
                    formatter={(value: any, _name: any, item: any) => [`${value}%`, "Completion"]}
                    labelFormatter={(label: any, payload: any) => {
                      const p = payload?.[0]?.payload;
                      return p ? `${label} · ${p.completions}/${p.published_days} days` : label;
                    }}
                  />
                  <Bar dataKey="completion_percent" fill="#4f46e5" radius={[6, 6, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card title="Submission status" subtitle="Distribution of submitted vs graded attempts">
          {!statusData.length ? (
            <EmptyState icon={<ClipboardCheck className="h-6 w-6" />} title="No submissions yet" />
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={3}>
                    {statusData.map((_entry, index) => (
                      <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend verticalAlign="bottom" height={36} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card title="Score distribution" subtitle="Spread of graded scores">
          {!scoreData.length ? (
            <EmptyState icon={<BarChart3 className="h-6 w-6" />} title="Score distribution unavailable" description="No score distribution data was returned for your domains." />
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={scoreData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#64748b" }} />
                  <YAxis tick={{ fontSize: 12, fill: "#64748b" }} allowDecimals={false} />
                  <Tooltip formatter={(value: any) => [value, "Attempts"]} />
                  <Bar dataKey="value" fill="#10b981" radius={[6, 6, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card title="Grading workload" subtitle="Pending submissions by domain">
          {!workload.length ? (
            <EmptyState icon={<ClipboardCheck className="h-6 w-6" />} title="No pending grading" />
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={workload} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="domain" tick={{ fontSize: 12, fill: "#64748b" }} interval={0} angle={-15} textAnchor="end" height={64} />
                  <YAxis tick={{ fontSize: 12, fill: "#64748b" }} allowDecimals={false} />
                  <Tooltip formatter={(value: any) => [value, "Pending"]} />
                  <Bar dataKey="pending" fill="#f59e0b" radius={[6, 6, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
