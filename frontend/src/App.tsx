import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { PORTAL_HOME, useAuth } from "./lib/auth";
import { PageLoader } from "./components/ui";

import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import ForgotPasswordPage from "./pages/auth/ForgotPasswordPage";
import ResetPasswordPage from "./pages/auth/ResetPasswordPage";

import NotificationsPage from "./pages/common/NotificationsPage";
import RequestsPage from "./pages/common/RequestsPage";
import ProfilePage from "./pages/common/ProfilePage";

import StudentDashboard from "./pages/student/Dashboard";
import LearningPathPage from "./pages/student/LearningPath";
import LearningDayPage from "./pages/student/LearningDay";
import StudentAssessments from "./pages/student/Assessments";
import TakeAssessment from "./pages/student/TakeAssessment";
import StudentTasks from "./pages/student/Tasks";
import MyDomains from "./pages/student/MyDomains";
import StudentPoints from "./pages/student/Points";
import Leaderboard from "./pages/student/Leaderboard";
import MyAppeals from "./pages/student/Appeals";

import CoordinatorDashboard from "./pages/coordinator/Dashboard";
import ContentBuilder from "./pages/coordinator/ContentBuilder";
import AssessmentBuilder from "./pages/coordinator/AssessmentBuilder";
import CoordinatorSubmissions from "./pages/coordinator/Submissions";
import SubmissionDetail from "./pages/coordinator/SubmissionDetail";
import CoordinatorStudents from "./pages/coordinator/Students";
import CoordinatorAnalytics from "./pages/coordinator/Analytics";

import FacultyDashboard from "./pages/faculty/Dashboard";
import GradingQueue from "./pages/faculty/GradingQueue";
import TaskEvidenceQueue from "./pages/faculty/TaskEvidence";
import AppealsQueue from "./pages/faculty/Appeals";
import PointAdjustments from "./pages/faculty/PointAdjustments";
import FacultyAnalytics from "./pages/faculty/Analytics";

import AdminDashboard from "./pages/admin/Dashboard";
import AdminUsers from "./pages/admin/Users";
import AdminDomains from "./pages/admin/Domains";
import AdminContent from "./pages/admin/Content";
import AdminAssessments from "./pages/admin/Assessments";
import AdminTasks from "./pages/admin/Tasks";
import AdminAnnouncements from "./pages/admin/Announcements";
import AdminSettings from "./pages/admin/Settings";
import AdminAudit from "./pages/admin/Audit";

function RoleHome() {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={PORTAL_HOME[user.role]} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RoleHome />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      <Route element={<ProtectedRoute roles={["student", "coordinator", "faculty", "admin"]}><AppShell /></ProtectedRoute>}>
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/requests" element={<RequestsPage />} />
        <Route path="/profile" element={<ProfilePage />} />

        <Route path="/student" element={<ProtectedRoute roles={["student"]}><StudentDashboard /></ProtectedRoute>} />
        <Route path="/student/learning" element={<ProtectedRoute roles={["student"]}><LearningPathPage /></ProtectedRoute>} />
        <Route path="/student/learning/:dayId" element={<ProtectedRoute roles={["student"]}><LearningDayPage /></ProtectedRoute>} />
        <Route path="/student/assessments" element={<ProtectedRoute roles={["student"]}><StudentAssessments /></ProtectedRoute>} />
        <Route path="/student/assessments/:attemptId/take" element={<ProtectedRoute roles={["student"]}><TakeAssessment /></ProtectedRoute>} />
        <Route path="/student/tasks" element={<ProtectedRoute roles={["student"]}><StudentTasks /></ProtectedRoute>} />
        <Route path="/student/domains" element={<ProtectedRoute roles={["student"]}><MyDomains /></ProtectedRoute>} />
        <Route path="/student/points" element={<ProtectedRoute roles={["student"]}><StudentPoints /></ProtectedRoute>} />
        <Route path="/student/leaderboard" element={<ProtectedRoute roles={["student"]}><Leaderboard /></ProtectedRoute>} />
        <Route path="/student/appeals" element={<ProtectedRoute roles={["student"]}><MyAppeals /></ProtectedRoute>} />

        <Route path="/coordinator" element={<ProtectedRoute roles={["coordinator", "admin"]}><CoordinatorDashboard /></ProtectedRoute>} />
        <Route path="/coordinator/content" element={<ProtectedRoute roles={["coordinator", "admin"]}><ContentBuilder /></ProtectedRoute>} />
        <Route path="/coordinator/assessments" element={<ProtectedRoute roles={["coordinator", "admin"]}><AssessmentBuilder /></ProtectedRoute>} />
        <Route path="/coordinator/submissions" element={<ProtectedRoute roles={["coordinator", "faculty", "admin"]}><CoordinatorSubmissions /></ProtectedRoute>} />
        <Route path="/coordinator/submissions/:attemptId" element={<ProtectedRoute roles={["coordinator", "faculty", "admin"]}><SubmissionDetail /></ProtectedRoute>} />
        <Route path="/coordinator/students" element={<ProtectedRoute roles={["coordinator", "faculty", "admin"]}><CoordinatorStudents /></ProtectedRoute>} />
        <Route path="/coordinator/analytics" element={<ProtectedRoute roles={["coordinator", "faculty", "admin"]}><CoordinatorAnalytics /></ProtectedRoute>} />

        <Route path="/faculty" element={<ProtectedRoute roles={["faculty", "admin"]}><FacultyDashboard /></ProtectedRoute>} />
        <Route path="/faculty/grading" element={<ProtectedRoute roles={["faculty", "coordinator", "admin"]}><GradingQueue /></ProtectedRoute>} />
        <Route path="/faculty/evidence" element={<ProtectedRoute roles={["faculty", "coordinator", "admin"]}><TaskEvidenceQueue /></ProtectedRoute>} />
        <Route path="/faculty/appeals" element={<ProtectedRoute roles={["faculty", "admin"]}><AppealsQueue /></ProtectedRoute>} />
        <Route path="/faculty/adjustments" element={<ProtectedRoute roles={["faculty", "admin"]}><PointAdjustments /></ProtectedRoute>} />
        <Route path="/faculty/analytics" element={<ProtectedRoute roles={["faculty", "coordinator", "admin"]}><FacultyAnalytics /></ProtectedRoute>} />

        <Route path="/admin" element={<ProtectedRoute roles={["admin"]}><AdminDashboard /></ProtectedRoute>} />
        <Route path="/admin/users" element={<ProtectedRoute roles={["admin"]}><AdminUsers /></ProtectedRoute>} />
        <Route path="/admin/domains" element={<ProtectedRoute roles={["admin"]}><AdminDomains /></ProtectedRoute>} />
        <Route path="/admin/content" element={<ProtectedRoute roles={["admin"]}><AdminContent /></ProtectedRoute>} />
        <Route path="/admin/assessments" element={<ProtectedRoute roles={["admin"]}><AdminAssessments /></ProtectedRoute>} />
        <Route path="/admin/tasks" element={<ProtectedRoute roles={["admin"]}><AdminTasks /></ProtectedRoute>} />
        <Route path="/admin/announcements" element={<ProtectedRoute roles={["admin"]}><AdminAnnouncements /></ProtectedRoute>} />
        <Route path="/admin/settings" element={<ProtectedRoute roles={["admin"]}><AdminSettings /></ProtectedRoute>} />
        <Route path="/admin/audit" element={<ProtectedRoute roles={["admin"]}><AdminAudit /></ProtectedRoute>} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
