import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  ExternalLink,
  FileText,
  Link as LinkIcon,
  Video,
} from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDuration, humanize } from "../../lib/format";
import { Badge, Card, EmptyState, PageHeader, PageLoader, ProgressBar } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

const TYPE_ICON: Record<string, any> = { video: Video, article: FileText, link: LinkIcon, pdf: FileText, document: FileText };

export default function LearningDayPage() {
  const { dayId } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();
  const { data, loading, reload } = useApi<any>(`/learning-days/${dayId}`);

  if (loading || !data) return <PageLoader />;

  async function complete() {
    try {
      const res = await api.post<any>(`/learning-days/${dayId}/complete`);
      push(res.already_completed ? "Already completed." : "Learning day completed!", "success");
      reload();
    } catch (err: any) {
      push(err.message, "error");
    }
  }

  return (
    <div>
      <button onClick={() => navigate(-1)} className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700">
        <ArrowLeft className="h-4 w-4" /> Back to learning path
      </button>

      <PageHeader
        title={`Day ${data.day_number}: ${data.title}`}
        subtitle={data.domain?.name}
        actions={
          data.completed ? (
            <Badge tone="green"><CheckCircle2 className="h-3.5 w-3.5" /> Completed</Badge>
          ) : (
            <button className="btn-primary" onClick={complete}><CheckCircle2 className="h-4 w-4" /> Mark day complete</button>
          )
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {(data.description || data.learning_objectives) && (
            <Card title="About this day">
              {data.description && <p className="text-sm text-slate-600">{data.description}</p>}
              {data.learning_objectives && (
                <div className="mt-3 rounded-xl bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase text-slate-400">Learning objectives</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{data.learning_objectives}</p>
                </div>
              )}
            </Card>
          )}

          <Card title={`Learning materials (${data.materials?.length || 0})`} pad={false}>
            {!data.materials?.length ? (
              <EmptyState title="No materials" description="Materials for this day will appear here." />
            ) : (
              <div className="divide-y divide-slate-100">
                {data.materials.map((m: any) => {
                  const Icon = TYPE_ICON[m.material_type] || FileText;
                  return (
                    <div key={m.id} className="flex items-center gap-4 px-5 py-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-slate-800">{m.title}</p>
                        <p className="text-xs text-slate-500">
                          {humanize(m.material_type)}{m.duration_minutes ? ` · ${formatDuration(m.duration_minutes)}` : ""}
                          {m.file_size_display ? ` · ${m.file_size_display}` : ""}
                        </p>
                      </div>
                      {(m.url || m.file_key) && (
                        <a href={m.url || `/api/v1/files/${m.file_key}`} target="_blank" rel="noreferrer" className="btn-secondary !px-3 !py-1.5">
                          <ExternalLink className="h-4 w-4" /> Open
                        </a>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Progress">
            <ProgressBar value={data.completed ? 100 : 0} tone={data.completed ? "green" : "brand"} />
            <p className="mt-2 text-sm text-slate-500">{data.completed ? "You've completed this day." : "Mark this day complete once you finish the materials."}</p>
          </Card>

          {data.assessments?.length > 0 && (
            <Card title="Assessments for this day" pad={false}>
              <div className="divide-y divide-slate-100">
                {data.assessments.map((a: any) => (
                  <Link key={a.id} to="/student/assessments" className="flex items-center gap-3 px-5 py-3.5 hover:bg-slate-50">
                    <ClipboardCheck className="h-4 w-4 text-slate-400" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-800">{a.title}</p>
                      <p className="text-xs text-slate-500">{humanize(a.assessment_type)} · {a.total_marks} marks</p>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
