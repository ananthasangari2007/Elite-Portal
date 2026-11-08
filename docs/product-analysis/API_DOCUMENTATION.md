# ELITE PORTAL — COMPREHENSIVE REST API SPECIFICATION (119 ENDPOINTS)

**Document Version:** 2.0.0  
**Status:** Approved Reference  
**Base URL:** `/api/v1`  
**API Engine:** FastAPI 0.115+ (ASGI)  
**Standard Response Contract:** `{"data": ...}`  
**Standard Error Contract:** `{"error": {"code": string, "message": string, "details": any}}`  

---

## 1. Authentication & Session Module (`/api/v1/auth`) — 10 Endpoints

### 1.1. `GET /api/v1/auth/csrf`
- **Role / Auth:** Public / Anonymous or Authenticated
- **Purpose:** Fetches a valid CSRF token. If signed in, returns the session-bound token; if anonymous, issues a signed cookie token (`elite_csrf`).
- **Response `200 OK`:**
  ```json
  { "data": { "csrf_token": "string" } }
  ```

### 1.2. `GET /api/v1/auth/me`
- **Role / Auth:** Authenticated (`student`, `faculty`, `coordinator`, `admin`)
- **Purpose:** Restores active user session, returns public profile, CSRF token, and enrolled domains.
- **Response `200 OK`:**
  ```json
  {
    "data": {
      "user": { "id": 1, "name": "Jane Doe", "email": "jane@francisxavier.ac.in", "role": "student" },
      "csrf_token": "string",
      "domains": [{ "id": 1, "code": "dsa", "name": "Data Structures", "is_compulsory": true }]
    }
  }
  ```
- **Error `401 Unauthorized`:** `{"error": {"code": "unauthenticated", "message": "Authentication required."}}`

### 1.3. `POST /api/v1/auth/login`
- **Role / Auth:** Public (Rate limit: 10/min)
- **Purpose:** Authenticates user credentials against the specified portal. Sets `session` cookie and returns Bearer token.
- **Request Body:**
  ```json
  {
    "portal": "student | faculty | coordinator | admin",
    "email": "user@francisxavier.ac.in",
    "password": "Password123!",
    "remember": true
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "data": {
      "user": { ... },
      "token": "signed.session.token",
      "csrf_token": "string",
      "redirect": "/student",
      "profile_required": false
    }
  }
  ```
- **Error `401 Unauthorized`:** `invalid_credentials`
- **Error `403 Forbidden`:** `role_mismatch`, `account_inactive`, `pending_approval`, `no_domain_assignment`

### 1.4. `POST /api/v1/auth/logout`
- **Role / Auth:** Authenticated
- **Purpose:** Signs out current user, logs audit event, and clears session cookies.
- **Response `200 OK`:**
  ```json
  { "data": { "message": "Signed out.", "csrf_token": "string" } }
  ```

### 1.5. `POST /api/v1/auth/upload-avatar`
- **Role / Auth:** Public / Pre-registration (Rate limit: 20/hr)
- **Purpose:** Uploads a temporary or permanent avatar image.
- **Payload:** Multipart Form-Data with `file: UploadFile` (PNG, JPG, WEBP $\le$ 5MB).
- **Response `200 OK`:**
  ```json
  { "data": { "avatar_url": "/api/v1/files/avatars/uuid_filename.png" } }
  ```

### 1.6. `POST /api/v1/auth/register`
- **Role / Auth:** Public (Rate limit: 5/hr)
- **Purpose:** Self-registration for students with institutional roster validation.
- **Request Body:**
  ```json
  {
    "name": "John Smith",
    "email": "john.ug.25.cs@francisxavier.ac.in",
    "password": "SecurePassword!",
    "register_number": "950725104001",
    "phone_number": "9876543210",
    "linkedin_url": "https://linkedin.com/in/john",
    "github_url": "https://github.com/john",
    "leetcode_url": "https://leetcode.com/john",
    "avatar_url": "/api/v1/files/avatars/uuid.png"
  }
  ```
- **Response `201 Created`:**
  ```json
  { "data": { "user": { ... }, "message": "Registration successful." } }
  ```

### 1.7. `POST /api/v1/auth/forgot-password`
- **Role / Auth:** Public (Rate limit: 5/hr)
- **Purpose:** Initiates password reset by issuing a timed reset token.
- **Request Body:** `{"email": "user@francisxavier.ac.in"}`
- **Response `200 OK`:** `{"data": {"message": "If an account exists, a reset link was sent."}}`

