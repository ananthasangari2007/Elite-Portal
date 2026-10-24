import { useState, useEffect } from "react";
import { Calendar, Clock, Code2, Globe, Lock, Plus, Sparkles, Trash2, Trophy, UploadCloud } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { Card, EmptyState, Field, Modal, PageHeader, PageLoader, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { formatDateTime, humanize } from "../../lib/format";

export const ALL_COMPILER_LANGUAGES = [
  { id: "cpp", label: "C++ (G++)" },
  { id: "java", label: "Java (JDK 17)" },
  { id: "python3", label: "Python3 (3.14)" },
  { id: "python", label: "Python" },
  { id: "javascript", label: "JavaScript (Node)" },
  { id: "typescript", label: "TypeScript (Node)" },
  { id: "csharp", label: "C#" },
  { id: "c", label: "C (GCC)" },
  { id: "go", label: "Go" },
  { id: "kotlin", label: "Kotlin" },
  { id: "swift", label: "Swift" },
  { id: "rust", label: "Rust" },
  { id: "ruby", label: "Ruby" },
  { id: "php", label: "PHP" },
  { id: "dart", label: "Dart" },
  { id: "scala", label: "Scala" },
  { id: "elixir", label: "Elixir" },
  { id: "erlang", label: "Erlang" },
  { id: "racket", label: "Racket" },
  { id: "web", label: "HTML / CSS / JS (Web Sandbox)" },
];

export default function AssessmentBuilder() {
  const { push } = useToast();
  const { data: domains } = useApi<any[]>("/coordinator/domains");
  const [domainId, setDomainId] = useState<string>("");
  const [assessments, setAssessments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [batchCount, setBatchCount] = useState<number>(5);
  const [form, setForm] = useState({
    title: "",
    mode: "scheduled", // scheduled | daily | betting
    assessment_type: "mcq", // mcq | coding | betting
    grading_mode: "automatic", // automatic | manual
    attendance_points: 5,
    description: "",
    learning_day_id: "",
    time_limit_minutes: "30",
    max_attempts: 1,
    shuffle_options: true,
    shuffle_questions: true,
    show_results_after: "submission",
    show_correct_answers: true,
    scheduled_start: "",
    scheduled_end: "",
    instructions: "",
    total_marks: "",
    allowed_languages: ALL_COMPILER_LANGUAGES.map((l) => l.id),
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
      const res = await api.get<any>(`/coordinator/domains/${domainId}/assessments`);
      setAssessments(res.assessments || res || []);
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

  function addQuestion(type: string = "mcq") {
    setQuestions([
      ...questions,
      {
        question_type: type,
        question_text: "",
        marks: 1,
        explanation: "",
        options: [
          { option_text: "", is_correct: true },
          { option_text: "", is_correct: false },
          { option_text: "", is_correct: false },
          { option_text: "", is_correct: false },
        ],
        coding: { constraints: "", sample_input: "", sample_output: "", test_cases: [] },
      },
    ]);
  }

  function generateBatchQuestions() {
    const count = Math.max(1, Math.min(batchCount, 50));
    const newQs: any[] = [];
    for (let i = 1; i <= count; i++) {
      newQs.push({
        question_type: form.assessment_type === "coding" ? "coding" : "mcq",
        question_text: `Question ${questions.length + i}`,
        marks: 1,
        explanation: "",
        options: [
          { option_text: "Option A", is_correct: true },
          { option_text: "Option B", is_correct: false },
          { option_text: "Option C", is_correct: false },
          { option_text: "Option D", is_correct: false },
        ],
        coding: { constraints: "", sample_input: "", sample_output: "", test_cases: [] },
      });
    }
    setQuestions([...questions, ...newQs]);
    push(`Added ${count} question slot(s).`, "info");
  }

  function removeQuestion(i: number) {
    const q = [...questions];
    q.splice(i, 1);
    setQuestions(q);
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
    q[i].coding.test_cases.push({
      input_data: "",
      expected_output: "",
      points: q[i].marks || 1,
      is_sample: false,
    });
    setQuestions(q);
  }

  async function saveAssessment() {
    try {
      const actualType = form.mode === "betting" ? "betting" : form.assessment_type;
      const payload = {
        title: form.title,
        assessment_type: actualType,
        description: form.description,
        domain_id: Number(domainId),
        learning_day_id: form.learning_day_id ? Number(form.learning_day_id) : null,
        grading_mode: form.grading_mode,
        attendance_points: Number(form.attendance_points || 0),
        allowed_languages: form.assessment_type === "coding" ? form.allowed_languages : [],
        time_limit_minutes: form.time_limit_minutes ? Number(form.time_limit_minutes) : null,
        max_attempts: Number(form.max_attempts),
        total_marks: form.total_marks ? Number(form.total_marks) : undefined,
        shuffle_options: form.shuffle_options,
        shuffle_questions: form.shuffle_questions,
        show_results_after: form.show_results_after,
        show_correct_answers: form.show_correct_answers,
        instructions: form.instructions,
        status: form.mode === "scheduled" && form.scheduled_start ? "scheduled" : "published",
        scheduled_start: form.scheduled_start ? new Date(form.scheduled_start).toISOString() : null,
        scheduled_end: form.scheduled_end ? new Date(form.scheduled_end).toISOString() : null,
        questions: questions.map((q) => ({
          question_type: q.question_type,
          question_text: q.question_text,
          marks: Number(q.marks || 0),
          explanation: q.explanation,
          options: q.question_type === "mcq" ? q.options : undefined,
          coding: q.question_type === "coding" ? q.coding : undefined,
        })),
      };

      await api.post("/coordinator/assessments", payload);
      setShowModal(false);
      setForm({
        title: "",
        mode: "scheduled",
        assessment_type: "mcq",
        grading_mode: "automatic",
        attendance_points: 5,
        description: "",
        learning_day_id: "",
        time_limit_minutes: "30",
        max_attempts: 1,
        shuffle_options: true,
        shuffle_questions: true,
        show_results_after: "submission",
        show_correct_answers: true,
        scheduled_start: "",
        scheduled_end: "",
        instructions: "",
        total_marks: "",
        allowed_languages: ALL_COMPILER_LANGUAGES.map((l) => l.id),
      });
      setQuestions([]);
      loadAssessments();
      push("Assessment created and published successfully.", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  async function publish(id: number) {
    try {
      await api.post(`/coordinator/assessments/${id}/publish`);
      loadAssessments();
      push("Assessment published.", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  async function close(id: number) {
    try {
      await api.post(`/coordinator/assessments/${id}/close`);
      loadAssessments();
      push("Assessment closed.", "success");
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  const isSingleDomain = domains && domains.length === 1;

  return (
    <div>
      <PageHeader
        title="Assessment Builder"
        subtitle="Author scheduled, daily, betting and coding assessments with proctored delivery."
        actions={
          <button className="btn-primary" onClick={() => setShowModal(true)}>
            <Plus className="h-4 w-4" /> New Assessment
          </button>
        }
      />

      {/* Domain Isolation Banner / Selector */}
      <Card className="mb-4 p-4">
        {isSingleDomain ? (
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 text-slate-700">
              <Lock className="h-4 w-4 text-brand-600" />
              <span>
                Assigned Domain: <strong>{domains[0].name}</strong> ({domains[0].code})
              </span>
            </div>
            <span className="badge-slate text-xs">Single Domain Isolation Active</span>
          </div>
        ) : (
          <Field label="Domain">
            <select
              className="input"
              value={domainId}
              onChange={(e) => setDomainId(e.target.value)}
            >
              {domains?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.code})
                </option>
              ))}
            </select>
          </Field>
        )}
      </Card>

      {loading ? (
        <PageLoader />
      ) : !assessments.length ? (
        <Card>
          <EmptyState
            title="No assessments yet"
            description="Create your first MCQ, coding, or betting assessment for this domain."
            action={
              <button className="btn-primary" onClick={() => setShowModal(true)}>
                <Plus className="h-4 w-4" /> Create Assessment
              </button>
            }
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {assessments.map((a) => (
            <Card key={a.id} className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-slate-800">{a.title}</p>
                    <StatusBadge status={a.status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {humanize(a.assessment_type)} · {a.question_count} question(s) · {a.total_marks} marks
                    {a.time_limit_minutes ? ` · ${a.time_limit_minutes} min` : ""}
                  </p>
                  {(a.scheduled_start || a.scheduled_end) && (
                    <p className="mt-1 text-xs text-brand-600">
                      Window: {a.scheduled_start ? formatDateTime(a.scheduled_start) : "Anytime"} →{" "}
                      {a.scheduled_end ? formatDateTime(a.scheduled_end) : "Indefinite"} (IST)
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {a.status === "draft" && (
                    <button className="btn-primary !px-2.5 !py-1 text-xs" onClick={() => publish(a.id)}>
                      Publish
                    </button>
                  )}
                  {a.status === "published" && (
                    <button className="btn-secondary !px-2.5 !py-1 text-xs" onClick={() => close(a.id)}>
                      Close
                    </button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Assessment Creator Modal */}
      <Modal
        open={showModal}
        onClose={() => setShowModal(false)}
        title="Create New Assessment"
        size="xl"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setShowModal(false)}>
              Cancel
            </button>
            <button className="btn-primary" onClick={saveAssessment} disabled={!form.title.trim()}>
              Save & Release Assessment
            </button>
          </>
        }
      >
        <div className="space-y-5 text-sm">
          {/* Mode Selector */}
          <div>
            <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider block mb-2">
              Assessment Mode
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setForm({ ...form, mode: "scheduled", assessment_type: "mcq" })}
                className={`p-3 rounded-xl border text-left transition ${
                  form.mode === "scheduled"
                    ? "border-brand-500 bg-brand-50/70 ring-1 ring-brand-500"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center gap-2 font-semibold text-slate-800 text-xs">
                  <Calendar className="h-4 w-4 text-brand-600" /> Scheduled Mode
                </div>
                <p className="text-[11px] text-slate-500 mt-1">Specific test window with start/end time</p>
              </button>

              <button
                type="button"
                onClick={() => setForm({ ...form, mode: "daily", assessment_type: "mcq" })}
                className={`p-3 rounded-xl border text-left transition ${
                  form.mode === "daily"
                    ? "border-brand-500 bg-brand-50/70 ring-1 ring-brand-500"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center gap-2 font-semibold text-slate-800 text-xs">
                  <Clock className="h-4 w-4 text-emerald-600" /> Daily Quiz Mode
                </div>
                <p className="text-[11px] text-slate-500 mt-1">Linked directly to a day's curriculum</p>
              </button>

              <button
                type="button"
                onClick={() => setForm({ ...form, mode: "betting", assessment_type: "betting" })}
                className={`p-3 rounded-xl border text-left transition ${
                  form.mode === "betting"
                    ? "border-brand-500 bg-brand-50/70 ring-1 ring-brand-500"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center gap-2 font-semibold text-slate-800 text-xs">
                  <Trophy className="h-4 w-4 text-violet-600" /> Betting Mode
                </div>
                <p className="text-[11px] text-slate-500 mt-1">High-stakes point risk/reward settlement</p>
              </button>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Assessment Title *">
              <input
                className="input"
                placeholder="e.g. Trees and Graphs Milestone Test"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </Field>

            <Field label="Question Format">
              <select
                className="input"
                value={form.assessment_type}
                onChange={(e) => setForm({ ...form, assessment_type: e.target.value })}
                disabled={form.mode === "betting"}
              >
                <option value="mcq">Multiple Choice Questions (MCQ)</option>
                <option value="coding">Coding Problem (Code Runner)</option>
                <option value="betting">Betting Assessment</option>
              </select>
            </Field>

            <Field label="Linked Learning Day">
              <select
                className="input"
                value={form.learning_day_id}
                onChange={(e) => setForm({ ...form, learning_day_id: e.target.value })}
              >
                <option value="">None (Standalone)</option>
                {days.map((d) => (
                  <option key={d.id} value={d.id}>
                    Day {d.day_number}: {d.title}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Time Limit (minutes)">
              <input
                type="number"
                className="input"
                min="1"
                value={form.time_limit_minutes}
                onChange={(e) => setForm({ ...form, time_limit_minutes: e.target.value })}
              />
            </Field>

            <Field label="Max Allowed Attempts">
              <input
                type="number"
                className="input"
                min="1"
                value={form.max_attempts}
                onChange={(e) => setForm({ ...form, max_attempts: Number(e.target.value) })}
              />
            </Field>

            <Field label="Grading Mode *">
              <select
                className="input"
                value={form.grading_mode}
                onChange={(e) => setForm({ ...form, grading_mode: e.target.value })}
              >
                <option value="automatic">Automatic Grading (Instant Scoring & Points)</option>
                <option value="manual">Manual Grading (Sent to Faculty Queue)</option>
              </select>
            </Field>

            <Field label="General Attendance Points (Awarded on Attempt)">
              <input
                type="number"
                className="input"
                min="0"
                value={form.attendance_points}
                onChange={(e) => setForm({ ...form, attendance_points: Number(e.target.value) })}
                placeholder="e.g. 5"
              />
            </Field>

            <Field label="Total Marks (optional override)">
              <input
                type="number"
                className="input"
                placeholder="Auto-calculated from questions"
                value={form.total_marks}
                onChange={(e) => setForm({ ...form, total_marks: e.target.value })}
              />
            </Field>
          </div>

          {/* Allowed Compilers Selection (When Coding Assessment is Selected) */}
          {form.assessment_type === "coding" && (
            <div className="rounded-xl border border-brand-200 bg-brand-50/40 p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <Code2 className="h-4 w-4 text-brand-600" />
                    Allowed Compilers for Students ({form.allowed_languages.length} selected)
                  </label>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Select which programming language compilers students can choose from during this assessment.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, allowed_languages: ALL_COMPILER_LANGUAGES.map((l) => l.id) })}
                    className="text-xs font-semibold text-brand-600 hover:text-brand-800 underline"
                  >
                    Select All
                  </button>
                  <span className="text-slate-300">|</span>
                  <button
                    type="button"
                    onClick={() =>
                      setForm({
                        ...form,
                        allowed_languages: ["python3", "python", "cpp", "c", "java", "javascript"],
                      })
                    }
                    className="text-xs font-semibold text-brand-600 hover:text-brand-800 underline"
                  >
                    Popular (Python, C++, Java, JS, C)
                  </button>
                  <span className="text-slate-300">|</span>
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, allowed_languages: ["web"] })}
                    className="text-xs font-semibold text-brand-600 hover:text-brand-800 underline"
                  >
                    Web Only
                  </button>
                  <span className="text-slate-300">|</span>
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, allowed_languages: [] })}
                    className="text-xs font-semibold text-slate-500 hover:text-slate-700 underline"
                  >
                    Clear All
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 pt-2">
                {ALL_COMPILER_LANGUAGES.map((lang) => {
                  const isChecked = form.allowed_languages.includes(lang.id);
                  return (
                    <label
                      key={lang.id}
                      className={`flex items-center gap-2 p-2 rounded-lg border text-xs cursor-pointer transition select-none ${
                        isChecked
                          ? "border-brand-500 bg-white shadow-xs font-medium text-slate-900"
                          : "border-slate-200 bg-slate-50/60 text-slate-500 hover:bg-white"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => {
                          const updated = e.target.checked
                            ? [...form.allowed_languages, lang.id]
                            : form.allowed_languages.filter((id) => id !== lang.id);
                          setForm({ ...form, allowed_languages: updated });
                        }}
                        className="rounded border-slate-300 text-brand-600 focus:ring-brand-500 h-3.5 w-3.5"
                      />
                      <span className="truncate">{lang.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Timezone & Window Settings */}
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
              <Globe className="h-4 w-4 text-brand-600" />
              <span>Assessment Schedule Window (Timezone: Asia/Kolkata / IST UTC+05:30)</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Scheduled Start Time (IST)">
                <input
                  type="datetime-local"
                  className="input text-xs"
                  value={form.scheduled_start}
                  onChange={(e) => setForm({ ...form, scheduled_start: e.target.value })}
                />
              </Field>
              <Field label="Scheduled End Time (IST)">
                <input
                  type="datetime-local"
                  className="input text-xs"
                  value={form.scheduled_end}
                  onChange={(e) => setForm({ ...form, scheduled_end: e.target.value })}
                />
              </Field>
            </div>
          </div>

          <Field label="Student Instructions">
            <textarea
              className="input min-h-[50px] text-xs"
              placeholder="Provide test instructions, honor pledge rules, or allowable references."
              value={form.instructions}
              onChange={(e) => setForm({ ...form, instructions: e.target.value })}
            />
          </Field>

          {/* Question Generator & Palette */}
          <div className="pt-2 border-t border-slate-200">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <div>
                <p className="font-semibold text-slate-800 text-sm">
                  Questions ({questions.length})
                </p>
                <p className="text-xs text-slate-400">Total Marks: {questions.reduce((sum, q) => sum + (Number(q.marks) || 0), 0)}</p>
              </div>

              {/* Typable Question Count Generator */}
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="1"
                  max="50"
                  className="input !w-16 !py-1 text-xs text-center"
                  value={batchCount}
                  onChange={(e) => setBatchCount(Number(e.target.value))}
                />
                <button
                  type="button"
                  className="btn-secondary !py-1 !px-2 text-xs"
                  onClick={generateBatchQuestions}
                >
                  <Sparkles className="h-3.5 w-3.5 text-brand-600" /> Add {batchCount} Questions
                </button>
                <button
                  type="button"
                  className="btn-secondary !py-1 !px-2 text-xs"
                  onClick={() => addQuestion(form.assessment_type)}
                >
                  <Plus className="h-3.5 w-3.5" /> 1 Question
                </button>
              </div>
            </div>

            <div className="space-y-4 max-h-96 overflow-y-auto pr-1">
              {questions.map((q, i) => (
                <div key={i} className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-500 uppercase">
                      Question {i + 1}
                    </span>
                    <div className="flex items-center gap-2">
                      <select
                        className="input !w-32 !py-1 text-xs"
                        value={q.question_type}
                        onChange={(e) => {
                          const nq = [...questions];
                          nq[i].question_type = e.target.value;
                          setQuestions(nq);
                        }}
                      >
                        <option value="mcq">MCQ</option>
                        <option value="coding">Coding</option>
                      </select>
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-slate-400">Marks:</span>
                        <input
                          type="number"
                          min="1"
                          className="input !w-16 !py-1 text-xs"
                          value={q.marks}
                          onChange={(e) => {
                            const nq = [...questions];
                            nq[i].marks = Number(e.target.value);
                            setQuestions(nq);
                          }}
                        />
                      </div>
                      <button
                        className="btn-danger !px-2 !py-1 text-xs"
                        onClick={() => removeQuestion(i)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  <textarea
                    className="input min-h-[60px] text-xs"
                    placeholder="Enter question text here..."
                    value={q.question_text}
                    onChange={(e) => {
                      const nq = [...questions];
                      nq[i].question_text = e.target.value;
                      setQuestions(nq);
                    }}
                  />

                  {q.question_type === "mcq" && (
                    <div className="space-y-2 pt-2 border-t border-slate-100">
                      <p className="text-[11px] font-semibold text-slate-500 uppercase">
                        Answer Options (Select the correct option)
                      </p>
                      {q.options.map((o: any, oi: number) => (
                        <div key={oi} className="flex items-center gap-2">
                          <input
                            type="radio"
                            name={`correct_${i}`}
                            checked={o.is_correct}
                            onChange={() => setCorrect(i, oi)}
                            className="text-brand-600 focus:ring-brand-500"
                          />
                          <input
                            className="input flex-1 !py-1 text-xs"
                            placeholder={`Option ${String.fromCharCode(65 + oi)}`}
                            value={o.option_text}
                            onChange={(e) => {
                              const nq = [...questions];
                              nq[i].options[oi].option_text = e.target.value;
                              setQuestions(nq);
                            }}
                          />
                        </div>
                      ))}
                      <button
                        type="button"
                        className="btn-secondary !py-1 !px-2 text-xs"
                        onClick={() => addOption(i)}
                      >
                        + Add Option
                      </button>
                    </div>
                  )}

                  {q.question_type === "coding" && (
                    <div className="space-y-2 pt-2 border-t border-slate-100">
                      <Field label="Constraints">
                        <textarea
                          className="input min-h-[40px] text-xs"
                          placeholder="e.g. 1 <= N <= 10^5"
                          value={q.coding.constraints}
                          onChange={(e) => {
                            const nq = [...questions];
                            nq[i].coding.constraints = e.target.value;
                            setQuestions(nq);
                          }}
                        />
                      </Field>
                      <div className="grid gap-2 sm:grid-cols-2">
                        <Field label="Sample Input">
                          <textarea
                            className="input min-h-[40px] text-xs font-mono"
                            value={q.coding.sample_input}
                            onChange={(e) => {
                              const nq = [...questions];
                              nq[i].coding.sample_input = e.target.value;
                              setQuestions(nq);
                            }}
                          />
                        </Field>
                        <Field label="Sample Output">
                          <textarea
                            className="input min-h-[40px] text-xs font-mono"
                            value={q.coding.sample_output}
                            onChange={(e) => {
                              const nq = [...questions];
                              nq[i].coding.sample_output = e.target.value;
                              setQuestions(nq);
                            }}
                          />
                        </Field>
                      </div>
                      <div className="flex items-center justify-between pt-1">
                        <p className="text-[11px] font-semibold text-slate-500 uppercase">
                          Evaluation Test Cases
                        </p>
                        <button
                          type="button"
                          className="btn-secondary !py-1 !px-2 text-xs"
                          onClick={() => addTestCase(i)}
                        >
                          + Add Test Case
                        </button>
                      </div>
                      {q.coding.test_cases.map((tc: any, ti: number) => (
                        <div
                          key={ti}
                          className="grid gap-2 rounded-lg bg-slate-50 p-2 sm:grid-cols-2 border border-slate-200"
                        >
                          <textarea
                            className="input min-h-[35px] text-xs font-mono"
                            placeholder="Input"
                            value={tc.input_data}
                            onChange={(e) => {
                              const nq = [...questions];
                              nq[i].coding.test_cases[ti].input_data = e.target.value;
                              setQuestions(nq);
                            }}
                          />
                          <textarea
                            className="input min-h-[35px] text-xs font-mono"
                            placeholder="Expected Output"
                            value={tc.expected_output}
                            onChange={(e) => {
                              const nq = [...questions];
                              nq[i].coding.test_cases[ti].expected_output = e.target.value;
                              setQuestions(nq);
                            }}
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
