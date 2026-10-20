import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertCircle, CheckCircle2, ChevronLeft, ChevronRight, Clock, Code2, Save, Send } from "lucide-react";
import clsx from "clsx";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, PageLoader, Spinner } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function TakeAssessment() {
  const { attemptId } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();
  const { data, loading, reload } = useApi<any>(`/attempts/${attemptId}`);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [idx, setIdx] = useState(0);
  const [code, setCode] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [remaining, setRemaining] = useState<number | null>(null);
  const submittedRef = useRef(false);

  useEffect(() => {
    if (data && !data.finished) {
      const map: Record<number, number> = {};
      (data.answers || []).forEach((a: any) => { if (a.selected_option_id) map[a.question_id] = a.selected_option_id; });
      setAnswers(map);
    }
  }, [data]);

  useEffect(() => {
    if (data?.finished) {
      api.get(`/attempts/${attemptId}/result`).then(setResult).catch((e) => push(e.message, "info"));
    }
  }, [data?.finished, attemptId]);

  useEffect(() => {
    if (!data?.deadline || data.finished) return;
    const deadline = new Date(data.deadline).getTime();
    const tick = () => setRemaining(Math.max(0, Math.floor((deadline - Date.now()) / 1000)));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [data?.deadline, data?.finished]);

  const questions = data?.questions || [];
  const current = questions[idx];

  async function choose(questionId: number, optionId: number) {
    setAnswers((prev) => ({ ...prev, [questionId]: optionId }));
    try {
      await api.patch(`/attempts/${attemptId}/answers`, { question_id: questionId, selected_option_id: optionId });
    } catch (err: any) {
      if (err.code === "time_expired") push("Time is up — please submit.", "error");
    }
  }

  async function submitCode(questionId: number) {
    try {
      await api.post(`/attempts/${attemptId}/code`, { question_id: questionId, language: "python", code: code[questionId] || "" });
      push("Code saved for review.", "success");
    } catch (err: any) {
      push(err.message, "error");
    }
  }

  async function submit() {
    if (submittedRef.current) return;
    submittedRef.current = true;
    setSubmitting(true);
    try {
      const res = await api.post<any>(`/attempts/${attemptId}/submit`);
      push("Assessment submitted.", "success");
      setResult(res.attempt);
      reload();
    } catch (err: any) {
      push(err.message, "error");
      submittedRef.current = false;
    } finally {
      setSubmitting(false);
    }
  }

  const answeredCount = Object.keys(answers).length;

  if (loading || !data) return <PageLoader />;

  if (data.finished || result) {
    const attempt = result || data.attempt;
    return (
      <div className="mx-auto max-w-2xl">
        <Card className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
            <CheckCircle2 className="h-8 w-8" />
          </div>
          <h2 className="text-xl font-semibold text-slate-900">Assessment submitted</h2>
          <p className="mt-1 text-sm text-slate-500">{attempt?.assessment}</p>

          <div className="mt-6 grid grid-cols-3 gap-3">
            <Stat label="Score" value={attempt?.score ?? "—"} />
            <Stat label="Total" value={attempt?.total_marks ?? "—"} />
            <Stat label="Status" value={humanize(attempt?.status)} />
          </div>

          {attempt?.assessment_type === "betting" && (
            <div className="mt-6 rounded-xl bg-violet-50 p-4 text-left text-sm text-violet-800">
              <p className="font-medium">Betting points applied</p>
              <p className="mt-1">Locked: {attempt.locked_points} · Attendance: {attempt.attendance_points} · Total: {attempt.total_points_awarded}</p>
            </div>
          )}

          {attempt?.feedback && (
            <div className="mt-4 rounded-xl bg-slate-50 p-4 text-left text-sm text-slate-600">
              <p className="text-xs font-semibold uppercase text-slate-400">Feedback</p>
              <p className="mt-1">{attempt.feedback}</p>
            </div>
          )}

          <div className="mt-6 flex justify-center gap-2">
            <Link to="/student/assessments" className="btn-primary">Back to assessments</Link>
          </div>
        </Card>
      </div>
    );
  }

  const timeLow = remaining != null && remaining <= 60;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <button onClick={() => navigate("/student/assessments")} className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700">
          <ChevronLeft className="h-4 w-4" /> Exit
        </button>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">{answeredCount}/{questions.length} answered</span>
          {remaining != null && (
            <span className={clsx("inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-medium", timeLow ? "bg-red-50 text-red-600" : "bg-slate-100 text-slate-700")}>
              <Clock className="h-4 w-4" /> {Math.floor((remaining || 0) / 60)}:{String((remaining || 0) % 60).padStart(2, "0")}
            </span>
          )}
          <button className="btn-primary" onClick={submit} disabled={submitting}>
            {submitting ? <Spinner className="text-white" /> : <><Send className="h-4 w-4" /> Submit</>}
          </button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-4">
        <div className="lg:col-span-3">
          {current && (
            <Card>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-400">Question {idx + 1} of {questions.length}</span>
                <Badge tone="blue">{current.marks} mark(s)</Badge>
              </div>
              <p className="mt-3 whitespace-pre-wrap text-[15px] font-medium text-slate-800">{current.question_text}</p>

              {current.question_type === "coding" ? (
                <div className="mt-5">
                  {current.constraints && <p className="mb-2 whitespace-pre-wrap text-xs text-slate-500">{current.constraints}</p>}
                  <div className="mb-3 grid gap-2 sm:grid-cols-2">
                    {current.sample_input && <Sample label="Sample input" value={current.sample_input} />}
                    {current.sample_output && <Sample label="Sample output" value={current.sample_output} />}
                  </div>
                  <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
                    <Code2 className="h-4 w-4" /> Python
                    <span className="text-slate-300">·</span>
                    <span className="inline-flex items-center gap-1"><AlertCircle className="h-3.5 w-3.5" /> Auto-run is unconfigured; code is saved for coordinator review.</span>
                  </div>
                  <textarea
                    className="input min-h-56 font-mono text-sm"
                    placeholder="# Write your solution here"
                    value={code[current.id] || ""}
                    onChange={(e) => setCode({ ...code, [current.id]: e.target.value })}
                  />
                  <button className="btn-secondary mt-3" onClick={() => submitCode(current.id)}><Save className="h-4 w-4" /> Save code</button>
                </div>
              ) : (
                <div className="mt-5 space-y-2.5">
                  {current.options?.map((o: any, i: number) => {
                    const selected = answers[current.id] === o.id;
                    return (
                      <button
                        key={o.id}
                        onClick={() => choose(current.id, o.id)}
                        className={clsx(
                          "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition",
                          selected ? "border-brand-500 bg-brand-50" : "border-slate-200 hover:border-brand-200"
                        )}
                      >
                        <span className={clsx("flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold", selected ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-500")}>
                          {String.fromCharCode(65 + i)}
                        </span>
                        <span className="text-sm text-slate-700">{o.option_text}</span>
                      </button>
                    );
                  })}
                </div>
              )}

              <div className="mt-6 flex justify-between">
                <button className="btn-secondary" onClick={() => setIdx((i) => Math.max(0, i - 1))} disabled={idx === 0}>
                  <ChevronLeft className="h-4 w-4" /> Previous
                </button>
                <button className="btn-secondary" onClick={() => setIdx((i) => Math.min(questions.length - 1, i + 1))} disabled={idx === questions.length - 1}>
                  Next <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </Card>
          )}
        </div>

        <div>
          <Card title="Question palette">
            <div className="grid grid-cols-5 gap-2">
              {questions.map((q: any, i: number) => (
                <button
                  key={q.id}
                  onClick={() => setIdx(i)}
                  className={clsx(
                    "flex h-9 items-center justify-center rounded-lg text-sm font-medium",
                    i === idx ? "bg-brand-600 text-white" : answers[q.id] ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"
                  )}
                >
                  {i + 1}
                </button>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <p className="text-lg font-semibold text-slate-800">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}

function Sample({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-900 p-3 text-xs text-slate-200">
      <p className="mb-1 text-[10px] uppercase text-slate-400">{label}</p>
      <pre className="whitespace-pre-wrap font-mono">{value}</pre>
    </div>
  );
}