### 1.8. `POST /api/v1/auth/reset-password`
- **Role / Auth:** Public (Rate limit: 10/hr)
- **Purpose:** Consumes a valid reset token and sets the new password.
- **Request Body:** `{"token": "token_string", "password": "NewPassword123!"}`
- **Response `200 OK`:** `{"data": {"message": "Password updated successfully."}}`

### 1.9. `POST /api/v1/auth/change-password`
- **Role / Auth:** Authenticated
- **Purpose:** Updates active user password requiring current password verification.
- **Request Body:** `{"current_password": "OldPassword!", "new_password": "NewPassword!"}`
- **Response `200 OK`:** `{"data": {"message": "Password changed successfully."}}`

### 1.10. `PATCH /api/v1/auth/profile`
- **Role / Auth:** Authenticated
- **Purpose:** Updates user profile details (bio, phone, social URLs, avatar).
- **Request Body:** `{"bio": "string", "phone_number": "string", "github_url": "string"}`
- **Response `200 OK`:** `{"data": {"user": { ... }}}`

---

## 2. Common & Utility Module (`/api/v1`) — 10 Endpoints

| Method | Endpoint | Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/public/config` | Public | Returns client platform settings (branding, allowed domains). |
| `GET` | `/api/v1/health` | Public | System liveness probe checking API engine and database connectivity. |
| `POST` | `/api/v1/uploads` | Authenticated | Generic multi-evidence upload handler writing to Cloudflare R2. |
| `GET` | `/api/v1/files/{key:path}` | Authenticated | Authorized file proxy streaming media files with role-based checks. |
| `GET` | `/api/v1/requests/{request_id}` | Authenticated | Retrieves detailed message thread for a support ticket. |
| `POST` | `/api/v1/requests/{request_id}/messages` | Authenticated | Appends a response message to a support ticket thread. |
| `PATCH` | `/api/v1/requests/{request_id}/status` | Staff / Admin | Updates ticket lifecycle state (`open`, `in_progress`, `resolved`, `closed`). |
| `POST` | `/api/v1/notifications/{id}/read` | Authenticated | Marks a specific notification as read. |
| `POST` | `/api/v1/notifications/read-all` | Authenticated | Marks all unread user notifications as read. |
| `GET` | `/api/v1/config/uploads` | Authenticated | Returns allowed file types, maximum payload sizes, and storage limits. |

---

## 3. Student Operations Module (`/api/v1/student`) — 29 Endpoints

### 3.1. Dashboards & Domains
- `GET /api/v1/student/dashboard`: High-level summary of points, active streak, enrolled domains, pending tasks, and recent announcements.
- `GET /api/v1/student/points`: Full itemized point ledger history with category totals and streak status.
- `GET /api/v1/domains`: Public listing of all active technical domains.
- `GET /api/v1/student/domains`: Enrolled domains with individual completion percentages.
- `POST /api/v1/student/domains`: Selects optional domains (maximum 2). Blocked if deadline has expired.

### 3.2. Learning Curriculum
- `GET /api/v1/student/domains/{domain_id}/learning-path`: Sequential Learning Days with unlocked status.
- `GET /api/v1/learning-days/{day_id}`: Learning Day detail, video embeds, Markdown notes, and materials.
- `POST /api/v1/learning-days/{day_id}/complete`: Marks current day complete, unlocking sequential Day $N+1$.
- `GET /api/v1/student/materials`: List of study materials filterable by domain and completion state.

### 3.3. Assessments & Code Runner
- `GET /api/v1/student/assessments`: Active, upcoming, and past assessments.
- `GET /api/v1/assessments/{assessment_id}/instructions`: Pre-flight instructions, rules, time limits, and wager terms.
- `POST /api/v1/assessments/{assessment_id}/start`: Initiates test sitting, starts timer, creates `AssessmentAttempt`.
- `GET /api/v1/attempts/{attempt_id}`: Fetches active attempt state, questions, saved answers, and remaining seconds.
- `PATCH /api/v1/attempts/{attempt_id}/answers`: Autosaves candidate answer selections.
- `POST /api/v1/attempts/{attempt_id}/submit`: Finalizes test attempt and triggers grading calculation.
- `POST /api/v1/attempts/{attempt_id}/run-code`: Sandboxed compiler execution against public sample test cases.
- `POST /api/v1/attempts/{attempt_id}/code`: Evaluates candidate code against hidden evaluation test cases.
- `POST /api/v1/attempts/{attempt_id}/integrity`: Logs anti-cheating events (tab switch, fullscreen exit).
- `GET /api/v1/attempts/{attempt_id}/result`: Post-grading score summary, breakdown, and feedback.

### 3.4. Daily Tasks & Proofs
- `GET /api/v1/student/tasks`: Active daily challenges for current business day.
- `GET /api/v1/student/tasks/submissions`: Historical list of student task evidence and review states.
- `POST /api/v1/student/tasks/{task_id}/submit`: Submits photo/video evidence for the task. Enforces 1-per-day constraint.

### 3.5. Support, Appeals & Leaderboards
- `GET /api/v1/student/requests`: List of opened support tickets.
- `POST /api/v1/student/requests`: Creates new inquiry or technical support request.
- `GET /api/v1/student/appeals`: History of grade appeals filed by the student.
- `POST /api/v1/student/appeals`: Files formal appeal against a rejected task or disputed assessment.
- `GET /api/v1/announcements`: Broadcast institutional notices.
- `GET /api/v1/notifications`: Paginated in-app alert inbox.
- `GET /api/v1/leaderboards`: Global and domain-specific student rankings.

---

## 4. Faculty Mentor Module (`/api/v1/faculty`) — 17 Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/faculty/dashboard` | Review queue counts, pending submissions, assigned students, active domains. |
| `GET` | `/api/v1/faculty/domains` | Assigned domain cohorts for the mentor. |
| `GET` | `/api/v1/faculty/task-evidence` | Filterable queue of student submissions requiring review. |
| `POST` | `/api/v1/faculty/task-evidence/{id}/review` | Approves or rejects submission, awards points, grants Golden Stars, provides feedback. |
| `GET` | `/api/v1/faculty/appeals` | List of student grade appeals routed to the faculty. |
| `POST` | `/api/v1/faculty/appeals/{id}/assign` | Claims an appeal for review. |
| `POST` | `/api/v1/faculty/appeals/{id}/decision` | Upholds grade or grants appeal with compensatory points. |
| `GET` | `/api/v1/faculty/point-adjustments` | List of requested manual point adjustments. |
| `POST` | `/api/v1/faculty/point-adjustments` | Creates manual merit adjustment or demerit penalty. |
| `POST` | `/api/v1/faculty/point-adjustments/{id}/review` | Secondary approval for high-value point adjustments. |
| `GET` | `/api/v1/faculty/requests` | Mentor inbox for student inquiry messages. |
| `GET` | `/api/v1/faculty/analytics` | Cohort performance metrics, submission completion rates, streak retention. |
| `GET` | `/api/v1/faculty/assessments` | Domain assessments overseen by faculty. |
| `GET` | `/api/v1/faculty/authorizations` | Active student test unlock authorizations. |
| `POST` | `/api/v1/faculty/assessments/{id}/authorize-student` | Authorizes an extra attempt or resets lock for a glitched student. |
| `POST` | `/api/v1/faculty/assessments/{id}/open-proctor` | Unlocks live proctoring dashboard for active session. |
| `DELETE` | `/api/v1/faculty/authorizations/{id}` | Revokes active proctoring authorization. |

