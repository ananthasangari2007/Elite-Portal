import { useEffect, useMemo, useState } from "react";
import { Award, Crown, Filter, Medal, Sparkles, Target, Trophy, Users } from "lucide-react";
import clsx from "clsx";
import { useAuth } from "../../lib/auth";
import { useApi } from "../../lib/hooks";
import { formatPoints } from "../../lib/format";
import { Avatar, Badge, Card, EmptyState, PageHeader, PageLoader, Tabs } from "../../components/ui";

export default function Leaderboard() {
  const { user } = useAuth();
  const [filterType, setFilterType] = useState<"overall" | "department" | "domain">("overall");
  const [selectedDomainId, setSelectedDomainId] = useState<number | null>(null);
  const [selectedDept, setSelectedDept] = useState<string>(user?.department || "CSE");

  const { data: domainData } = useApi<{ enrolled: Array<{ id: number; code: string; name: string }> }>(
    "/student/domains"
  );
  const enrolled = domainData?.enrolled || [];

  // Default selectedDomainId to first enrolled domain
  useEffect(() => {
    if (enrolled.length > 0 && selectedDomainId === null) {
      setSelectedDomainId(enrolled[0].id);
    }
  }, [enrolled, selectedDomainId]);

  const queryParams = useMemo(() => {
    const params: any = { limit: 20 };
    if (filterType === "overall") {
      params.scope = "overall";
    } else if (filterType === "department") {
      params.scope = "department";
      params.department = selectedDept;
    } else if (filterType === "domain" && selectedDomainId) {
      params.scope = "domain";
      params.domain_id = selectedDomainId;
    }
    return params;
  }, [filterType, selectedDept, selectedDomainId]);

  const { data, loading } = useApi<any>("/leaderboards", queryParams);
  const entries = data?.entries || [];
  const podium = entries.slice(0, 3);
  const myRanks = data?.my_ranks;

  const filterTabs = [
    { key: "overall", label: "Top 20 Overall" },
    { key: "department", label: "Top 20 by Department" },
    { key: "domain", label: "Top 20 in My Domain" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Student Leaderboard"
        subtitle="Live academic rankings across general standing and your registered domains."
      />

      {/* ── My Current Standing Cards (General + Enrolled Domains Only) ──────── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {/* Overall Rank Card */}
        <div className="rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50/80 via-white to-brand-50/40 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-700">
              My Overall Rank
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand-600 text-white shadow">
              <Trophy className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">
              {myRanks?.overall?.rank ? `#${myRanks.overall.rank}` : "—"}
            </span>
            <span className="text-xs font-semibold text-slate-500">
              ({formatPoints(myRanks?.overall?.points ?? 0)} pts)
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">Overall Batch 2025–2029 Standing</p>
        </div>

        {/* Registered Domains Ranks (Strictly Student's Enrolled Domains) */}
        {myRanks?.domains &&
          Object.values(myRanks.domains).map((dr: any) => (
            <div
              key={dr.domain_id}
              className="rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50/80 via-white to-violet-50/40 p-5 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-violet-700 truncate max-w-[180px]">
                  {dr.domain_name}
                </span>
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-600 text-white shadow">
                  <Award className="h-4 w-4" />
                </div>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-slate-900">
                  {dr.rank ? `#${dr.rank}` : "—"}
                </span>
                <span className="text-xs font-semibold text-slate-500">
                  ({formatPoints(dr.points)} pts)
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">Your Registered Domain Rank</p>
            </div>
          ))}
      </div>

      {/* ── Filter Controls Bar ────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <Tabs
          tabs={filterTabs}
          active={filterType}
          onChange={(k) => setFilterType(k as any)}
        />

        <div className="flex items-center gap-3">
          {filterType === "department" && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-500">Dept:</span>
              <select
                className="input !py-1.5 !text-xs !w-auto cursor-pointer"
                value={selectedDept}
                onChange={(e) => setSelectedDept(e.target.value)}
              >
                <option value="CSE">CSE</option>
                <option value="IT">IT</option>
                <option value="AIDS">AIDS</option>
                <option value="ECE">ECE</option>
                <option value="EEE">EEE</option>
                <option value="MECH">MECH</option>
              </select>
            </div>
          )}

          {filterType === "domain" && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-500">Domain:</span>
              <select
                className="input !py-1.5 !text-xs !w-auto cursor-pointer"
                value={selectedDomainId || ""}
                onChange={(e) => setSelectedDomainId(Number(e.target.value))}
              >
                {enrolled.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* ── Leaderboard Content & Podium ───────────────────────────────────── */}
      {loading ? (
        <PageLoader />
      ) : !entries.length ? (
        <Card className="mt-6">
          <EmptyState
            icon={<Trophy className="h-6 w-6 text-slate-400" />}
            title="No rankings found"
            description="No points recorded for this filter category yet."
          />
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Top 3 Podium Cards */}
          {podium.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-3">
              {podium.map((p: any, i: number) => (
                <Card
                  key={p.student_id}
                  className={clsx(
                    "text-center transition duration-150 hover:shadow-md",
                    i === 0 && "sm:order-2 sm:-mt-2 ring-2 ring-amber-400 bg-amber-50/20 shadow-md"
                  )}
                >
                  <div className="flex flex-col items-center">
                    <div
                      className={clsx(
                        "mb-3 flex h-10 w-10 items-center justify-center rounded-full shadow-sm",
                        i === 0
                          ? "bg-amber-100 text-amber-600 ring-2 ring-amber-300"
                          : i === 1
                          ? "bg-slate-200 text-slate-600 ring-2 ring-slate-300"
                          : "bg-orange-100 text-orange-600 ring-2 ring-orange-300"
                      )}
                    >
                      {i === 0 ? <Crown className="h-5 w-5" /> : <Medal className="h-5 w-5" />}
                    </div>
                    <Avatar name={p.name} src={p.avatar_url} size={64} />
                    <p className="mt-3 font-bold text-slate-900">{p.name}</p>
                    <p className="text-xs text-slate-400">{p.register_number} · {p.department || "FXEC"}</p>
                    <p className="mt-3 text-2xl font-extrabold text-brand-700">
                      {formatPoints(p.points)}
                    </p>
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      Rank #{p.rank}
                    </span>
                  </div>
                </Card>
              ))}
            </div>
          )}

          {/* Top 20 Table View */}
          <Card pad={false}>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Student</th>
                    <th>Department</th>
                    <th className="text-right">Points</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e: any) => {
                    const isMe = data?.me?.student_id === e.student_id;
                    return (
                      <tr
                        key={e.student_id}
                        className={clsx(
                          isMe ? "bg-brand-50/70 font-semibold" : "hover:bg-slate-50/60"
                        )}
                      >
                        <td>
                          <span
                            className={clsx(
                              "inline-flex h-6 w-6 items-center justify-center rounded-lg text-xs font-bold",
                              e.rank === 1
                                ? "bg-amber-100 text-amber-800"
                                : e.rank === 2
                                ? "bg-slate-200 text-slate-800"
                                : e.rank === 3
                                ? "bg-orange-100 text-orange-800"
                                : "bg-slate-100 text-slate-600"
                            )}
                          >
                            #{e.rank}
                          </span>
                        </td>
                        <td>
                          <div className="flex items-center gap-3">
                            <Avatar name={e.name} src={e.avatar_url} size={34} />
                            <div>
                              <p className="font-medium text-slate-900 flex items-center gap-1.5">
                                <span>{e.name}</span>
                                {isMe && (
                                  <Badge tone="blue">You</Badge>
                                )}
                              </p>
                              <p className="text-xs text-slate-400">{e.register_number}</p>
                            </div>
                          </div>
                        </td>
                        <td className="text-slate-500 font-medium">{e.department || "—"}</td>
                        <td className="text-right font-bold text-slate-900">
                          {formatPoints(e.points)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
