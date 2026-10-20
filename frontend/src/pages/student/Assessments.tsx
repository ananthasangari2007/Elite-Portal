import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarClock, ClipboardCheck, Clock, Play, RotateCcw, Trophy } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, EmptyState, Modal, PageHeader, PageLoader, Tabs } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function StudentAssessments() {
  const { data, loading, reload } = useApi<any[]>("/student/assessments");
  const [tab, setTab] = useState("available");
  const [instructions, setInstructions] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const { push } = useToast();

  const list = data || [];
  const filtered = list.filter((a) => {
    if (tab === "available") return a.available && a.attempts_used < a.max_attempts;
    if (tab === "in_progress") return a.active_attempt_id;
    if (tab === "completed") return a.latest_attempt;
    return true;
  });

  async function open(id: number) {
    const res = await api.get(`/assessments/${id}/instructions`);
    setInstructions(res);
  }

  async function start(id: number) {
    setBusy(true);
    try {
      const res = await api.post<any>(`/assessments/${id}/start`);
      const attemptId = res.attempt?.id ?? res.attempt?.id;
      navigate(`/student/assessments/${attemptId}/take`);
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title="Assessments" subtitle="Attempt MCQ, betting and coding assessments assigned to your domains." />

      <Tabs
        tabs={[
          { key: "available", label: "Available", count: list.filter((a) => a.available && a.attempts_used < a.max_attempts).length },
          { key: "in_progress", label: "In progress", count: list.filter((a) => a.active_attempt_id).length },
          { key: "completed", label: "Completed", count: list.filter((a) => a.latest_attempt).length },
          { key: "all", label: "All", count: list.length },
        ]}
        active={tab}
        onChange={setTab}
      />

      {loading ? (
        <PageLoader />
      ) : !filtered.length ? (
        <Card className="mt-6"><EmptyState icon={<ClipboardCheck className="h-6 w-6" />} title="No assessments here" description="Check another tab or wait for your coordinator to publish assessments." /></Card>
      ) : (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {filtered.map((a) => (
            <Card key={a.id} className="flex flex-col">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                    <ClipboardCheck className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-medium text-slate-800">{a.title}</p>
                    <p className="text-xs text-slate-400">{a.domain} · {humanize(a.assessment_type)}</p>
                  </div>
                </div>
                <Badge tone={a.assessment_type === "betting" ? "violet" : a.assessment_type === "coding" ? "blue" : "green"}>
                  {humanize(a.assessment_type)}
                </Badge>
              </div>

              <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
                <span className="inline-flex items-center gap-1"><Trophy className="h-3.5 w-3.5" /> {a.total_marks} marks</span>
                {a.time_limit_minutes && <span className="inline-flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {a.time_limit_minutes} min</span>}
                <span className="inline-flex items-center gap-1"><RotateCcw className="h-3.5 w-3.5" /> {a.attempts_used}/{a.max_attempts} attempts</span>
                {a.scheduled_end && <span className="inline-flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" /> ends {formatDateTime(a.scheduled_end)}</span>}
              </div>

              {a.latest_attempt && (
                <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Last attempt</span>
                    <span className="font-semibold text-slate-800">
                      {a.latest_attempt.score}/{a.latest_attempt.total_marks}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between">
                    <span className="text-xs text-slate-400">Status</span>
                    <Badge tone={a.latest_attempt.status === "graded" ? "green" : "amber"}>{humanize(a.latest_attempt.status)}</Badge>
                  </div>
                </div>
              )}

              <div className="mt-4 flex justify-end gap-2">
                <button className="btn-secondary" onClick={() => open(a.id)}>View details</button>
                {a.active_attempt_id ? (
                  <button className="btn-primary" onClick={() => navigate(`/student/assessments/${a.active_attempt_id}/take`)}>
                    <Play className="h-4 w-4" /> Resume
                  </button>
                ) : a.available && a.attempts_used < a.max_attempts ? (
                  <button className="btn-primary" onClick={() => open(a.id)}>
                    <Play className="h-4 w-4" /> Start
                  </button>
                ) : null}
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={!!instructions}
        onClose={() => setInstructions(null)}
        title={instructions?.title || "Assessment"}
        subtitle={instructions ? `${humanize(instructions.assessment_type)} · ${instructions.total_marks} marks` : ""}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setInstructions(null)}>Close</button>
            {(instructions?.attempts_remaining > 0 || instructions?.active_attempt_id) && instructions?.available && (
              <button className="btn-primary" disabled={busy} onClick={() => instructions.active_attempt_id ? navigate(`/student/assessments/${instructions.active_attempt_id}/take`) : start(instructions.id)}>
                <Play className="h-4 w-4" /> {instructions.active_attempt_id ? "Resume attempt" : "Start attempt"}
              </button>
            )}
          </>
        }
      >
        {instructions && (
          <div className="space-y-4 text-sm text-slate-600">
            {instructions.description && <p>{instructions.description}</p>}
            {instructions.instructions && (
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase text-slate-400">Instructions</p>
                <p className="mt-1 whitespace-pre-wrap">{instructions.instructions}</p>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Info label="Questions" value={instructions.question_count} />
              <Info label="Marks" value={instructions.total_marks} />
              <Info label="Time limit" value={instructions.time_limit_minutes ? `${instructions.time_limit_minutes} min` : "None"} />
              <Info label="Attempts left" value={instructions.attempts_remaining} />
            </div>
            {instructions.latest_result && (
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs font-semibold uppercase text-slate-400">Previous attempt</p>
                <p className="mt-1 text-slate-700">Score: <span className="font-semibold">{instructions.latest_result.score}/{instructions.latest_result.total_marks}</span></p>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}

function Info({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3 text-center">
      <p className="text-lg font-semibold text-slate-800">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}
