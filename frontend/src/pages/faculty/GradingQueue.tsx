import { useMemo, useState } from "react";
import {
  CheckCircle2,
  ClipboardCheck,
  GraduationCap,
  ListChecks,
  MousePointerClick,
  UserCheck,
} from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Modal,
  PageHeader,
  PageLoader,
  Pagination,
  Tabs,
} from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

const TABS = [
  { key: "submitted", label: "Needs grading" },
  { key: "graded", label: "Graded" },
  { key: "all", label: "All" },
];

export default function GradingQueue() {
  const [tab, setTab] = useState("submitted");
  const [page, setPage] = useState(1);
  const [gradeId, setGradeId] = useState<number | null>(null);

  const params = useMemo(() => {
    const base: Record<string, any> = { page };
    if (tab !== "all") base.status = tab;
    return base;
  }, [tab, page]);

  const { data, meta, loading, error, reload } = useApi<any[]>("/coordinator/submissions", params);

  const rows = data || [];

  return (
    <div>
      <PageHeader
        title="Grading Queue"
        subtitle="Review student submissions and award scores across your domains."
        actions={
          <button className="btn-secondary" onClick={reload}>
            Refresh
          </button>
        }
      />

      <Tabs
        tabs={TABS}
        active={tab}
        onChange={(key) => {
          setTab(key);
          setPage(1);
        }}
      />

      <Card className="mt-6" pad={false}>
        {loading ? (
          <PageLoader label="Loading submissions" />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !rows.length ? (
          <EmptyState icon={<ClipboardCheck className="h-6 w-6" />} title="Nothing to grade" description="Submissions will appear here as students submit assessments." />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Assessment</th>
                    <th>Domain / Type</th>
                    <th>Status</th>
                    <th>Score</th>
                    <th>Submitted</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((a: any) => (
                    <tr key={a.id}>
                      <td>
                        <p className="font-medium text-slate-800">{a.student}</p>
                        <p className="text-xs text-slate-400">{a.register_number}</p>
                      </td>
                      <td className="text-slate-700">{a.assessment}</td>
                      <td>
                        <Badge tone={a.assessment_type === "betting" ? "violet" : a.assessment_type === "coding" ? "blue" : "green"}>
                          {humanize(a.assessment_type)}
                        </Badge>
                      </td>
                      <td>
                        <Badge tone={a.status === "graded" ? "green" : "amber"}>{humanize(a.status)}</Badge>
                      </td>
                      <td className="text-slate-600">
                        {a.score != null ? `${a.score}/${a.total_marks ?? "—"}` : "—"}
                      </td>
                      <td className="whitespace-nowrap text-slate-500">{a.submitted_at ? formatDateTime(a.submitted_at) : "—"}</td>
                      <td className="text-right">
                        <button className="btn-primary !px-3 !py-1.5" onClick={() => setGradeId(a.id)}>
                          <GraduationCap className="h-4 w-4" /> Grade
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={meta?.page || 1} pages={meta?.pages || 1} total={meta?.total} onPage={setPage} />
          </>
        )}
      </Card>

      {gradeId != null && (
        <GradeModal
          attemptId={gradeId}
          onClose={() => setGradeId(null)}
          onDone={() => {
            setGradeId(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

function GradeModal({ attemptId, onClose, onDone }: { attemptId: number; onClose: () => void; onDone: () => void }) {
  const { data, loading, error } = useApi<any>(`/coordinator/submissions/${attemptId}`);
  const { push } = useToast();
  const [mode, setMode] = useState<"total" | "answers">("total");
  const [score, setScore] = useState("");
  const [feedback, setFeedback] = useState("");
  const [attended, setAttended] = useState(true);
  const [marks, setMarks] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);

  const questions: any[] = data?.questions || [];
  const isBetting = data?.assessment_type === "betting";
  const totalMarks = data?.total_marks ?? data?.assessment_total_marks ?? 0;

  async function submitTotal() {
    setBusy(true);
    try {
      await api.post(`/coordinator/submissions/${attemptId}/grade`, {
        score: Number(score),
        feedback,
      });
      push("Submission graded.", "success");
      onDone();
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswers() {
    setBusy(true);
    try {
      await api.post(`/coordinator/submissions/${attemptId}/grade`, {
        answer_scores: questions.map((q: any) => ({
          question_id: q.id,
          marks_awarded: Number(marks[q.id] ?? 0),
        })),
        feedback,
      });
      push("Submission graded.", "success");
      onDone();
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function submitAttendance() {
    setBusy(true);
    try {
      await api.post(`/coordinator/submissions/${attemptId}/attendance`, {
        attended,
        score: score === "" ? undefined : Number(score),
        feedback,
      });
      push("Attendance and betting points updated.", "success");
      onDone();
    } catch (err: any) {
      push(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={data?.assessment || "Submission"}
      subtitle={data ? `${data.student} · ${humanize(data.assessment_type)}` : "Loading…"}
      size="lg"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          {isBetting ? (
            <button className="btn-primary" onClick={submitAttendance} disabled={busy || loading}>
              <UserCheck className="h-4 w-4" /> Save attendance
            </button>
          ) : mode === "total" ? (
            <button className="btn-primary" onClick={submitTotal} disabled={busy || loading || score === ""}>
              <CheckCircle2 className="h-4 w-4" /> Save score
            </button>
          ) : (
            <button className="btn-primary" onClick={submitAnswers} disabled={busy || loading}>
              <CheckCircle2 className="h-4 w-4" /> Save marks
            </button>
          )}
        </>
      }
    >
      {loading || !data ? (
        <PageLoader />
      ) : error ? (
        <ErrorState message={error} />
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Info label="Status" value={humanize(data.status)} />
            <Info label="Total marks" value={totalMarks || "—"} />
            <Info label="Current score" value={data.score ?? "—"} />
            <Info label="Submitted" value={data.submitted_at ? formatDateTime(data.submitted_at) : "—"} />
          </div>

          {isBetting ? (
            <div className="space-y-4">
              <label className="flex items-center gap-3 rounded-xl border border-slate-200 p-4">
                <input type="checkbox" checked={attended} onChange={(e) => setAttended(e.target.checked)} />
                <span className="text-sm text-slate-700">Student attended the betting assessment session</span>
              </label>
              <Field label="Score (optional)" hint="Betting points are recomputed automatically from attendance and locked points.">
                <input className="input" type="number" min={0} value={score} onChange={(e) => setScore(e.target.value)} placeholder="Leave blank to keep current" />
              </Field>
              <Field label="Feedback">
                <textarea className="input min-h-24" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
              </Field>
            </div>
          ) : (
            <>
              <Tabs
                tabs={[
                  { key: "total", label: "Total score" },
                  { key: "answers", label: "Per-question marks" },
                ]}
                active={mode}
                onChange={(k) => setMode(k as "total" | "answers")}
              />

              {mode === "total" ? (
                <Field label="Total score" hint={totalMarks ? `Maximum ${totalMarks} marks.` : undefined}>
                  <input className="input" type="number" min={0} value={score} onChange={(e) => setScore(e.target.value)} />
                </Field>
              ) : !questions.length ? (
                <EmptyState icon={<ListChecks className="h-6 w-6" />} title="No questions available" description="This submission has no gradable questions." />
              ) : (
                <div className="space-y-3">
                  {questions.map((q: any, index: number) => (
                    <div key={q.id} className="rounded-xl border border-slate-200 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-medium text-slate-800">
                          <span className="mr-2 text-slate-400">Q{index + 1}.</span>
                          {q.question_text}
                        </p>
                        <Badge tone="slate">/ {q.marks}</Badge>
                      </div>
                      {q.answer && (
                        <p className="mt-1 text-xs text-slate-500">
                          {q.question_type === "mcq"
                            ? `Selected: ${(q.options || []).find((o: any) => o.id === q.answer.selected_option_id)?.option_text || "—"}`
                            : `Auto marks: ${q.answer.marks_awarded ?? 0}`}
                        </p>
                      )}
                      <div className="mt-3 flex items-center gap-2">
                        <MousePointerClick className="h-4 w-4 text-slate-400" />
                        <input
                          className="input max-w-[7rem]"
                          type="number"
                          min={0}
                          max={q.marks}
                          placeholder="0"
                          value={marks[q.id] ?? ""}
                          onChange={(e) => setMarks({ ...marks, [q.id]: e.target.value })}
                        />
                        <span className="text-xs text-slate-400">of {q.marks} marks</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <Field label="Feedback">
                <textarea className="input min-h-24" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
              </Field>
            </>
          )}
        </div>
      )}
    </Modal>
  );
}

function Info({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3 text-center">
      <p className="text-sm font-semibold text-slate-800">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}
