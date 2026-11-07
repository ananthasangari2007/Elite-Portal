import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { PORTAL_HOME, useAuth } from "./lib/auth";
import { PageLoader } from "./components/ui";

// Route-level code splitting using React.lazy for instant bundle loading and performance optimization
const LoginPage = lazy(() => import("./pages/auth/LoginPage"));
const RegisterPage = lazy(() => import("./pages/auth/RegisterPage"));
const ForgotPasswordPage = lazy(() => import("./pages/auth/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("./pages/auth/ResetPasswordPage"));

const NotificationsPage = lazy(() => import("./pages/common/NotificationsPage"));
const RequestsPage = lazy(() => import("./pages/common/RequestsPage"));
const ProfilePage = lazy(() => import("./pages/common/ProfilePage"));

const StudentDashboard = lazy(() => import("./pages/student/Dashboard"));
const LearningPathPage = lazy(() => import("./pages/student/LearningPath"));
const LearningDayPage = lazy(() => import("./pages/student/LearningDay"));
const StudentAssessments = lazy(() => import("./pages/student/Assessments"));
const TakeAssessment = lazy(() => import("./pages/student/TakeAssessment"));
const StudentTasks = lazy(() => import("./pages/student/Tasks"));
const MyDomains = lazy(() => import("./pages/student/MyDomains"));
const StudentPoints = lazy(() => import("./pages/student/Points"));
const Leaderboard = lazy(() => import("./pages/student/Leaderboard"));
const MyAppeals = lazy(() => import("./pages/student/Appeals"));

const CoordinatorDashboard = lazy(() => import("./pages/coordinator/Dashboard"));
const ContentBuilder = lazy(() => import("./pages/coordinator/ContentBuilder"));
const AssessmentBuilder = lazy(() => import("./pages/coordinator/AssessmentBuilder"));
const CoordinatorSubmissions = lazy(() => import("./pages/coordinator/Submissions"));
const SubmissionDetail = lazy(() => import("./pages/coordinator/SubmissionDetail"));
const CoordinatorStudents = lazy(() => import("./pages/coordinator/Students"));
const CoordinatorAnalytics = lazy(() => import("./pages/coordinator/Analytics"));

const FacultyDashboard = lazy(() => import("./pages/faculty/Dashboard"));
const GradingQueue = lazy(() => import("./pages/faculty/GradingQueue"));
const TaskEvidenceQueue = lazy(() => import("./pages/faculty/TaskEvidence"));
const AppealsQueue = lazy(() => import("./pages/faculty/Appeals"));
const PointAdjustments = lazy(() => import("./pages/faculty/PointAdjustments"));
const FacultyAnalytics = lazy(() => import("./pages/faculty/Analytics"));
const FacultyAuthorizations = lazy(() => import("./pages/faculty/Authorizations"));

const AdminDashboard = lazy(() => import("./pages/admin/Dashboard"));
const AdminUsers = lazy(() => import("./pages/admin/Users"));
const AdminDomains = lazy(() => import("./pages/admin/Domains"));
const AdminContent = lazy(() => import("./pages/admin/Content"));
const AdminAssessments = lazy(() => import("./pages/admin/Assessments"));
const AdminTasks = lazy(() => import("./pages/admin/Tasks"));
const AdminAnnouncements = lazy(() => import("./pages/admin/Announcements"));
const AdminSettings = lazy(() => import("./pages/admin/Settings"));
const AdminAudit = lazy(() => import("./pages/admin/Audit"));

function RoleHome() {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={PORTAL_HOME[user.role]} replace />;
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader label="Loading page..." />}>
      <Routes>
        <Route path="/" element={<RoleHome />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        {/* Standalone Fullscreen Assessment Runner (isolated from AppShell) */}
        <Route
          path="/student/assessments/:attemptId/take"
          element={
            <ProtectedRoute roles={["student"]}>
              <TakeAssessment />
            </ProtectedRoute>
          }
        />

        <Route
          element={
            <ProtectedRoute roles={["student", "coordinator", "faculty", "admin"]}>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/requests" element={<RequestsPage />} />
          <Route path="/profile" element={<ProfilePage />} />

          <Route
            path="/student"
            element={
              <ProtectedRoute roles={["student"]}>
                <StudentDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/learning"
            element={
              <ProtectedRoute roles={["student"]}>
                <LearningPathPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/learning/:dayId"
            element={
              <ProtectedRoute roles={["student"]}>
                <LearningDayPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/assessments"
            element={
              <ProtectedRoute roles={["student"]}>
                <StudentAssessments />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/tasks"
            element={
              <ProtectedRoute roles={["student"]}>
                <StudentTasks />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/domains"
            element={
              <ProtectedRoute roles={["student"]}>
                <MyDomains />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/points"
            element={
              <ProtectedRoute roles={["student"]}>
                <StudentPoints />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/leaderboard"
            element={
              <ProtectedRoute roles={["student"]}>
                <Leaderboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/appeals"
            element={
              <ProtectedRoute roles={["student"]}>
                <MyAppeals />
              </ProtectedRoute>
            }
          />

          <Route
            path="/coordinator"
            element={
              <ProtectedRoute roles={["coordinator", "admin"]}>
                <CoordinatorDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/coordinator/content"
            element={
              <ProtectedRoute roles={["coordinator", "admin"]}>
                <ContentBuilder />
              </ProtectedRoute>
            }
          />
          <Route
            path="/coordinator/assessments"
            element={
              <ProtectedRoute roles={["coordinator", "admin"]}>
                <AssessmentBuilder />
              </ProtectedRoute>
            }
          />
          <Route
            path="/coordinator/submissions"
            element={
              <ProtectedRoute roles={["coordinator", "faculty", "admin"]}>
                <CoordinatorSubmissions />
              </ProtectedRoute>
            }
          />
          <Route
            path="/coordinator/submissions/:attemptId"
            element={
              <ProtectedRoute roles={["coordinator", "faculty", "admin"]}>
                <SubmissionDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/coordinator/students"
            element={
              <ProtectedRoute roles={["coordinator", "faculty", "admin"]}>
                <CoordinatorStudents />
              </ProtectedRoute>
            }
          />
          <Route
            path="/coordinator/analytics"
            element={
              <ProtectedRoute roles={["coordinator", "faculty", "admin"]}>
                <CoordinatorAnalytics />
              </ProtectedRoute>
            }
          />

          <Route
            path="/faculty"
            element={
              <ProtectedRoute roles={["faculty", "admin"]}>
                <FacultyDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/faculty/grading"
            element={
              <ProtectedRoute roles={["faculty", "coordinator", "admin"]}>
                <GradingQueue />
              </ProtectedRoute>
            }
          />
          <Route
            path="/faculty/evidence"
            element={
              <ProtectedRoute roles={["faculty", "coordinator", "admin"]}>
                <TaskEvidenceQueue />
              </ProtectedRoute>
            }
          />
          <Route
            path="/faculty/appeals"
            element={
              <ProtectedRoute roles={["faculty", "admin"]}>
                <AppealsQueue />
              </ProtectedRoute>
            }
          />
          <Route
            path="/faculty/adjustments"
            element={
              <ProtectedRoute roles={["faculty", "admin"]}>
                <PointAdjustments />
              </ProtectedRoute>
            }
          />
          <Route
            path="/faculty/analytics"
            element={
              <ProtectedRoute roles={["faculty", "coordinator", "admin"]}>
                <FacultyAnalytics />
              </ProtectedRoute>
            }
          />
          <Route
            path="/faculty/authorizations"
            element={
              <ProtectedRoute roles={["faculty", "coordinator", "admin"]}>
                <FacultyAuthorizations />
              </ProtectedRoute>
            }
          />

          <Route
            path="/admin"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminUsers />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/domains"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminDomains />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/content"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminContent />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/assessments"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminAssessments />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/tasks"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminTasks />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/announcements"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminAnnouncements />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/settings"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminSettings />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/audit"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminAudit />
              </ProtectedRoute>
            }
          />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
