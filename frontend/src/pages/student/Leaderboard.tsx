import { useState } from "react";
import { Crown, Medal, Trophy } from "lucide-react";
import clsx from "clsx";
import { useApi } from "../../lib/hooks";
import { formatPoints } from "../../lib/format";
import { Avatar, Card, EmptyState, PageHeader, PageLoader, Tabs } from "../../components/ui";

const SCOPES = [
  { key: "overall", label: "Overall" },
  { key: "dsa", label: "DSA" },
  { key: "fullstack", label: "Full Stack" },
  { key: "aiml", label: "AI/ML" },
  { key: "embedded", label: "Embedded/IoT" },
  { key: "monthly", label: "Monthly" },
];

export default function Leaderboard() {
  const [scope, setScope] = useState("overall");
  const month = new Date().toISOString().slice(0, 7);
  const { data, loading } = useApi<any>("/leaderboards", scope === "monthly" ? { scope, month } : { scope });
  const entries = data?.entries || [];
  const podium = entries.slice(0, 3);

  return (
    <div>
      <PageHeader title="Leaderboard" subtitle="Eligible points only — approved tasks, assessments, betting and adjustments." />

      <Tabs tabs={SCOPES} active={scope} onChange={setScope} />

      {loading ? (
        <PageLoader />
      ) : !entries.length ? (
        <Card className="mt-6"><EmptyState icon={<Trophy className="h-6 w-6" />} title="No rankings yet" description="Points will appear as they are approved." /></Card>
      ) : (
        <div className="mt-6 space-y-6">
          {podium.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-3">
              {podium.map((p: any, i: number) => (
                <Card key={p.student_id} className={clsx("text-center", i === 0 && "sm:order-2 sm:-mt-2 ring-1 ring-amber-200")}>
                  <div className="flex flex-col items-center">
                    <div className={clsx("mb-2 flex h-9 w-9 items-center justify-center rounded-full", i === 0 ? "bg-amber-100 text-amber-600" : i === 1 ? "bg-slate-200 text-slate-600" : "bg-orange-100 text-orange-600")}>
                      {i === 0 ? <Crown className="h-5 w-5" /> : <Medal className="h-5 w-5" />}
                    </div>
                    <Avatar name={p.name} size={56} />
                    <p className="mt-2 font-semibold text-slate-800">{p.name}</p>
                    <p className="text-xs text-slate-400">{p.register_number}</p>
                    <p className="mt-2 text-2xl font-bold text-brand-700">{formatPoints(p.points)}</p>
                    <p className="text-xs text-slate-400">points</p>
                  </div>
                </Card>
              ))}
            </div>
          )}

          <Card pad={false}>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Rank</th><th>Student</th><th>Department</th><th className="text-right">Points</th></tr>
                </thead>
                <tbody>
                  {entries.map((e: any) => (
                    <tr key={e.student_id} className={clsx(data?.me?.student_id === e.student_id && "bg-brand-50/50")}>
                      <td className="font-semibold text-slate-500">#{e.rank}</td>
                      <td>
                        <div className="flex items-center gap-3">
                          <Avatar name={e.name} size={32} />
                          <div>
                            <p className="font-medium text-slate-800">{e.name}{data?.me?.student_id === e.student_id && <span className="ml-2 text-xs text-brand-600">You</span>}</p>
                            <p className="text-xs text-slate-400">{e.register_number}</p>
                          </div>
                        </div>
                      </td>
                      <td className="text-slate-500">{e.department || "—"}</td>
                      <td className="text-right font-semibold text-slate-800">{formatPoints(e.points)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
