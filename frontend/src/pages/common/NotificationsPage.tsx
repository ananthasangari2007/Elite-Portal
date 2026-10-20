import { useNavigate } from "react-router-dom";
import { Bell, BellRing, CheckCheck } from "lucide-react";
import clsx from "clsx";
import { useApi } from "../../lib/hooks";
import { api } from "../../lib/api";
import { relativeTime } from "../../lib/format";
import { Card, EmptyState, PageHeader, PageLoader } from "../../components/ui";

const typeTone: Record<string, string> = {
  success: "bg-emerald-100 text-emerald-600",
  warning: "bg-amber-100 text-amber-600",
  error: "bg-red-100 text-red-600",
  info: "bg-brand-100 text-brand-600",
};

export default function NotificationsPage() {
  const { data, loading, reload } = useApi<any[]>("/notifications");
  const navigate = useNavigate();

  async function open(n: any) {
    if (!n.is_read) await api.post(`/notifications/${n.id}/read`).then(reload).catch(() => {});
    if (n.link_url?.startsWith("/")) navigate(n.link_url);
  }

  return (
    <div>
      <PageHeader
        title="Notifications"
        subtitle="Updates about your assessments, tasks, points and requests."
        actions={
          <button
            className="btn-secondary"
            onClick={() => api.post("/notifications/read-all").then(reload)}
            disabled={!data?.length}
          >
            <CheckCheck className="h-4 w-4" /> Mark all read
          </button>
        }
      />

      <Card pad={false}>
        {loading ? (
          <PageLoader />
        ) : !data || data.length === 0 ? (
          <EmptyState icon={<Bell className="h-6 w-6" />} title="No notifications" description="You're all caught up." />
        ) : (
          <div className="divide-y divide-slate-100">
            {data.map((n) => (
              <button
                key={n.id}
                onClick={() => open(n)}
                className={clsx("flex w-full items-start gap-3 px-5 py-4 text-left hover:bg-slate-50", !n.is_read && "bg-brand-50/30")}
              >
                <div className={clsx("mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl", typeTone[n.type] || typeTone.info)}>
                  <BellRing className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-slate-800">{n.title}</p>
                    {!n.is_read && <span className="h-2 w-2 rounded-full bg-brand-500" />}
                  </div>
                  <p className="mt-0.5 text-sm text-slate-500">{n.message}</p>
                  <p className="mt-1 text-xs text-slate-400">{relativeTime(n.created_at)}</p>
                </div>
              </button>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
