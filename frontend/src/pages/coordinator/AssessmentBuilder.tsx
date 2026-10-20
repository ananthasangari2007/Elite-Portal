import { useState, useEffect } from "react";
import { Plus, Trash2, UploadCloud } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { Card, EmptyState, Field, Modal, PageHeader, PageLoader, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { humanize } from "../../lib/format";

export default function AssessmentBuilder() {
  const { push } = useToast();
  const { data: domains } = useApi<any[]>("/coordinator/domains");
  const [domainId, setDomainId] = useState<string>("");
  const [assessments, setAssessments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({
    title: "", assessment_type: "mcq", description: "", learning_day_id: "", time_limit_minutes: "", max_attempts: 1,
    shuffle_options: true, shuffle_questions: true, show_results_after: "immediate", show_correct_answers: true,
    scheduled_start: "", scheduled_end: "", instructions: "", total_marks: ""
  });
  const [questions, setQuestions] = useState<any[]>([]);
  const [days, setDays] = useState<any[]>([]);

  useEffect(() => {
    if (domains?.length && !domainId) setDomainId(String(domains[0].id));
  }, [domains]);

  useEffect(() => {
    if (!domainId) return;
    loadAssessments();
    loadDays();
  }, [domainId]);

  async function loadAssessments() {
    setLoading(true);
    try {
      const res = await api.get<any[]>(`/coordinator/domains/${domainId}/assessments`);
      setAssessments(res || []);
    } finally {
      setLoading(false);
    }
  }

  async function loadDays() {
    try {
      const res = await api.get<any>(`/coordinator/domains/${domainId}/days`);
      setDays(res.days || []);
    } catch (e) {
      setDays([]);
    }
  }

  function addQuestion() {
    setQuestions([...questions, {
      question_type: "mcq",
      question_text: "",
      marks: 1,
      explanation: "",
      options: [{ option_text: "", is_correct: false }, { option_text: "", is_correct: false }],
      coding: { constraints: "", sample_input: "", sample_output: "", test_cases: [] }
    }]);
  }

  function removeQuestion(i: number) {
    const q = [...questions]; q.splice(i, 1); setQuestions(q);
  }

  function addOption(i: number) {
    const q = [...questions];
    q[i].options.push({ option_text: "", is_correct: false });
    setQuestions(q);
  }

  function setCorrect(i: number, optIdx: number) {
    const q = [...questions];
    q[i].options = q[i].options.map((o: any, oi: number) => ({ ...o, is_correct: oi === optIdx }));
    setQuestions(q);
  }

  function addTestCase(i: number) {
    const q = [...questions];
    q[i].coding.test_cases.push({ input_data: "", expected_output: "", points: q[i].marks || 1, is_sample: false });
    setQuestions(q);
  }

  async function saveAssessment() {
    try {
      const payload = {
        ...form,
        domain_id: Number(domainId),
        time_limit_minutes: form.time_limit_minutes ? Number(form.time_limit_minutes) : null,
        max_attempts: Number(form.max_attempts),
        learning_day_id: form.learning_day_id ? Number(form.learning_day_id) : null,
        total_marks: form.total_marks ? Number(form.total_marks) : undefined,
        questions: questions.map((q) => ({
          question_type: q.question_type,
          question_text: q.question_text,
          marks: Number(q.marks || 0),
          explanation: q.explanation,
          options: q.question_type === "mcq" ? q.options : undefined,
          coding: q.question_type === "coding" ? q.coding : undefined
        }))
      };
      await api.post("/coordinator/assessments", payload);
      setShowModal(false);
      setForm({
        title: "", assessment_type: "mcq", description: "", learning_day_id: "", time_limit_minutes: "", max_attempts: 1,
        shuffle_options: true, shuffle_questions: true, show_results_after: "immediate", show_correct_answers: true,
        scheduled_start: "", scheduled_end: "", instructions: "", total_marks: ""
      });
      setQuestions([]);
      loadAssessments();
      push("Assessment created", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  async function publish(id: number) {
    try {
      await api.post(`/coordinator/assessments/${id}/publish`);
      loadAssessments();
      push("Assessment published", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  async function close(id: number) {
    try {
      await api.post(`/coordinator/assessments/${id}/close`);
      loadAssessments();
      push("Assessment closed", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  return (
    <div>
      <PageHeader
        title="Assessment Builder"
        subtitle="Create MCQ, Betting and Coding assessments"
        actions={
          <button className="btn-primary" onClick={() => setShowModal(true)}>
            <Plus className="h-4 w-4" /> New Assessment
          </button>
        }
      />

      <Card className="mb-4">
        <Field label="Select Domain">
          <select className="input" value={domainId} onChange={(e) => setDomainId(e.target.value)}>
            {domains?.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </Field>
      </Card>

      {loading ? (
        <PageLoader />
      ) : !assessments.length ? (
        <Card><EmptyState title="No assessments yet" /></Card>
      ) : (
        <div className="space-y-3">
          {assessments.map((a) => (
            <Card key={a.id}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-800">{a.title}</p>
                  <p className="text-xs text-slate-500">{humanize(a.assessment_type)} · {a.question_count} questions · {a.total_marks} marks</p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={a.status} />
                  {a.status === "draft" && <button className="btn-primary !px-2.5 !py-1.5" onClick={() => publish(a.id)}>Publish</button>}
                  {a.status === "published" && <button className="btn-secondary !px-2.5 !py-1.5" onClick={() => close(a.id)}>Close</button>}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={showModal} onClose={() => setShowModal(false)} title="New Assessment" size="xl" footer={
        <>
          <button className="btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
          <button className="btn-primary" onClick={saveAssessment}>Save</button>
        </>
      }>
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Title"><input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
            <Field label="Type">
              <select className="input" value={form.assessment_type} onChange={(e) => setForm({ ...form, assessment_type: e.target.value })}>
                <option value="mcq">MCQ</option>
                <option value="betting">Betting</option>
                <option value="coding">Coding</option>
              </select>
            </Field>
            <Field label="Learning Day">
              <select className="input" value={form.learning_day_id} onChange={(e) => setForm({ ...form, learning_day_id: e.target.value })}>
                <option value="">None</option>
                {days.map((d) => (
                  <option key={d.id} value={d.id}>Day {d.day_number}: {d.title}</option>
                ))}
              </select>
            </Field>
            <Field label="Time Limit (min)"><input type="number" className="input" value={form.time_limit_minutes} onChange={(e) => setForm({ ...form, time_limit_minutes: e.target.value })} /></Field>
            <Field label="Max Attempts"><input type="number" className="input" value={form.max_attempts} onChange={(e) => setForm({ ...form, max_attempts: Number(e.target.value) })} /></Field>
            <Field label="Total Marks"><input type="number" className="input" value={form.total_marks} onChange={(e) => setForm({ ...form, total_marks: e.target.value })} /></Field>
          </div>
          <Field label="Description"><textarea className="input min-h-[60px]" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <Field label="Instructions"><textarea className="input min-h-[60px]" value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} /></Field>

          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-slate-800">Questions</p>
            <button className="btn-secondary !px-2.5 !py-1.5" onClick={addQuestion}><Plus className="h-3.5 w-3.5" /> Add Question</button>
          </div>

          {questions.map((q, i) => (
            <div key={i} className="rounded-xl border border-slate-200 p-4">
              <div className="flex items-center justify-between">
                <select className="input w-40" value={q.question_type} onChange={(e) => { const nq = [...questions]; nq[i].question_type = e.target.value; setQuestions(nq); }}>
                  <option value="mcq">MCQ</option>
                  <option value="coding">Coding</option>
                </select>
                <div className="flex items-center gap-2">
                  <input type="number" className="input w-20" value={q.marks} onChange={(e) => { const nq = [...questions]; nq[i].marks = Number(e.target.value); setQuestions(nq); }} />
                  <button className="btn-danger !px-2.5 !py-1.5" onClick={() => removeQuestion(i)}><Trash2 className="h-4 w-4" /></button>
                </div>
              </div>
              <textarea className="input mt-2 min-h-[60px]" value={q.question_text} onChange={(e) => { const nq = [...questions]; nq[i].question_text = e.target.value; setQuestions(nq); }} placeholder="Question text" />
              {q.question_type === "mcq" && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs font-semibold text-slate-500">Options</p>
                  {q.options.map((o: any, oi: number) => (
                    <div key={oi} className="flex items-center gap-2">
                      <input type="radio" checked={o.is_correct} onChange={() => setCorrect(i, oi)} />
                      <input className="input flex-1" value={o.option_text} onChange={(e) => { const nq = [...questions]; nq[i].options[oi].option_text = e.target.value; setQuestions(nq); }} placeholder={`Option ${oi + 1}`} />
                    </div>
                  ))}
                  <button className="btn-secondary !px-2.5 !py-1.5" onClick={() => addOption(i)}>Add Option</button>
                </div>
              )}
              {q.question_type === "coding" && (
                <div className="mt-3 space-y-2">
                  <Field label="Constraints"><textarea className="input min-h-[50px]" value={q.coding.constraints} onChange={(e) => { const nq = [...questions]; nq[i].coding.constraints = e.target.value; setQuestions(nq); }} /></Field>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Field label="Sample Input"><textarea className="input min-h-[50px]" value={q.coding.sample_input} onChange={(e) => { const nq = [...questions]; nq[i].coding.sample_input = e.target.value; setQuestions(nq); }} /></Field>
                    <Field label="Sample Output"><textarea className="input min-h-[50px]" value={q.coding.sample_output} onChange={(e) => { const nq = [...questions]; nq[i].coding.sample_output = e.target.value; setQuestions(nq); }} /></Field>
                  </div>
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-slate-500">Test Cases</p>
                    <button className="btn-secondary !px-2.5 !py-1.5" onClick={() => addTestCase(i)}>Add Test Case</button>
                  </div>
                  {q.coding.test_cases.map((tc: any, ti: number) => (
                    <div key={ti} className="grid gap-2 rounded-lg bg-slate-50 p-2 sm:grid-cols-2">
                      <textarea className="input min-h-[40px]" value={tc.input_data} onChange={(e) => { const nq = [...questions]; nq[i].coding.test_cases[ti].input_data = e.target.value; setQuestions(nq); }} placeholder="Input" />
                      <textarea className="input min-h-[40px]" value={tc.expected_output} onChange={(e) => { const nq = [...questions]; nq[i].coding.test_cases[ti].expected_output = e.target.value; setQuestions(nq); }} placeholder="Expected Output" />
                    </div>
                  ))}
                </div>
              )}
              <Field label="Explanation"><textarea className="input min-h-[50px]" value={q.explanation} onChange={(e) => { const nq = [...questions]; nq[i].explanation = e.target.value; setQuestions(nq); }} /></Field>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
}