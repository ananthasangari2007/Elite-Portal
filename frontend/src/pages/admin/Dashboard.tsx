import { Activity, AlertCircle, Award, ClipboardCheck, Clock, Database, HardDrive, Mail, Target, Users, UserCheck } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApi } from "../../lib/hooks";
import { formatDate, relativeTime } from "../../lib/format";
import { Badge, Card, EmptyState, ErrorState, MetricCard, PageHeader, PageLoader, StatusBadge } from "../../components/ui";

export default function AdminDashboard() {
  const { data, loading, error, reload } = useApi<any>("/admin/dashboard");

  if (loading) return <PageLoader label="Loading admin dashboard" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <EmptyState title="Could not load dashboard" />;

  const status = data.system_status || {};
  const activity = data.platform_activity || [];

  return (
    <div>
      <PageHeader title="Admin Dashboard" subtitle="Platform-wide overview, content activity and system health." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Total Students" value={data.total_students} icon={<Users className="h-5 w-5" />} tone="brand" />
        <MetricCard label="Total Staff" value={data.total_staff} icon={<UserCheck className="h-5 w-5" />} tone="violet" />
        <MetricCard label="Assessments Created" value={data.assessments_created} icon={<ClipboardCheck className="h-5 w-5" />} tone="green" />
        <MetricCard label="Total Submissions" value={data.total_submissions} icon={<Target className="h-5 w-5" />} tone="amber" />
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Pending Accounts" value={data.pending_accounts} icon={<AlertCircle className="h-5 w-5" />} tone="amber" />
        <MetricCard label="Pending Task Approvals" value={data.pending_task_approvals} icon={<Award className="h-5 w-5" />} tone="violet" />
        <MetricCard label="Open Appeals" value={data.open_appeals} icon={<Activity className="h-5 w-5" />} tone="brand" />
        <MetricCard label="Point Adjustments" value={data.pending_point_adjustments} icon={<Clock className="h-5 w-5" />} tone="slate" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Platform activity" subtitle="Last 14 days">
          {!activity.length ? (
            <EmptyState icon={<Activity className="h-6 w-6" />} title="No activity recorded" />
          ) : (
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={activity} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={(v) => formatDate(v).slice(0, 6)} tick={{ fontSize: 11, fill: "#94a3b8" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} allowDecimals={false} />
                  <Tooltip labelFormatter={(v) => formatDate(v as string)} contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="submissions" stroke="#4f46e5" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="evidence" stroke="#7c3aed" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="completions" stroke="#059669" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card title="System status" subtitle="Live service health">
          <div className="space-y-3">
            <StatusRow icon={<Database className="h-4 w-4" />} label="Database" value={status.database} />
            <StatusRow icon={<HardDrive className="h-4 w-4" />} label="Storage" value={status.storage} />
            <StatusRow icon={<Mail className="h-4 w-4" />} label="Email" value={status.email} />
            <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3.5 py-3">
              <div className="flex items-center gap-2.5 text-sm text-slate-600">
                <Clock className="h-4 w-4 text-slate-400" /> Timezone
              </div>
              <Badge tone="blue">{status.timezone || "—"}</Badge>
            </div>
          </div>
        </Card>
      </div>

      <Card className="mt-6" title="Recent activity" subtitle="Latest administrative actions" pad={false}>
        {!data.recent_activity?.length ? (
          <EmptyState icon={<Activity className="h-6 w-6" />} title="No recent activity" />
        ) : (
          <div className="divide-y divide-slate-100">
            {data.recent_activity.map((e: any) => (
              <div key={e.id} className="flex items-start gap-3 px-5 py-3.5">
                <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                  <Activity className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-700">
                    <span className="font-medium text-slate-800">{e.actor}</span> {e.description}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-400">{e.action} · {relativeTime(e.created_at)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function StatusRow({ icon, label, value }: { icon: React.ReactNode; label: string; value?: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3.5 py-3">
      <div className="flex items-center gap-2.5 text-sm text-slate-600">
        <span className="text-slate-400">{icon}</span> {label}
      </div>
      <StatusBadge status={value} />
    </div>
  );
}
