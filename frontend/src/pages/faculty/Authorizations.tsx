import { useState } from "react";
import {
  CheckCircle2,
  Clock,
  KeyRound,
  Lock,
  Plus,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  Unlock,
  UserCheck,
} from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import { formatDateTime, humanize } from "../../lib/format";
import { Badge, Card, EmptyState, Field, Modal, PageHeader, PageLoader, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";

export default function FacultyAuthorizations() {
  const { data: assessments, loading: loadingAssessments, reload: reloadAssessments } = useApi<any[]>("/faculty/assessments");
  const { data: authorizations, loading: loadingAuths, reload: reloadAuths } = useApi<any[]>("/faculty/authorizations");
  const { data: students } = useApi<any[]>("/coordinator/students/progress");
  const { push } = useToast();

  const [unlockModal, setUnlockModal] = useState<any | null>(null);
  const [proctorModal, setProctorModal] = useState<any | null>(null);
  const [studentId, setStudentId] = useState<string>("");
  const [reason, setReason] = useState<string>("");
  const [extraAttempts, setExtraAttempts] = useState<number>(1);
  const [validMinutes, setValidMinutes] = useState<number>(120);
  const [busy, setBusy] = useState(false);

  async function handleAuthorizeStudent() {
    if (!unlockModal || !studentId) {
      push("Please select an assessment and student.", "error");
      return;
    }
    setBusy(true);
    try {
      await api.post(`/faculty/assessments/${unlockModal.id}/authorize-student`, {
        student_id: Number(studentId),
        reason: reason || "Faculty authorized re-attempt / window override",
        extra_attempts: Number(extraAttempts),
        valid_minutes: Number(validMinutes),
      });
      push("Student authorized successfully.", "success");
      setUnlockModal(null);
      setStudentId("");
      setReason("");
      reloadAuths();
      reloadAssessments();
    } catch (e: any) {
      push(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleOpenProctor() {
    if (!proctorModal) return;
    setBusy(true);
    try {
      await api.post(`/faculty/assessments/${proctorModal.id}/open-proctor`, {
        reason: reason || "Proctor in-person session unlocked",
        valid_minutes: Number(validMinutes),
      });
      push("Assessment opened for proctored session.", "success");
      setProctorModal(null);
      setReason("");
      reloadAuths();
      reloadAssessments();
    } catch (e: any) {
      push(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke(authId: number) {
    try {
      await api.delete(`/faculty/authorizations/${authId}`);
      push("Authorization revoked.", "info");
      reloadAuths();
    } catch (e: any) {
      push(e.message, "error");
    }
  }

  const assessmentList = assessments || [];
  const authList = authorizations || [];
  const studentOptions = students || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Assessment Authorization Desk"
        subtitle="Manage student-specific unlocks, emergency re-attempts, and proctored session activations."
      />

      {/* Active Authorizations Table */}
      <Card title="Active Authorizations & Overrides" subtitle="Current single-student overrides and proctor-activated sessions" pad={false}>
        {loadingAuths ? (
          <div className="p-8"><PageLoader label="Loading authorizations..." /></div>
        ) : !authList.filter((a) => a.is_active).length ? (
          <EmptyState
            icon={<ShieldCheck className="h-6 w-6" />}
            title="No active authorizations"
            description="Use the assessment list below to grant single-student unlocks or open proctored sessions."
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Assessment</th>
                  <th>Student Target</th>
                  <th>Authorization Type</th>
                  <th>Extra Attempts</th>
                  <th>Valid Until</th>
                  <th>Authorized By</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {authList
                  .filter((a) => a.is_active)
                  .map((a: any) => (
                    <tr key={a.id}>
                      <td className="font-semibold text-slate-800 text-xs">
                        {a.assessment_title}
                      </td>
                      <td>
                        <p className="font-medium text-slate-800 text-xs">{a.student_name}</p>
                        {a.student_register_number && (
                          <p className="text-[11px] text-slate-400">{a.student_register_number}</p>
                        )}
                      </td>
                      <td>
                        <Badge tone={a.authorization_type === "proctor_open" ? "violet" : "blue"}>
                          {humanize(a.authorization_type)}
                        </Badge>
                      </td>
                      <td className="text-xs font-semibold text-slate-700">
                        {a.extra_attempts > 0 ? `+${a.extra_attempts}` : "Standard"}
                      </td>
                      <td className="text-xs text-slate-500">
                        {a.valid_until ? formatDateTime(a.valid_until) : "No expiration"}
                      </td>
                      <td className="text-xs text-slate-600">{a.authorizer_name}</td>
                      <td>
                        <button
                          className="btn-danger !py-1 !px-2 text-xs"
                          onClick={() => handleRevoke(a.id)}
                        >
                          Revoke
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Assessment Controls Table */}
      <Card title="Assessments in Scope" subtitle="Select an assessment to grant single-student unlocks or open a live proctor session" pad={false}>
        {loadingAssessments ? (
          <div className="p-8"><PageLoader label="Loading assessments..." /></div>
        ) : !assessmentList.length ? (
          <EmptyState title="No assessments found" description="No assessments currently exist in your scope." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Assessment</th>
                  <th>Domain</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Schedule Window (IST)</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {assessmentList.map((a: any) => (
                  <tr key={a.id}>
                    <td>
                      <p className="font-semibold text-slate-800 text-xs">{a.title}</p>
                      <p className="text-[11px] text-slate-400">{a.question_count} questions · {a.total_marks} marks</p>
                    </td>
                    <td className="text-xs text-slate-600">{a.domain}</td>
                    <td>
                      <Badge tone={a.assessment_type === "betting" ? "violet" : a.assessment_type === "coding" ? "blue" : "green"}>
                        {humanize(a.assessment_type)}
                      </Badge>
                    </td>
                    <td>
                      <StatusBadge status={a.status} />
                    </td>
                    <td className="text-xs text-slate-500">
                      {a.scheduled_start ? `${formatDateTime(a.scheduled_start)} → ` : "Anytime → "}
                      {a.scheduled_end ? formatDateTime(a.scheduled_end) : "Indefinite"}
                    </td>
                    <td className="text-right space-x-2">
                      <button
                        className="btn-secondary !py-1 !px-2.5 text-xs inline-flex items-center gap-1"
                        onClick={() => {
                          setUnlockModal(a);
                          setReason("");
                          setExtraAttempts(1);
                        }}
                      >
                        <UserCheck className="h-3.5 w-3.5 text-brand-600" /> Unlock Student
                      </button>
                      <button
                        className="btn-primary !py-1 !px-2.5 text-xs inline-flex items-center gap-1"
                        onClick={() => {
                          setProctorModal(a);
                          setReason("");
                        }}
                      >
                        <Unlock className="h-3.5 w-3.5" /> Open Proctor
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Unlock Student Modal */}
      <Modal
        open={!!unlockModal}
        onClose={() => setUnlockModal(null)}
        title="Authorize Single-Student Unlock"
        subtitle={unlockModal ? `${unlockModal.title} (${unlockModal.domain})` : ""}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setUnlockModal(null)}>Cancel</button>
            <button className="btn-primary" onClick={handleAuthorizeStudent} disabled={busy || !studentId}>
              Grant Authorization
            </button>
          </>
        }
      >
        <div className="space-y-4 text-sm text-slate-600">
          <Field label="Select Student *">
            <select
              className="input text-xs"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
            >
              <option value="">Select a student...</option>
              {studentOptions.map((s: any) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.register_number || s.email}) - {s.department || "General"}
                </option>
              ))}
            </select>
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Extra Allowed Attempts">
              <input
                type="number"
                min="1"
                max="5"
                className="input text-xs"
                value={extraAttempts}
                onChange={(e) => setExtraAttempts(Number(e.target.value))}
              />
            </Field>

            <Field label="Valid Window (minutes)">
              <input
                type="number"
                min="1"
                max="1440"
                className="input text-xs"
                value={validMinutes}
                onChange={(e) => setValidMinutes(Number(e.target.value))}
              />
            </Field>
          </div>

          <Field label="Reason / Justification">
            <textarea
              className="input min-h-[60px] text-xs"
              placeholder="e.g. Student reported browser crash or network interruption during scheduled window."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
        </div>
      </Modal>

      {/* Open Proctor Modal */}
      <Modal
        open={!!proctorModal}
        onClose={() => setProctorModal(null)}
        title="Open Assessment for Proctored Session"
        subtitle={proctorModal ? `${proctorModal.title} (${proctorModal.domain})` : ""}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setProctorModal(null)}>Cancel</button>
            <button className="btn-primary" onClick={handleOpenProctor} disabled={busy}>
              Activate Proctor Session
            </button>
          </>
        }
      >
        <div className="space-y-4 text-sm text-slate-600">
          <p className="text-xs text-slate-600">
            This will immediately publish and unlock this assessment for all enrolled students for the specified duration,
            bypassing standard closed or future schedule constraints for an in-person or live supervised session.
          </p>

          <Field label="Active Session Duration (minutes)">
            <input
              type="number"
              min="15"
              max="480"
              className="input text-xs"
              value={validMinutes}
              onChange={(e) => setValidMinutes(Number(e.target.value))}
            />
          </Field>

          <Field label="Session Remarks">
            <textarea
              className="input min-h-[60px] text-xs"
              placeholder="e.g. Lab 3 In-Person Betting Assessment Session."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
        </div>
      </Modal>
    </div>
  );
}
