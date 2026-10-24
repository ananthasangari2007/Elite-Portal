import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, ChevronRight, Circle, Lock, PlayCircle } from "lucide-react";
import clsx from "clsx";
import { useApi } from "../../lib/hooks";
import { Card, EmptyState, PageHeader, PageLoader, ProgressBar, Tabs } from "../../components/ui";

export default function LearningPathPage() {
  const [params, setParams] = useSearchParams();
  const { data: domains, loading: domainsLoading } = useApi<any>("/student/domains");
  const enrolled: any[] = domains?.enrolled || [];

  const initialDomainId = params.get("domain") ? Number(params.get("domain")) : null;
  const [selectedDomainId, setSelectedDomainId] = useState<number | null>(initialDomainId);

  // Derive active domain without race conditions
  const activeDomainId = useMemo(() => {
    if (selectedDomainId && enrolled.some((d: any) => d.id === selectedDomainId)) {
      return selectedDomainId;
    }
    if (enrolled.length > 0) {
      return enrolled[0].id;
    }
    return null;
  }, [selectedDomainId, enrolled]);

  // Keep URL search params in sync
  useEffect(() => {
    if (activeDomainId && params.get("domain") !== String(activeDomainId)) {
      setParams({ domain: String(activeDomainId) }, { replace: true });
    }
  }, [activeDomainId, params, setParams]);

  // Fetch learning path with SWR cache
  const { data: path, loading: pathLoading } = useApi<any>(
    activeDomainId ? `/student/domains/${activeDomainId}/learning-path` : null
  );

  // Prevent flash of empty state while initial domain list is loading
  if (domainsLoading && !domains) {
    return <PageLoader label="Loading your learning path..." />;
  }

  // Truly not enrolled in any domain
  if (!enrolled.length) {
    return (
      <div>
        <PageHeader title="Learning Path" />
        <Card>
          <EmptyState
            title="No domains enrolled"
            description="Select at least one domain to begin your customized learning journey."
            action={
              <Link to="/student/domains" className="btn-primary">
                Choose domains
              </Link>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Learning Path"
        subtitle="Work through each day sequentially. Complete a day to unlock the next."
      />

      <Tabs
        tabs={enrolled.map((d: any) => ({ key: String(d.id), label: d.name }))}
        active={String(activeDomainId)}
        onChange={(k) => setSelectedDomainId(Number(k))}
      />

      {pathLoading && !path ? (
        <PageLoader label="Loading content..." />
      ) : !path ? (
        <Card className="mt-6">
          <EmptyState title="Could not load learning path" description="Please try selecting the domain again." />
        </Card>
      ) : (
        <div className="mt-6 space-y-6">
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-800">{path.domain?.name}</h3>
                <p className="mt-0.5 text-sm text-slate-500">
                  {path.progress?.completed_days || 0} of {path.progress?.published_days || 0} days completed
                </p>
              </div>
              <span className="text-2xl font-bold text-brand-700">{path.progress?.percent || 0}%</span>
            </div>
            <ProgressBar value={path.progress?.percent || 0} className="mt-3" />
          </Card>

          {!path.days?.length ? (
            <Card>
              <EmptyState
                title="No learning days yet"
                description="Your coordinator hasn't published content for this domain yet. Check back soon!"
              />
            </Card>
          ) : (
            <div className="grid gap-3">
              {path.days.map((day: any) => {
                const locked = day.locked && !day.completed;
                return (
                  <div
                    key={day.id}
                    className={clsx(
                      "card flex items-center gap-4 p-4 transition duration-150",
                      day.current && "ring-2 ring-brand-500 shadow-sm",
                      locked && "opacity-60 bg-slate-50/70"
                    )}
                  >
                    <div
                      className={clsx(
                        "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-sm font-semibold transition",
                        day.completed
                          ? "bg-emerald-100 text-emerald-600"
                          : day.current
                          ? "bg-brand-600 text-white shadow-md shadow-brand-500/20"
                          : "bg-slate-100 text-slate-500"
                      )}
                    >
                      {day.completed ? (
                        <CheckCircle2 className="h-5 w-5" />
                      ) : locked ? (
                        <Lock className="h-5 w-5" />
                      ) : (
                        <Circle className="h-5 w-5" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold text-slate-500">Day {day.day_number}</span>
                        {day.current && <span className="badge-blue">Current Topic</span>}
                        {day.completed && <span className="badge-green">Completed</span>}
                      </div>
                      <p className="mt-0.5 font-medium text-slate-800">{day.title}</p>
                      <p className="text-xs text-slate-500">
                        {day.material_count} material(s) · {day.assessment_count} assessment(s)
                      </p>
                    </div>
                    {locked ? (
                      <span className="text-xs font-medium text-slate-400">Complete previous day</span>
                    ) : (
                      <Link to={`/student/learning/${day.id}`} className="btn-secondary">
                        <PlayCircle className="h-4 w-4" /> Open <ChevronRight className="h-4 w-4" />
                      </Link>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
