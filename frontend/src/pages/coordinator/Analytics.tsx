import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, Legend } from "recharts";
import { useApi } from "../../lib/hooks";
import { Card, EmptyState, MetricCard, PageHeader, PageLoader } from "../../components/ui";
import { api } from "../../lib/api";
import { BarChart as BarIcon, Download, TrendingUp, Users } from "lucide-react";

export default function CoordinatorAnalytics() {
  const { data, loading } = useApi<any>("/coordinator/analytics");

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

  return (
    <div>
      <PageHeader
        title="Analytics"
        subtitle="Learning and assessment insights"
        actions={
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={downloadStudents}><Download className="h-4 w-4" /> Students CSV</button>
            <button className="btn-secondary" onClick={downloadSubmissions}><Download className="h-4 w-4" /> Submissions CSV</button>
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Students" value={totals.students} icon={<Users className="h-5 w-5" />} tone="brand" />
        <MetricCard label="Assessments" value={totals.assessments} icon={<BarIcon className="h-5 w-5" />} tone="violet" />
        <MetricCard label="Submissions" value={totals.submissions} icon={<TrendingUp className="h-5 w-5" />} tone="green" />
        <MetricCard label="Avg Score (%)" value={totals.average_score_percent} icon={<TrendingUp className="h-5 w-5" />} tone="amber" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Learning Completion by Domain" pad={false}>
          {!learning.length ? (
            <EmptyState title="No learning data" />
          ) : (
            <div className="px-5 py-4">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={learning}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="domain" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="completion_percent" fill="#4F46E5" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </Card>

        <Card title="Submission Status" pad={false}>
          {!Object.keys(status).length ? (
            <EmptyState title="No submissions" />
          ) : (
            <div className="px-5 py-4">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={Object.entries(status).map(([k, v]) => ({ name: k, value: v }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis allowDecimals={false} />
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
        <Card className="mt-6" title="Score Distribution / Workload" pad={false}>
          <div className="px-5 py-4">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={scoreDist}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="domain" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="pending" stroke="#F59E0B" />
                  <Line type="monotone" dataKey="value" stroke="#4F46E5" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}