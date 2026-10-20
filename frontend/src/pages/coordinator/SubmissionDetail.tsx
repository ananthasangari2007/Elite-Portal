import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CalendarClock, CheckCircle2, FileText, History } from "lucide-react";
import { api } from "../../lib/api";
import { formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, Field, PageHeader, PageLoader, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function SubmissionDetail() {
  const { attemptId } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [answerScores, setAnswerScores] = useState<Record<number, number>>({});
  const [totalScore, setTotalScore] = useState<string>("");
  const [feedback, setFeedback] = useState("");
  const [attended, setAttended] = useState(true);
  const [bettingScore, setBettingScore] = useState<string>("");

  useEffect(() => {
    if (!attemptId) return;
    (async () => {
      try {
        const res = await api.get<any>(`/coordinator/submissions/${attemptId}`);
        setData(res);
        const answers = res.answers || [];
        const scores: Record<number, number> = {};
        answers.forEach((a: any) => {
          if (a.marks_awarded != null) scores[a.question_id] = a.marks_awarded;
        });
        setAnswerScores(scores);
        setFeedback(res.attempt?.feedback || "");
        setTotalScore(res.attempt?.score != null ? String(res.attempt.score) : "");
        setAttended(res.attempt?.attended !== false);
        if (res.attempt?.score != null) setBettingScore(String(res.attempt.score));
      } finally {
        setLoading(false);
      }
    })();
  }, [attemptId]);

  async function grade() {
    if (!attemptId || !data) return;
    setSaving(true);
    try {
      const answers = data.answers || [];
      const payload: any = { feedback };
      if (answers.length > 0) {
        const answer_scores = answers.map((a: any) => ({
          question_id: a.question_id,
          marks_awarded: Number(answerScores[a.question_id] ?? 0),
        }));
        payload.answer_scores = answer_scores;
      } else if (totalScore !== "") {
        payload.score = Number(totalScore);
      }
      await api.post(`/coordinator/submissions/${attemptId}/grade`, payload);
      push("Submission graded", "success");
      const res = await api.get<any>(`/coordinator/submissions/${attemptId}`);
      setData(res);
    } catch (e: any) {
      push(e.message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function setAttendance() {
    if (!attemptId) return;
    setSaving(true);
    try {
      const payload: any = { attended };
      if (bettingScore !== "") payload.score = Number(bettingScore);
      const res = await api.post<any>(`/coordinator/submissions/${attemptId}/attendance`, payload);
      push("Attendance updated", "success");
      setData({ ...data, attempt: res.attempt });
    } catch (e: any) {
      push(e.message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function requestChanges() {
    if (!attemptId) return;
    if (feedback.length < 5) {
      push("Please add feedback explaining changes", "error");
      return;
    }
    setSaving(true);
    try {
      await api.post(`/coordinator/submissions/${attemptId}/request-changes`, { feedback });
      push("Changes requested", "success");
      const res = await api.get<any>(`/coordinator/submissions/${attemptId}`);
      setData(res);
    } catch (e: any) {
      push(e.message, "error");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <PageLoader />;
  if (!data) return null;

  const attempt = data.attempt || data;
  const answers = data.answers || [];
  const coding = data.coding_submissions || [];
  const history = data.grading_history || [];

  return (
    <div>
      <PageHeader
        title="Submission Details"
        subtitle={`${attempt.student} · ${attempt.assessment}`}
        actions={
          <button className="btn-secondary" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Assessment Info">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <p className="text-xs text-slate-500">Assessment</p>
                <p className="text-sm font-medium text-slate-800">{attempt.assessment}</p>
                <p className="text-xs text-slate-500">{humanize(attempt.assessment_type)} · {attempt.total_marks} marks</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Student</p>
                <p className="text-sm font-medium text-slate-800">{attempt.student}</p>
                <p className="text-xs text-slate-500">{attempt.register_number}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Status</p>
                <div className="mt-1"><StatusBadge status={attempt.status} /></div>
              </div>
              <div>
                <p className="text-xs text-slate-500">Submitted</p>
                <p className="text-sm text-slate-800">{attempt.submitted_at ? formatDateTime(attempt.submitted_at) : "—"}</p>
                <p className="text-xs text-slate-500">{attempt.time_taken_seconds ? `${Math.round(attempt.time_taken_seconds / 60)} min` : ""}</p>
              </div>
            </div>
          </Card>

          {answers.length > 0 && (
            <Card title="Answers" pad={false}>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Question</th>
                      <th>Marks</th>
                      <th>Selected</th>
                      <th>Correct</th>
                      <th>Marks Awarded</th>
                    </tr>
                  </thead>
                  <tbody>
                    {answers.map((a: any, idx: number) => (
                      <tr key={a.question_id}>
                        <td className="max-w-lg">
                          <p className="text-sm text-slate-800">{a.question_text || `Q${idx + 1}`}</p>
                        </td>
                        <td className="text-slate-500">{a.marks}</td>
                        <td className="text-slate-500">{a.selected_option_id || "—"}</td>
                        <td>{a.is_correct ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : null}</td>
                        <td>
                          <input
                            type="number"
                            className="input w-24"
                            value={answerScores[a.question_id] ?? ""}
                            onChange={(e) => setAnswerScores({ ...answerScores, [a.question_id]: Number(e.target.value) })}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {coding.length > 0 && (
            <Card title="Coding Submissions">
              {coding.map((c: any) => (
                <div key={c.id} className="mb-4 rounded-xl border border-slate-200 p-4">
                  <p className="text-sm font-medium text-slate-800">Question {c.question_id} · {c.language}</p>
                  <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                    {c.code}
                  </pre>
                  {c.test_results?.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs font-semibold text-slate-500">Test Results</p>
                      <div className="mt-2 space-y-2">
                        {c.test_results.map((t: any, i: number) => (
                          <div key={i} className="rounded-lg bg-slate-50 p-2 text-xs">
                            <p>{t.passed ? "PASS" : "FAIL"} · Points {t.points_awarded || 0}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </Card>
          )}

          <Card title="Grading">
            {answers.length === 0 && (
              <Field label="Total Score">
                <input type="number" className="input w-32" value={totalScore} onChange={(e) => setTotalScore(e.target.value)} />
              </Field>
            )}
            <Field label="Feedback">
              <textarea className="input min-h-[100px]" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
            </Field>
            <div className="mt-4 flex gap-2">
              <button className="btn-primary" disabled={saving} onClick={grade}>
                Submit Grade
              </button>
              <button className="btn-secondary" disabled={saving} onClick={requestChanges}>
                Request Changes
              </button>
            </div>
          </Card>

          {attempt.assessment_type === "betting" && (
            <Card title="Attendance & Betting Points">
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={attended} onChange={(e) => setAttended(e.target.checked)} />
                  Attended
                </label>
                <Field label="Score">
                  <input type="number" className="input w-32" value={bettingScore} onChange={(e) => setBettingScore(e.target.value)} />
                </Field>
              </div>
              <button className="btn-primary mt-3" disabled={saving} onClick={setAttendance}>
                Apply
              </button>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card title="Grading History" pad={false}>
            {!history.length ? (
              <EmptyState icon={<History className="h-6 w-6" />} title="No history" />
            ) : (
              <div className="divide-y divide-slate-100">
                {history.map((h: any) => (
                  <div key={h.id} className="px-5 py-3.5">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium text-slate-800">{humanize(h.action)}</p>
                      <span className="text-xs text-slate-500">{h.created_at ? formatDateTime(h.created_at) : ""}</span>
                    </div>
                    <p className="text-xs text-slate-500">{h.grader} · Score {h.score != null ? h.score : "—"}</p>
                    {h.feedback && <p className="mt-1 text-xs text-slate-600">{h.feedback}</p>}
                  </div>
                ))}
              </div>
            )}
          </Card>

          {attempt.feedback && (
            <Card title="Latest Feedback">
              <p className="text-sm text-slate-600">{attempt.feedback}</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyState({ icon, title }: { icon: any; title: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
        {icon}
      </div>
      <p className="text-sm text-slate-500">{title}</p>
    </div>
  );
}