---

## 5. Domain Coordinator Module (`/api/v1/coordinator`) — 29 Endpoints

### 5.1. Dashboard & Curriculum Management
- `GET /api/v1/coordinator/dashboard`: Domain health metrics, content completion velocity, assessment averages.
- `GET /api/v1/coordinator/domains`: Domains managed by coordinator.
- `GET /api/v1/coordinator/domains/{domain_id}/days`: Curricular days in domain.
- `POST /api/v1/coordinator/domains/{domain_id}/days`: Creates new Learning Day.
- `PATCH /api/v1/coordinator/days/{day_id}`: Updates Day title, description, or objectives.
- `POST /api/v1/coordinator/days/{day_id}/publish`: Makes day visible to enrolled students.
- `POST /api/v1/coordinator/days/{day_id}/lock`: Temporarily locks day from student progression.
- `POST /api/v1/coordinator/days/reorder`: Batch updates sequence ordering of days.
- `DELETE /api/v1/coordinator/days/{day_id}`: Archives curricular day.
- `POST /api/v1/coordinator/days/{day_id}/materials`: Uploads or attaches learning resource.
- `PATCH /api/v1/coordinator/materials/{material_id}`: Updates resource metadata or content.
- `DELETE /api/v1/coordinator/materials/{material_id}`: Removes learning resource.

