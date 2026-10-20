import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { humanize } from "../../lib/format";
import { Card, ErrorState, PageHeader, PageLoader, Spinner } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

const GROUPS: { title: string; keys: string[] }[] = [
  { title: "General", keys: ["institution_timezone", "notifications_enabled"] },
  { title: "Domains & Enrollment", keys: ["max_optional_domains"] },
  { title: "Tasks & Assessments", keys: ["daily_task_limit", "task_points_require_approval", "assessment_attempt_default"] },
  { title: "Uploads & Retention", keys: ["upload_max_mb", "evidence_retention_days"] },
];

export default function AdminSettings() {
  const { data, loading, error, reload } = useApi<any[]>("/admin/settings");
  const [values, setValues] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState(false);
  const { push } = useToast();

  useEffect(() => {
    if (data) {
      const next: Record<string, any> = {};
      data.forEach((s) => { next[s.key] = s.value; });
      setValues(next);
    }
  }, [data]);

  async function save() {
    setBusy(true);
    try {
      await api.put("/admin/settings", { settings: values });
      push("Settings saved.", "success");
      reload();
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <PageLoader label="Loading settings" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;

  const settings = data || [];
  const lookup = new Map(settings.map((s) => [s.key, s]));
  const grouped = GROUPS.map((g) => ({ ...g, items: g.keys.map((k) => lookup.get(k)).filter(Boolean) }));
  const groupedKeys = new Set(GROUPS.flatMap((g) => g.keys));
  const others = settings.filter((s) => !groupedKeys.has(s.key));

  function renderField(s: any) {
    if (s.value_type === "boolean") {
      return (
        <button
          type="button"
          role="switch"
          aria-checked={!!values[s.key]}
          onClick={() => setValues((prev) => ({ ...prev, [s.key]: !prev[s.key] }))}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition ${values[s.key] ? "bg-brand-600" : "bg-slate-300"}`}
        >
          <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${values[s.key] ? "translate-x-6" : "translate-x-1"}`} />
        </button>
      );
    }
    if (s.value_type === "integer") {
      return (
        <input
          type="number"
          className="input max-w-[10rem]"
          value={values[s.key] ?? ""}
          onChange={(e) => setValues((prev) => ({ ...prev, [s.key]: e.target.value === "" ? "" : Number(e.target.value) }))}
        />
      );
    }
    return (
      <input
        className="input max-w-sm"
        value={values[s.key] ?? ""}
        onChange={(e) => setValues((prev) => ({ ...prev, [s.key]: e.target.value }))}
      />
    );
  }

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Platform-wide configuration for the Elite Portal."
        actions={
          <button className="btn-primary" onClick={save} disabled={busy}>
            {busy ? <Spinner className="text-white" /> : <><Save className="h-4 w-4" /> Save changes</>}
          </button>
        }
      />

      <div className="space-y-6">
        {[...grouped, { title: "Other", keys: [], items: others }].map((group) => (
          group.items.length > 0 && (
            <Card key={group.title} title={group.title}>
              <div className="divide-y divide-slate-100">
                {group.items.map((s: any) => (
                  <div key={s.key} className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
                    <div className="pr-4">
                      <p className="text-sm font-medium text-slate-800">{humanize(s.key)}</p>
                      {s.description && <p className="mt-0.5 text-xs text-slate-500">{s.description}</p>}
                    </div>
                    <div className="shrink-0">{renderField(s)}</div>
                  </div>
                ))}
              </div>
            </Card>
          )
        ))}
      </div>
    </div>
  );
}
