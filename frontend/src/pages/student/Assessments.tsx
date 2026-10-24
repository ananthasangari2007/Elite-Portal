import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  Camera,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  Maximize2,
  Play,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Trophy,
  Video,
} from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, EmptyState, Modal, PageHeader, PageLoader, Tabs } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function StudentAssessments() {
  const [searchParams] = useSearchParams();
  const { data, loading, reload } = useApi<any[]>("/student/assessments");
  const [tab, setTab] = useState("available");
  const [instructions, setInstructions] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [honorAccepted, setHonorAccepted] = useState(false);
  const [cameraReady, setCameraReady] = useState(true);
  const [screenReady, setScreenReady] = useState(true);
  const navigate = useNavigate();
  const { push } = useToast();

  const list = data || [];
  const filtered = list.filter((a) => {
    if (tab === "available") return (a.available && a.attempts_used < a.max_attempts) || a.active_attempt_id;
    if (tab === "completed") return a.latest_attempt;
    return true;
  });

  // Automatically open assessment modal if query parameter ?id=... is present
  useEffect(() => {
    const targetId = searchParams.get("id");
    if (targetId && list.length > 0 && !instructions) {
      open(Number(targetId));
    }
  }, [searchParams, list]);

  async function open(id: number) {
    try {
      const res = await api.get<any>(`/assessments/${id}/instructions`);
      setInstructions(res);
      setHonorAccepted(false);
    } catch (err: any) {
      push(err.message, "error");
    }
  }

  async function start(id: number) {
    setBusy(true);
    try {
      // Attempt fullscreen before navigation if supported
      if (document.documentElement.requestFullscreen) {
        try {
          await document.documentElement.requestFullscreen();
        } catch (_) {}
      }
      const res = await api.post<any>(`/assessments/${id}/start`);
      const attemptId = res.attempt?.id ?? res.id;
      navigate(`/student/assessments/${attemptId}/take`);
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Assessments"
        subtitle="Attempt MCQ, betting and coding assessments assigned to your domains."
      />

      <Tabs
        tabs={[
          {
            key: "available",
            label: "Available",
            count: list.filter((a) => (a.available && a.attempts_used < a.max_attempts) || a.active_attempt_id).length,
          },
          {
            key: "completed",
            label: "Completed",
            count: list.filter((a) => a.latest_attempt).length,
          },
          { key: "all", label: "All", count: list.length },
        ]}
        active={tab}
        onChange={setTab}
      />

      {loading ? (
        <PageLoader />
      ) : !filtered.length ? (
        <Card className="mt-6">
          <EmptyState
            icon={<ClipboardCheck className="h-6 w-6" />}
            title="No assessments here"
            description="Check another tab or wait for your coordinator to publish assessments."
          />
        </Card>
      ) : (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {filtered.map((a) => {
            const isAvailable = a.available;
            const hasAttemptsLeft = (a.attempts_remaining ?? (a.max_attempts - a.attempts_used)) > 0;
            const canStart = isAvailable && hasAttemptsLeft;

            return (
              <Card key={a.id} className="flex flex-col justify-between">
                <div>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                        <ClipboardCheck className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-800">{a.title}</p>
                        <p className="text-xs text-slate-400">
                          {a.domain} · {humanize(a.assessment_type)}
                        </p>
                      </div>
                    </div>
                    <Badge
                      tone={
                        a.assessment_type === "betting"
                          ? "violet"
                          : a.assessment_type === "coding"
                          ? "blue"
                          : "green"
                      }
                    >
                      {humanize(a.assessment_type)}
                    </Badge>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
                    <span className="inline-flex items-center gap-1">
                      <Trophy className="h-3.5 w-3.5" /> {a.total_marks} marks
                    </span>
                    {a.time_limit_minutes && (
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" /> {a.time_limit_minutes} min
                      </span>
                    )}
                    <span className="inline-flex items-center gap-1">
                      <RotateCcw className="h-3.5 w-3.5" /> {a.attempts_used}/{a.max_attempts} attempts
                    </span>
                    {a.scheduled_end && (
                      <span className="inline-flex items-center gap-1">
                        <CalendarClock className="h-3.5 w-3.5" /> ends {formatDateTime(a.scheduled_end)}
                      </span>
                    )}
                  </div>

                  {a.lock_reason && !a.active_attempt_id && (
                    <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2 text-xs text-amber-800">
                      {a.lock_reason === "scheduled_countdown" && (
                        <span>Scheduled: opens at {a.scheduled_start ? formatDateTime(a.scheduled_start) : "scheduled time"}.</span>
                      )}
                      {a.lock_reason === "window_expired" && (
                        <span>Assessment window closed on {formatDateTime(a.scheduled_end)}. Contact faculty for an unlock.</span>
                      )}
                      {a.lock_reason === "no_attempts_left" && (
                        <span>All allowed attempts used. Request Faculty Coordinator for an unlock override.</span>
                      )}
                      {a.lock_reason === "not_published" && (
                        <span>Assessment is scheduled or awaiting proctor authorization.</span>
                      )}
                    </div>
                  )}

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
                        <Badge tone={a.latest_attempt.status === "graded" ? "green" : "amber"}>
                          {humanize(a.latest_attempt.status)}
                        </Badge>
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-4 flex justify-end gap-2 pt-2 border-t border-slate-100">
                  <button className="btn-secondary" onClick={() => open(a.id)}>
                    View details & instructions
                  </button>
                  {a.active_attempt_id ? (
                    <button
                      className="btn-primary"
                      onClick={() => navigate(`/student/assessments/${a.active_attempt_id}/take`)}
                    >
                      <Play className="h-4 w-4" /> Resume
                    </button>
                  ) : canStart ? (
                    <button className="btn-primary" onClick={() => open(a.id)}>
                      <Play className="h-4 w-4" /> Start
                    </button>
                  ) : null}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Unstop-Style Proctored Pre-Flight & Instructions Modal */}
      <Modal
        open={!!instructions}
        onClose={() => setInstructions(null)}
        title={instructions?.title || "Assessment Instructions"}
        subtitle={
          instructions
            ? `${humanize(instructions.assessment_type)} · ${instructions.total_marks} marks · ${
                instructions.domain || "Domain"
              }`
            : ""
        }
        size="lg"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setInstructions(null)}>
              Close
            </button>
            {instructions?.active_attempt_id ? (
              <button
                className="btn-primary"
                onClick={() => navigate(`/student/assessments/${instructions.active_attempt_id}/take`)}
              >
                <Play className="h-4 w-4" /> Resume attempt
              </button>
            ) : instructions?.available && (instructions?.attempts_remaining > 0 || instructions?.is_authorized) ? (
              <button
                className="btn-primary"
                disabled={busy || !honorAccepted}
                onClick={() => start(instructions.id)}
              >
                <Play className="h-4 w-4" /> Start Proctored Assessment
              </button>
            ) : (
              <span className="text-xs text-slate-400 px-3 py-2">
                {instructions?.lock_reason === "no_attempts_left"
                  ? "Max attempts reached"
                  : instructions?.lock_reason === "scheduled_countdown"
                  ? "Scheduled countdown active"
                  : "Currently unavailable"}
              </span>
            )}
          </>
        }
      >
        {instructions && (
          <div className="space-y-4 text-sm text-slate-600">
            {instructions.description && <p className="text-slate-700">{instructions.description}</p>}

            {instructions.instructions && (
              <div className="rounded-xl bg-slate-50 p-4 border border-slate-200">
                <p className="text-xs font-semibold uppercase text-slate-500">Assessment Instructions</p>
                <p className="mt-1 whitespace-pre-wrap text-slate-700">{instructions.instructions}</p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Info label="Questions" value={instructions.question_count} />
              <Info label="Total Marks" value={instructions.total_marks} />
              <Info
                label="Time limit"
                value={instructions.time_limit_minutes ? `${instructions.time_limit_minutes} min` : "None"}
              />
              <Info
                label="Attempts left"
                value={instructions.attempts_remaining ?? (instructions.max_attempts - instructions.attempts_used)}
              />
            </div>

            {/* Lock / schedule alert if unavailable */}
            {!instructions.available && instructions.lock_reason && (
              <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-900 flex items-start gap-3">
                <ShieldAlert className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-sm">
                    {instructions.lock_reason === "scheduled_countdown"
                      ? "Assessment is not open yet"
                      : instructions.lock_reason === "window_expired"
                      ? "Assessment window has closed"
                      : instructions.lock_reason === "no_attempts_left"
                      ? "All allowed attempts used"
                      : "Assessment is locked"}
                  </p>
                  <p className="text-xs mt-1 text-amber-700">
                    {instructions.lock_reason === "scheduled_countdown"
                      ? `Opens at ${instructions.scheduled_start ? formatDateTime(instructions.scheduled_start) : "scheduled time"}.`
                      : instructions.lock_reason === "window_expired"
                      ? `The assessment ended on ${formatDateTime(instructions.scheduled_end)}. If you experienced technical issues, request an unlock override from your Faculty Coordinator.`
                      : instructions.lock_reason === "no_attempts_left"
                      ? "You have exhausted your attempts for this assessment. Contact Faculty Coordinator to authorize an additional attempt."
                      : "This assessment requires authorization or publishing."}
                  </p>
                </div>
              </div>
            )}

            {/* Unstop Proctored Pre-Flight Checks */}
            {instructions.available && (instructions.attempts_remaining > 0 || instructions.is_authorized) && (
              <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-4 space-y-3">
                <div className="flex items-center gap-2 text-indigo-950 font-semibold text-sm">
                  <ShieldCheck className="h-4 w-4 text-indigo-600" />
                  <span>Proctored Environment Pre-Flight Checklist</span>
                </div>

                <div className="grid gap-2.5 sm:grid-cols-2 text-xs">
                  <div className="flex items-center gap-2.5 rounded-lg bg-white p-2.5 border border-indigo-100">
                    <Camera className="h-4 w-4 text-emerald-600" />
                    <div>
                      <p className="font-medium text-slate-800">Webcam Monitor</p>
                      <p className="text-[11px] text-slate-400">Monitoring & presence detection active</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 rounded-lg bg-white p-2.5 border border-indigo-100">
                    <Maximize2 className="h-4 w-4 text-brand-600" />
                    <div>
                      <p className="font-medium text-slate-800">Fullscreen Enforcement</p>
                      <p className="text-[11px] text-slate-400">Exits will be recorded as integrity flags</p>
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-indigo-100">
                  <label className="flex items-start gap-2.5 cursor-pointer text-xs text-slate-700">
                    <input
                      type="checkbox"
                      checked={honorAccepted}
                      onChange={(e) => setHonorAccepted(e.target.checked)}
                      className="mt-0.5 rounded border-indigo-300 text-brand-600 focus:ring-brand-500"
                    />
                    <span>
                      <strong>Academic Honor Pledge:</strong> I confirm that I will complete this assessment
                      independently without unauthorized external resources or aids. I acknowledge that window blurs,
                      copy-paste attempts, and tab switching are monitored and recorded.
                    </span>
                  </label>
                </div>
              </div>
            )}

            {instructions.latest_result && (
              <div className="rounded-xl border border-slate-200 p-4 bg-slate-50">
                <p className="text-xs font-semibold uppercase text-slate-500">Previous Attempt Result</p>
                <p className="mt-1 text-slate-700 font-medium">
                  Score:{" "}
                  <span className="font-semibold text-slate-900">
                    {instructions.latest_result.score}/{instructions.latest_result.total_marks}
                  </span>{" "}
                  ({humanize(instructions.latest_result.status)})
                </p>
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
    <div className="rounded-xl bg-slate-50 p-3 text-center border border-slate-100">
      <p className="text-lg font-semibold text-slate-800">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}
