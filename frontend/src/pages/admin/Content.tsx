import { useState } from "react";
import { FileText, Search } from "lucide-react";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, EmptyState, ErrorState, Field, PageHeader, Pagination, PageLoader, StatusBadge } from "../../components/ui";

const TYPES = ["all", "day", "material", "assessment", "task"];

const typeTone: Record<string, any> = {
  video: "violet",
  pdf: "red",
  document: "blue",
  link: "blue",
  code: "green",
  day: "amber",
  material: "blue",
  assessment: "violet",
  task: "green",
};

export default function AdminContent() {
  const [page, setPage] = useState(1);
  const [type, setType] = useState("all");
  const [domainId, setDomainId] = useState("");
  const [search, setSearch] = useState("");
  const { data: domains } = useApi<any[]>("/domains");

  const params: any = { page, per_page: 30 };
  if (type) params.type = type;
  if (domainId) params.domain_id = domainId;
  if (search.trim()) params.search = search.trim();

  const { data, meta, loading, error, reload } = useApi<any[]>("/admin/content", params);

  function reset(next: () => void) {
    setPage(1);
    next();
  }

  return (
    <div>
      <PageHeader title="Content Registry" subtitle="Read-only view of all published learning content across domains." />

      <Card className="mb-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Search">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input className="input pl-9" placeholder="Title contains…" value={search} onChange={(e) => reset(() => setSearch(e.target.value))} />
            </div>
          </Field>
          <Field label="Type">
            <select className="input" value={type} onChange={(e) => reset(() => setType(e.target.value))}>
              {TYPES.map((t) => <option key={t} value={t}>{humanize(t === "all" ? "all types" : t)}</option>)}
            </select>
          </Field>
          <Field label="Domain">
            <select className="input" value={domainId} onChange={(e) => reset(() => setDomainId(e.target.value))}>
              <option value="">All domains</option>
              {(domains || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
        </div>
      </Card>

      <Card pad={false}>
        {loading ? (
          <PageLoader />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !data?.length ? (
          <EmptyState icon={<FileText className="h-6 w-6" />} title="No content found" description="Try adjusting the filters." />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Type</th>
                    <th>Domain</th>
                    <th>Day</th>
                    <th>Status</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((item) => {
                    const kind = item.material_type || item.type || "material";
                    return (
                      <tr key={`${kind}-${item.id}`}>
                        <td className="font-medium text-slate-800">{item.title}</td>
                        <td><Badge tone={typeTone[kind] || "slate"}>{humanize(kind)}</Badge></td>
                        <td className="text-slate-700">{item.domain || "—"}</td>
                        <td className="text-slate-500">
                          {item.day_number ? `Day ${item.day_number}${item.day_title ? ` · ${item.day_title}` : ""}` : "—"}
                        </td>
                        <td><StatusBadge status={item.status} /></td>
                        <td className="whitespace-nowrap text-slate-500">{formatDateTime(item.created_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination page={meta?.page || 1} pages={meta?.pages || 1} total={meta?.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