### 5.2. Assessment Authoring & Sprint Sessions
- `GET /api/v1/coordinator/domains/{domain_id}/assessments`: Assessments in coordinator’s domain.
- `POST /api/v1/coordinator/assessments`: Authors new quiz, coding test, or betting assessment sprint.
- `GET /api/v1/coordinator/assessments/{assessment_id}`: Full assessment schema, question bank, test cases.
- `PATCH /api/v1/coordinator/assessments/{assessment_id}`: Updates test parameters, durations, windows.
- `POST /api/v1/coordinator/assessments/{assessment_id}/publish`: Publishes test to students.
- `POST /api/v1/coordinator/assessments/{assessment_id}/close`: Closes testing window and triggers settlement.

### 5.3. Submissions, Analytics & Exports
- `GET /api/v1/coordinator/submissions`: All test attempts across domain.
- `GET /api/v1/coordinator/submissions/{attempt_id}`: Candidate code, answers, proctoring telemetry.
- `POST /api/v1/coordinator/submissions/{attempt_id}/grade`: Manual override grading for subjective questions.
- `POST /api/v1/coordinator/submissions/{attempt_id}/attendance`: Overrides attendance status for sprint settlement.
- `POST /api/v1/coordinator/submissions/{attempt_id}/request-changes`: Returns submission for candidate correction.
- `GET /api/v1/coordinator/students`: Enrolled students in domain.
- `GET /api/v1/coordinator/students/{student_id}`: Individual student transcript, progress, and streak log.
- `GET /api/v1/coordinator/analytics`: Aggregate domain charts and pass rates.
- `GET /api/v1/coordinator/students/progress`: Matrix of daily completion across all domain students.
- `GET /api/v1/coordinator/exports/students.csv`: CSV export of student performance.
- `GET /api/v1/coordinator/exports/submissions.csv`: CSV export of assessment grades.

---

## 6. Administrator Module (`/api/v1/admin`) — 24 Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/admin/dashboard` | System-wide statistics: total users, active sessions, storage consumption, DB status. |
| `GET` | `/api/v1/admin/users` | Master user registry with search, role filters, and pagination. |
| `POST` | `/api/v1/admin/users` | Creates new user account (faculty, coordinator, admin, student). |
| `PATCH` | `/api/v1/admin/users/{id}` | Updates user role, department, or profile attributes. |
| `POST` | `/api/v1/admin/users/{id}/toggle-active` | Activates or deactivates user account access. |
| `POST` | `/api/v1/admin/users/{id}/approve` | Approves pending student registration. |
| `POST` | `/api/v1/admin/users/{id}/reset-password` | Administrative password reset trigger. |
| `GET` | `/api/v1/admin/domains` | Master technical domain registry. |
| `POST` | `/api/v1/admin/domains` | Creates new academic domain with compulsory flag. |
| `PATCH` | `/api/v1/admin/domains/{id}` | Updates domain properties (color, icon, description). |
| `POST` | `/api/v1/admin/domains/{id}/toggle-active` | Toggles domain availability across the portal. |
| `GET` | `/api/v1/admin/content` | Content registry across all domains and learning days. |
| `GET` | `/api/v1/admin/assessments` | Master assessment registry. |
| `POST` | `/api/v1/admin/assessments/{id}/reopen` | Reopens a closed assessment window. |
| `POST` | `/api/v1/admin/assessments/{id}/auto-release` | Releases grades to student dashboards. |
| `GET` | `/api/v1/admin/tasks` | Master daily task registry. |
| `POST` | `/api/v1/admin/tasks` | Publishes platform-wide institutional challenge. |
| `PATCH` | `/api/v1/admin/tasks/{id}` | Updates task requirements or deadlines. |
| `GET` | `/api/v1/admin/announcements` | Master broadcast announcement registry. |
| `POST` | `/api/v1/admin/announcements` | Publishes system-wide or domain broadcast notice. |
| `PATCH` | `/api/v1/admin/announcements/{id}` | Updates or expires announcement. |
| `GET` | `/api/v1/admin/settings` | Fetches runtime configuration parameters. |
| `PUT` | `/api/v1/admin/settings` | Updates platform configuration (deadlines, maintenance mode). |
| `GET` | `/api/v1/admin/audit-logs` | Filterable administrative audit trail. |
