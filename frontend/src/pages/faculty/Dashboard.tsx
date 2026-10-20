import { Link } from "react-router-dom";
import {
  Activity,
  BookOpen,
  CheckCircle2,
  ClipboardCheck,
  Layers,
  MessageSquare,
  Scale,
  SlidersHorizontal,
  Target,
  Users,
} from "lucide-react";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize, relativeTime } from "../../lib/format";
import {
  Badge,
  Card,
  EmptyState,
  MetricCard,
  PageHeader,
  PageLoader,
  StatusBadge,
} from "../../components/ui";

export default function FacultyDashboard() {
  const { data, loading, error, reload } = useApi<any>("/faculty/dashboard");

  if (loading) return <PageLoader label="Loading faculty dashboard" />;
  if (error || !data) return <EmptyState title="Could not load dashboard" description={error || undefined} />;

  return (
    <div>
      <PageHeader
        title="Faculty Dashboard"
        subtitle="Grading, evidence, appeals and point adjustments across your domains."
        actions={
          <Link to="/faculty/grading" className="btn-primary">
            <ClipboardCheck className="h-4 w-4" /> Grading queue
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Students" value={data.total_students} icon={<Users className="h-5 w-5" />} tone="brand" />
        <MetricCard label="Pending grading" value={data.pending_grading} icon={<ClipboardCheck className="h-5 w-5" />} tone="amber" />
        <MetricCard label="Open appeals" value={data.open_appeals} icon={<Scale className="h-5 w-5" />} tone="violet" />
        <MetricCard label="Point adjustments" value={data.pending_point_adjustments} icon={<SlidersHorizontal className="h-5 w-5" />} tone="green" />
        <MetricCard label="Task approvals" value={data.pending_task_approvals} icon={<Target className="h-5 w-5" />} tone="slate" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Your domains" subtitle="Enrollment, content and assessment coverage" pad={false}>
            {!data.domains?.length ? (
              <EmptyState icon={<Layers className="h-6 w-6" />} title="No domains assigned" description="You'll see your domains here once they are assigned." />
            ) : (
              <div className="grid gap-4 p-5 sm:grid-cols-2">
                {data.domains.map((d: any) => (
                  <div key={d.id} className="flex items-start gap-3 rounded-xl border border-slate-100 p-4">
                    <div
                      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white"
                      style={{ backgroundColor: d.color || "#4f46e5" }}
                    >
                      <BookOpen className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-800">{d.name}</p>
                      <p className="text-xs text-slate-400">{d.code}</p>
                      <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                        <span>{d.students} students</span>
                        <span>·</span>
                        <span>{d.published_days} days</span>
                        <span>·</span>
                        <span>{d.assessments} assessments</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card
            title="Pending grading"
            subtitle="Latest submissions awaiting a score"
            action={<Link to="/faculty/grading" className="text-sm text-brand-600 hover:underline">View all</Link>}
            pad={false}
          >
            {!data.pending_grading_list?.length ? (
              <EmptyState icon={<CheckCircle2 className="h-6 w-6" />} title="All caught up" description="No submissions are waiting to be graded." />
            ) : (
              <div className="divide-y divide-slate-100">
                {data.pending_grading_list.map((g: any) => (
                  <Link
                    key={g.id}
                    to={`/coordinator/submissions/${g.id}`}
                    className="flex items-center gap-4 px-5 py-4 hover:bg-slate-50"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                      <ClipboardCheck className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-800">{g.assessment}</p>
                      <p className="mt-0.5 truncate text-xs text-slate-500">
                        {g.student} · {g.domain}
                      </p>
                    </div>
                    <span className="hidden text-xs text-slate-400 sm:block">{g.submitted_at ? formatDateTime(g.submitted_at) : "—"}</span>
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card
            title="Student requests"
            subtitle="Open support conversations"
            action={<Link to="/requests" className="text-sm text-brand-600 hover:underline">Inbox</Link>}
            pad={false}
          >
            {!data.student_requests?.length ? (
              <EmptyState icon={<MessageSquare className="h-6 w-6" />} title="No open requests" />
            ) : (
              <div className="divide-y divide-slate-100">
                {data.student_requests.map((r: any) => (
                  <Link key={r.id} to="/requests" className="block px-5 py-3.5 hover:bg-slate-50">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-sm font-medium text-slate-800">{r.subject}</p>
                      <StatusBadge status={r.status} />
                    </div>
                    <p className="mt-0.5 truncate text-xs text-slate-500">
                      {r.student} · {humanize(r.category)}
                    </p>
                  </Link>
                ))}
              </div>
            )}
          </Card>

          <Card title="Recent activity" subtitle="Latest point transactions" pad={false}>
            {!data.recent_activity?.length ? (
              <EmptyState icon={<Activity className="h-6 w-6" />} title="No activity yet" />
            ) : (
              <div className="divide-y divide-slate-100">
                {data.recent_activity.map((e: any) => (
                  <div key={e.id} className="flex items-start gap-3 px-5 py-3.5">
                    <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                      <CheckCircle2 className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-slate-700">{e.description}</p>
                      <p className="text-xs text-slate-400">
                        {e.student} · {relativeTime(e.created_at)}
                      </p>
                    </div>
                    <Badge tone={e.points >= 0 ? "green" : "red"}>{e.points >= 0 ? "+" : ""}{e.points}</Badge>
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
