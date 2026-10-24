import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Award,
  BookOpen,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  Flame,
  Target,
  TrendingUp,
  Video,
} from "lucide-react";
import { useAuth } from "../../lib/auth";
import { useApi } from "../../lib/hooks";
import { formatDateTime, formatPoints, humanize, relativeTime, statusTone } from "../../lib/format";
import { Badge, Card, EmptyState, MetricCard, PageHeader, PageLoader, ProgressBar, StatusBadge } from "../../components/ui";

export default function StudentDashboard() {
  const { user } = useAuth();
  const { data, loading } = useApi<any>("/student/dashboard");

  if (loading) return <PageLoader label="Loading your dashboard" />;
  if (!data) return <EmptyState title="Could not load dashboard" />;

  return (
    <div>
      <PageHeader
        title={`Welcome back, ${user!.name.split(" ")[0]}`}
        subtitle="Here's your learning snapshot for today."
        actions={
          <Link to="/student/tasks" className="btn-primary">
            <Target className="h-4 w-4" /> Daily Elite Task
          </Link>
        }
      />

      {/* Faculty Meeting Instructions Notice */}
      {data.faculty_instructions && data.faculty_instructions.length > 0 && (
        <div className="mb-6 space-y-3">
          {data.faculty_instructions.map((ins: any) => (
            <div
              key={ins.id}
              className="flex items-start justify-between gap-3 rounded-2xl border border-amber-300 bg-amber-50/90 p-4 text-amber-950 shadow-sm"
            >
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-sm">Action Required: Meet Assigned Faculty</p>
                  <p className="text-xs text-amber-900 mt-0.5">
                    You are instructed to meet faculty <strong>{ins.faculty_name}</strong> {ins.faculty_email && `(${ins.faculty_email})`} regarding your appeal for <strong>{ins.assessment}</strong>.
                  </p>
                </div>
              </div>
              <Link
                to="/student/appeals"
                className="shrink-0 rounded-xl bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-500 transition shadow-sm"
              >
                View Appeal
              </Link>
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Total Points" value={formatPoints(data.total_points)} icon={<Award className="h-5 w-5" />} tone="brand" />
        <MetricCard label="Current Streak" value={`${data.current_streak} days`} icon={<Flame className="h-5 w-5" />} tone="amber" />
        <MetricCard label="Assessments Done" value={data.assessments_completed} icon={<ClipboardCheck className="h-5 w-5" />} tone="violet" />
        <MetricCard label="Videos Watched" value={data.videos_completed} icon={<Video className="h-5 w-5" />} tone="green" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Domain progress" subtitle="Your completion across enrolled domains" pad={false}>
            {!data.progress?.length ? (
              <EmptyState
                title="No domains yet"
                description="Select your domains to start learning."
                action={<Link to="/student/domains" className="btn-primary">Choose domains</Link>}
              />
            ) : (
              <div className="divide-y divide-slate-100">
                {data.progress.map((p: any) => (
                  <div key={p.domain_id} className="flex items-center gap-4 px-5 py-4">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
                      <BookOpen className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-slate-800">{p.name}</p>
                        <span className="text-xs text-slate-500">{p.completed_days}/{p.published_days} days</span>
                      </div>
                      <ProgressBar value={p.percent} className="mt-2" tone="brand" />
                    </div>
                    <Link to={`/student/learning?domain=${p.domain_id}`} className="btn-secondary !px-3 !py-1.5">
                      Open
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="Today's Elite Tasks" subtitle={data.daily_task_submitted ? "You've submitted today's task." : "One submission per day."} pad={false}>
            {!data.today_tasks?.length ? (
              <EmptyState icon={<Target className="h-6 w-6" />} title="No tasks today" description="Check back soon for new tasks." />
            ) : (
              <div className="divide-y divide-slate-100">
                {data.today_tasks.map((t: any) => (
                  <div key={t.id} className="flex items-center gap-4 px-5 py-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-800">{t.title}</p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {t.due_date ? `Due ${formatDateTime(t.due_date)}` : "No deadline"} · {t.potential_points} pts
                      </p>
                    </div>
                    {t.submitted ? <Badge tone="green">Submitted</Badge> : <Badge tone="amber">Pending</Badge>}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Upcoming assessments" pad={false}>
            {!data.upcoming_assessments?.length ? (
              <EmptyState icon={<CalendarClock className="h-6 w-6" />} title="Nothing scheduled" />
            ) : (
              <div className="divide-y divide-slate-100">
                {data.upcoming_assessments.map((a: any) => (
                  <Link key={a.id} to="/student/assessments" className="block px-5 py-3.5 hover:bg-slate-50">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium text-slate-800">{a.title}</p>
                      <Badge tone="blue">{humanize(a.type)}</Badge>
                    </div>
                    <p className="mt-0.5 text-xs text-slate-500">{a.scheduled_start ? formatDateTime(a.scheduled_start) : "Open window"}</p>
                  </Link>
                ))}
              </div>
            )}
          </Card>

          <Card title="Recent activity" pad={false}>
            {!data.recent_activity?.length ? (
              <EmptyState icon={<TrendingUp className="h-6 w-6" />} title="No activity yet" />
            ) : (
              <div className="divide-y divide-slate-100">
                {data.recent_activity.slice(0, 6).map((e: any) => (
                  <div key={e.id} className="flex items-start gap-3 px-5 py-3.5">
                    <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                      <CheckCircle2 className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-slate-700">{e.description}</p>
                      <p className="text-xs text-slate-400">{relativeTime(e.created_at)}</p>
                    </div>
                    {e.points ? <span className="text-sm font-semibold text-emerald-600">+{e.points}</span> : null}
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
