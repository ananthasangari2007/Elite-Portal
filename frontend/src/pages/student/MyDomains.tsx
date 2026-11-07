import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Lock, Save } from "lucide-react";
import clsx from "clsx";
import { useApi } from "../../lib/hooks";
import { api } from "../../lib/api";
import { Card, PageHeader, PageLoader, ProgressBar } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function MyDomains() {
  const navigate = useNavigate();
  const { data, loading, reload } = useApi<any>("/student/domains");
  const [selected, setSelected] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const { push } = useToast();

  useEffect(() => {
    if (!data) return;
    const enrolledIds = (data.enrolled || []).map((d: any) => d.id);
    const compulsoryIds = [
      ...(data.enrolled || []).filter((d: any) => d.is_compulsory),
      ...(data.available || []).filter((d: any) => d.is_compulsory),
    ].map((d: any) => d.id);
    setSelected(Array.from(new Set<number>([...enrolledIds, ...compulsoryIds])));
  }, [data]);

  if (loading || !data) return <PageLoader />;

  const compulsory = (data.available || []).filter((d: any) => d.is_compulsory);
  const enrolledCompulsory = (data.enrolled || []).filter((d: any) => d.is_compulsory);
  const allCompulsory = [...enrolledCompulsory, ...compulsory];
  const compulsoryIds = new Set(allCompulsory.map((d) => d.id));
  const optionalSelected = selected.filter((id) => !compulsoryIds.has(id));
  const maxOptional = data.max_optional ?? 2;
  const atLimit = optionalSelected.length >= maxOptional;

  function toggle(id: number) {
    if (compulsoryIds.has(id)) return;
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (optionalSelected.length >= maxOptional) {
        push(`You may select at most ${maxOptional} optional domains.`, "info");
        return prev;
      }
      return [...prev, id];
    });
  }

  async function save() {
    setBusy(true);
    try {
      await api.post("/student/domains", { domain_ids: selected });
      push("Domain selection saved. Redirecting to your learning path...", "success");
      navigate("/student/learning");
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  const domains = [...(data.enrolled || []), ...(data.available || []).filter((d: any) => !data.enrolled.some((e: any) => e.id === d.id))];

  return (
    <div>
      <PageHeader
        title="My Domains"
        subtitle={`DSA is compulsory. You may choose up to ${maxOptional} optional primary domains.`}
        actions={<button className="btn-primary" onClick={save} disabled={busy}><Save className="h-4 w-4" /> Save selection</button>}
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {domains.map((d: any) => {
          const isSelected = selected.includes(d.id);
          const isCompulsory = compulsoryIds.has(d.id);
          const enrolledProgress = (data.enrolled || []).find((e: any) => e.id === d.id)?.progress;
          const disabled = isCompulsory || (!isSelected && atLimit);
          return (
            <button
              key={d.id}
              onClick={() => toggle(d.id)}
              disabled={disabled}
              className={clsx(
                "card card-pad text-left transition",
                isSelected ? "ring-2 ring-brand-500" : "hover:border-brand-200",
                disabled && !isSelected && "opacity-60"
              )}
            >
              <div className="flex items-start justify-between">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl text-white" style={{ background: d.color || "#4f46e5" }}>
                  {d.code.slice(0, 2)}
                </div>
                <div className="flex items-center gap-2">
                  {isCompulsory && <span className="badge-slate"><Lock className="h-3 w-3" /> Compulsory</span>}
                  {isSelected && <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-600 text-white"><Check className="h-3.5 w-3.5" /></span>}
                </div>
              </div>
              <h3 className="mt-3 font-semibold text-slate-800">{d.name}</h3>
              <p className="mt-1 line-clamp-2 text-xs text-slate-500">{d.description}</p>
              {enrolledProgress && (
                <div className="mt-3">
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>{enrolledProgress.completed_days}/{enrolledProgress.published_days} days</span>
                    <span>{enrolledProgress.percent}%</span>
                  </div>
                  <ProgressBar value={enrolledProgress.percent} className="mt-1" />
                </div>
              )}
            </button>
          );
        })}
      </div>

      <Card className="mt-6" title="Selection summary">
        <p className="text-sm text-slate-600">
          Selected: <span className="font-medium text-slate-800">{selected.length}</span> domain(s) ·
          Optional: <span className="font-medium text-slate-800">{optionalSelected.length}/{maxOptional}</span>
        </p>
      </Card>
    </div>
  );
}
