import { Link } from "react-router-dom";
import { Award, Coins, Gift, RotateCcw, Scale, ShieldCheck, Target, TrendingDown, TrendingUp } from "lucide-react";
import { useApi } from "../../lib/hooks";
import { formatPoints, formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, EmptyState, MetricCard, PageHeader, PageLoader } from "../../components/ui";

export default function StudentPoints() {
  const { data, loading } = useApi<any>("/student/points");
  if (loading) return <PageLoader />;
  const s = data?.summary || {};

  return (
    <div>
      <PageHeader
        title="Points & Rewards"
        subtitle="Your complete points breakdown and transaction history."
        actions={
          <Link to="/student/appeals" className="btn-secondary">
            <Scale className="h-4 w-4" /> Raise Point Appeal
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Total Points" value={formatPoints(s.total)} icon={<Award className="h-5 w-5" />} tone="brand" />
        <MetricCard label="From Tasks" value={formatPoints(s.tasks)} icon={<Target className="h-5 w-5" />} tone="green" />
        <MetricCard label="From Assessments" value={formatPoints(s.assessments)} icon={<ShieldCheck className="h-5 w-5" />} tone="violet" />
        <MetricCard label="Betting Points" value={formatPoints(s.betting)} icon={<Coins className="h-5 w-5" />} tone="amber" />
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <Card className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600"><TrendingUp className="h-5 w-5" /></div>
          <div><p className="text-xs text-slate-500">Bonus</p><p className="text-lg font-semibold text-slate-800">{formatPoints(s.bonus)}</p></div>
        </Card>
        <Card className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><Gift className="h-5 w-5" /></div>
          <div><p className="text-xs text-slate-500">Adjustments</p><p className="text-lg font-semibold text-slate-800">{formatPoints(s.adjustments)}</p></div>
        </Card>
        <Card className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-50 text-red-600"><TrendingDown className="h-5 w-5" /></div>
          <div><p className="text-xs text-slate-500">Penalties</p><p className="text-lg font-semibold text-slate-800">{formatPoints(s.penalty)}</p></div>
        </Card>
      </div>

      <Card className="mt-6" title="Transaction history" pad={false}>
        {!data?.history?.length ? (
          <EmptyState icon={<Award className="h-6 w-6" />} title="No transactions yet" description="Approved tasks and assessments will appear here." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>Date</th><th>Description</th><th>Type</th><th className="text-right">Points</th></tr>
              </thead>
              <tbody>
                {data.history.map((e: any) => (
                  <tr key={e.id} className={e.is_reversed ? "opacity-60" : ""}>
                    <td className="whitespace-nowrap text-slate-500">{formatDateTime(e.created_at)}</td>
                    <td className="text-slate-700">
                      {e.description || "—"}
                      {e.is_reversed && <span className="ml-2 text-xs text-red-500">(reversed)</span>}
                      {e.is_override && !e.is_reversed && <span className="ml-2 text-xs text-brand-500">(override)</span>}
                    </td>
                    <td><Badge tone={e.is_reversed ? "slate" : "blue"}>{humanize(e.type)}</Badge></td>
                    <td className={`text-right font-semibold ${e.is_reversed ? "text-slate-400 line-through" : e.points >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                      {e.points >= 0 ? "+" : ""}{e.points}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
