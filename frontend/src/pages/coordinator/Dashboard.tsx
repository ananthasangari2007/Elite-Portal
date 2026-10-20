import { Link } from "react-router-dom";
import { Award, BookOpen, CalendarClock, CheckCircle2, ClipboardCheck, TrendingUp, UploadCloud } from "lucide-react";
import { useApi } from "../../lib/hooks";
import { formatDateTime, formatPoints, humanize, relativeTime } from "../../lib/format";
import { Badge, Card, EmptyState, MetricCard, PageHeader, PageLoader, ProgressBar } from "../../components/ui";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function CoordinatorDashboard() {
  const { data, loading } = useApi<any>("/coordinator/dashboard");

  if (loading) return <PageLoader label="Loading dashboard" />;
  if (!data) return <EmptyState title="Could not load dashboard" />;

  return (
    <div>
      <PageHeader
        title="Coordinator Dashboard"
        subtitle="Overview of content, assessments and submissions."
        actions={
          <Link to="/coordinator/content" className="btn-primary">
            <UploadCloud className="h-4 w-4" /> Manage Content
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Enrolled Students" value={data.enrolled_students} icon={<Award className="h-5 w-5" />} tone="brand" />
        <MetricCard label="Published Days" value={data.published_days} icon={<BookOpen className="h-5 w-5" />} tone="green" />
        <MetricCard label="Assessments Submitted" value={data.assessments_submitted} icon={<ClipboardCheck className="h-5 w-5" />} tone="violet" />
        <MetricCard label="Pending Grading" value={data.pending_grading} icon={<CalendarClock className="h-5 w-5" />} tone="amber" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {data.domains?.length > 0 && (
            <Card title="Domains" subtitle="Content and student coverage" pad={false}>
              <div className="divide-y divide-slate-100">
                {data.domains.map((d: any) => (
                  <div key={d.id} className="flex items-center gap-4 px-5 py-4">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
                      <BookOpen className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-slate-800">{d.name}</p>
                        <span className="text-xs text-slate-500">{d.students} students · {d.published_days} published days</span>
                      </div>
                    </div>
                    <Link to="/coordinator/content" className="btn-secondary !px-3 !py-1.5">
                      Open
                    </Link>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Card title="Progress by Day" subtitle="Completions per published day" pad={false}>
            {!data.progress_by_day?.length ? (
              <EmptyState icon={<TrendingUp className="h-6 w-6" />} title="No progress data yet" />
            ) : (
              <div className="px-5 py-4">
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.progress_by_day}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="day_number" label={{ value: "Day", position: "insideBottom", offset: -5 }} />
                      <YAxis allowDecimals={false} />
                      <Tooltip labelFormatter={(v) => data.progress_by_day.find((x: any) => x.day_number === v)?.title || `Day ${v}`} />
                      <Bar dataKey="completed" fill="#4F46E5" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </Card>

          <Card title="Pending Grading" pad={false}>
            {!data.pending_grading_list?.length ? (
              <EmptyState icon={<ClipboardCheck className="h-6 w-6" />} title="No pending submissions" description="All caught up." />
            ) : (
              <div className="divide-y divide-slate-100">
                {data.pending_grading_list.map((s: any) => (
                  <Link key={s.id} to={`/coordinator/submissions/${s.id}`} className="block px-5 py-3.5 hover:bg-slate-50">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-slate-800">{s.student}</p>
                        <p className="text-xs text-slate-500">{s.assessment} · {s.submitted_at ? formatDateTime(s.submitted_at) : ""}</p>
                      </div>
                      <Badge tone="amber">Pending</Badge>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Recent Activity" pad={false}>
            {!data.recent_activity?.length ? (
              <EmptyState icon={<TrendingUp className="h-6 w-6" />} title="No activity yet" />
            ) : (
              <div className="divide-y divide-slate-100">
                {data.recent_activity.slice(0, 8).map((e: any) => (
                  <div key={e.id} className="flex items-start gap-3 px-5 py-3.5">
                    <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                      <CheckCircle2 className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-slate-700">{e.student} · {e.assessment}</p>
                      <p className="text-xs text-slate-400">{e.at ? relativeTime(e.at) : ""} · {humanize(e.status)} {e.score != null ? `· ${e.score}` : ""}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="Publication Activity" pad={false}>
            {!data.publication_activity?.length ? (
              <EmptyState icon={<BookOpen className="h-6 w-6" />} title="No publications yet" />
            ) : (
              <div className="divide-y divide-slate-100">
                {data.publication_activity.map((p: any, i: number) => (
                  <div key={i} className="px-5 py-3.5">
                    <p className="text-sm font-medium text-slate-800">Day {p.day_number} · {p.title}</p>
                    <p className="text-xs text-slate-400">{p.published_at ? formatDateTime(p.published_at) : ""}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}