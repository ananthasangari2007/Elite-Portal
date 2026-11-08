# ELITE PORTAL — COMPREHENSIVE PRODUCT REQUIREMENTS DOCUMENT (PRD)

**Document Version:** 2.0.0  
**Status:** Approved / Baseline Reference  
**Target Platform:** Francis Xavier Engineering College | Elite Batch (2025–2029)  
**System Architecture:** FastAPI (ASGI) + React 18 SPA (TypeScript/Vite) + PostgreSQL / Neon DB  
**Classification:** Confidential Institutional Educational Platform  

---

## 1. Executive Summary & Product Vision

The **Elite Portal** is a specialized, high-accountability institutional learning and performance tracking platform designed specifically for the prestigious **Elite Batch (2025–2029)** at **Francis Xavier Engineering College (FXEC)**. 

Unlike generic Learning Management Systems (LMS), Elite Portal merges structured technical skill acquisition with rigorous operational accountability, competitive gamification, and daily verification mechanisms. The platform enforces daily consistency across foundational competencies (compulsory Data Structures & Algorithms) and advanced elective technology domains (Full Stack Web Development, Artificial Intelligence & Data Science, Cloud Computing, Cybersecurity, Internet of Things, and System Design).

### Core Pillars
1. **Compulsory Daily Accountability:** Enforces daily task completion with photo and video proof of work, reviewed directly by assigned faculty mentors within a strict 1-submission-per-day window.
2. **Double-Entry Gamification Ledger:** Features an immutable, append-only point ledger recording gains, penalties, streaks, golden stars, and tiered leaderboards.
3. **High-Integrity Proctored Assessments:** Incorporates multi-compiler coding environments (Python 3, C, C++, Java, Node.js) paired with client-side anti-tampering telemetry (tab switch counters, fullscreen enforcement, blur monitors).
4. **Strategic Risk Assessments ("Betting Assessments"):** A unique incentive structure wherein students stake points against their performance expectations across stratified scoring tiers.
5. **Role-Segregated Governance:** Five distinct operational roles (Student, Faculty, Faculty Coordinator, Domain Coordinator, and Administrator) with strict Role-Based Access Control (RBAC).

---

## 2. Stakeholder Matrix & User Personas

| Role | Key Persona | Primary Responsibility | Primary Needs & Pain Points |
| :--- | :--- | :--- | :--- |
| **Student** | 1st/2nd Year Elite Scholar | Completing daily tasks, tracking learning paths, submitting evidence, attempting assessments. | Needs instant clarity on daily tasks, transparent point logs, zero-friction code compilation, and clear leaderboard standings. |
| **Faculty Mentor** | Department Assistant Professor | Daily evaluation of task submissions, evidence verification, point adjustments, and student mentorship. | Needs batch review tools, fast video/image evidence previews, single-click approve/reject actions, and clear audit logging. |
| **Faculty Coordinator** | Institutional Batch Coordinator | Overseeing departmental faculty allocations, student progress monitoring, cohort analytics, and reporting. | Needs bird’s-eye view of task completion rates, submission backlogs, unverified students, and aggregate progress reports. |
| **Domain Coordinator** | Domain Subject Matter Expert | Curating learning path curriculum, uploading materials, authoring quizzes and coding assessments. | Needs intuitive syllabus authoring tools, test-case management for coding problems, and domain-level student performance analytics. |
| **Administrator** | Head of Academic Tech / HOD | System configuration, domain creation, user lifecycle management, point rule authoring, and audit inspection. | Needs comprehensive role management, point override mechanisms, bulk roster import, and server health oversight. |

---

## 3. System Scope & Boundaries

### In-Scope
- Student authentication with institutional email (`@francisxavier.ac.in`) and unique register number validation.
- Compulsory domain auto-enrollment (Data Structures & Algorithms) and capped optional domain selection.
- Learning Day progression (unlocking sequential days based on content completion).
- Daily Task submission with Cloudflare R2 / S3-compatible evidence storage.
- Faculty review interface with one-click approve, reject, feedback, and automatic point allocation.
- Multi-compiler sandboxed code runner executing user code against hidden and public test cases.
- Anti-tampering assessment runner capturing telemetry and proctoring events.
- Strategic Betting Assessment sprint sessions with lock-in mechanics and risk-tier point calculations.
- Immutable Point Ledger tracking all credits, debits, reversals, and streak multipliers.
- Support request ticketing and grade appeal workflow.
- Real-time and polling-based notification channels and broadcast announcements.

### Out-of-Scope (Future Enhancements)
- Automated AI-driven webcam facial proctoring or continuous biometric eye-tracking.
- Native iOS / Android mobile applications (platform is delivered as a mobile-responsive Progressive Web App).
- Peer-to-peer real-time chat (support messaging is structured asynchronously as tickets).
- Automated payment gateway integration (portal points are strictly non-monetary academic credits).

---

## 4. Functional Requirements Catalog

### 4.1. Authentication, Identity & Onboarding (FR-001 – FR-010)

- **FR-001: Institutional Roster Lookup**  
  The system must validate incoming student registrations against the institutional master roster (`RosterEntry`). If a student's register number is not present in the roster, self-registration is blocked.
- **FR-002: Student Self-Registration**  
  Students must provide name, valid institutional email (`@francisxavier.ac.in`), register number, mobile number, department, year, section, profile avatar, and external profile URLs (GitHub, LinkedIn, LeetCode).
- **FR-003: Multi-Portal Login Gateway**  
  The login gateway must present 4 selectable portal options: Student, Domain Coordinator, Faculty Coordinator, and Administrator. Attempting to log into a portal not matching the user's assigned role must yield HTTP 403 `role_mismatch`.
- **FR-004: Password Security & Cryptographic Hashing**  
  Passwords must be hashed using `scrypt` with work factors conforming to modern cryptographic standards (`scrypt:32768:8:1`). Plaintext passwords must never be stored, logged, or serialized.
- **FR-005: Dual-Channel Session Issuance**  
  Upon successful login, the server must issue a signed, timestamped session token both as an `HttpOnly`, `SameSite=Lax` cookie (`session`) and as an API JSON token (`data.token`) for `Authorization: Bearer` fallback.
- **FR-006: Session Invalidation & Expiry**  
  Standard sessions must expire after 8 hours of inactivity. If "Remember Me" is selected, session lifetime is extended to 30 days. Signing out must invalidate both cookie and bearer headers.
- **FR-007: Account Status & Approval Gates**  
  Student accounts must have `approval_status` set to either `approved` or `pending`. Unapproved student logins must be blocked with HTTP 403 `pending_approval`. Deactivated accounts must yield HTTP 403 `account_inactive`.
- **FR-008: Password Reset Flow**  
  The system must provide time-limited, single-use password reset tokens (`PasswordResetToken`) expiring in 60 minutes. Token consumption must be idempotent and invalidate previous tokens.
- **FR-009: CSRF Protection & Mitigation**  
  All mutating API endpoints (`POST`, `PUT`, `PATCH`, `DELETE`) must require and validate an `X-CSRF-Token` header bound to the active session or anonymous cookie session.
- **FR-010: Rate Limiting on Authentication Endpoints**  
  Login endpoints must be limited to 10 requests per minute per IP address. Registration must be limited to 5 requests per hour. Violations must return HTTP 429 `rate_limited`.

---

### 4.2. Domain Management & Learning Paths (FR-011 – FR-020)

- **FR-011: Compulsory Domain Auto-Enrollment**  
  Every registered student must automatically be enrolled in the compulsory `DSA` (Data Structures & Algorithms) domain upon account activation. This enrollment cannot be dropped by the student.
- **FR-012: Optional Domain Selection Rules**  
  Students can select up to a maximum of 2 optional domains (configurable via `SystemSetting: max_optional_domains`). Once chosen, modifications are locked after the configured institutional deadline (`domain_change_allowed_until`).
- **FR-013: Domain Allocation to Faculty & Coordinators**  
  Administrators must assign Domain Coordinators (`coordinator`) and Faculty Mentors (`faculty`) to specific domains via `DomainAssignment`. A coordinator or faculty without an active assignment cannot access operational dashboards.
- **FR-014: Structured Learning Day Curriculum**  
  Domains must be organized into sequential `LearningDay` modules (e.g., Day 1 to Day 30) featuring a title, summary, objectives, and sequence ordering.
- **FR-015: Multi-Format Learning Materials**  
  Each Learning Day must support multiple `LearningMaterial` assets: video links (YouTube/Vimeo embed URLs), external documentation links, rich Markdown content, and downloadable PDF resources.
- **FR-016: Granular Content Completion Tracking**  
  The system must record individual material completions via `ContentCompletion`. Students must manually mark materials completed or trigger auto-completion upon reaching threshold read times.
- **FR-017: Sequential Day Progression Locking**  
  A student cannot unlock `LearningDay N+1` until all mandatory materials and quizzes in `LearningDay N` have been marked as completed.
- **FR-018: Learning Day Resource Attachments**  
  Materials must support supplemental file attachments (code templates, starter files) served securely through authorized download URLs.
- **FR-019: Domain Progress Calculation**  
  The system must compute real-time domain completion percentages as:  
  $$\text{Progress} = \left(\frac{\text{Completed Materials} + \text{Passed Quizzes}}{\text{Total Materials} + \text{Total Quizzes}}\right) \times 100$$
- **FR-020: Domain Coordinator Authoring Interface**  
  Domain coordinators must have permissions to create, edit, reorder, archive, and publish Learning Days and associated materials within their assigned domain.

---

### 4.3. Daily Tasks & Proof Verification (FR-021 – FR-030)

- **FR-021: Daily Task Publishing**  
  Faculty and Coordinators must publish daily challenges (`EliteTask`) with title, description, submission guidelines, deadline timestamp, maximum score, and domain mapping.
- **FR-022: Strict Business Day Single-Submission Constraint**  
  A student is restricted to exactly **one evidence submission per task per business day** calculated in Indian Standard Time (`Asia/Kolkata`). This is enforced by a compound unique constraint: `uq_daily_task_evidence_per_task (task_id, student_id, submission_date)`.
- **FR-023: Multi-Evidence Submission Types**  
  Submissions (`TaskEvidence`) must accept three proof types:
  1. Image upload (PNG, JPG, WEBP) showing code/output.
  2. Video upload (MP4, WEBM) demonstrating live execution.
  3. External repository/deployment link (GitHub repo, live URL).
- **FR-024: Secure Object Storage Integration**  
  Uploaded evidence files must be validated for MIME type and magic numbers, assigned unique UUID keys, and stored in Cloudflare R2 (S3-compatible) or local disk fallback. Direct unauthenticated file exposure is strictly prohibited.
- **FR-025: Faculty Review & Grading Queue**  
  Assigned faculty members must access a dedicated review queue listing pending submissions filtered by domain, student, and date.
- **FR-026: One-Click Approval & Rejection Logic**  
  Faculty can approve a submission (awarding full or partial points) or reject it with mandatory corrective feedback.
- **FR-027: Re-Submission & Resubmission Deadlines**  
  Rejected submissions unlock the task for re-submission if the current timestamp is within the grace window (configurable, default 24 hours).
- **FR-028: Daily Streak Tracking & Computation**  
  Submitting daily tasks on consecutive days increments the student’s `current_streak`. If a business day passes without an approved submission, the streak resets to 0.
- **FR-029: Streak Multiplier Bonuses**  
  Reaching streak milestones (e.g., 7 days, 14 days, 30 days) automatically triggers bonus point ledger allocations based on active `PointRule` entries.
- **FR-030: Golden Star Badges**  
  Faculty can award a discretionary `Golden Star` to submissions demonstrating exceptional quality, granting an extra bonus (default: 50 points) and highlighting the student profile.

---

### 4.4. Assessment Engine & Multi-Compiler Code Runner (FR-031 – FR-040)

- **FR-031: Multi-Paradigm Assessment Creation**  
  Assessments (`Assessment`) must support:
  1. Multiple-Choice Questions (Single and Multi-select).
  2. Short Answer / Fill in the Blanks.
  3. Interactive Coding Problems with automated evaluation.
- **FR-032: Sandboxed Multi-Language Code Runner**  
  The system must execute and evaluate code in 5 standard programming languages:
  - Python 3 (`python3`)
  - C (`gcc -O2`)
  - C++ (`g++ -O2 -std=c++17`)
  - Java (`javac` / `java`)
  - Node.js (`node`)
- **FR-033: Automated Test-Case Evaluation**  
  Coding submissions must be evaluated against both public sample test cases and hidden test cases with strict execution time limits (2.0s) and memory caps (128MB).
- **FR-034: Assessment Time Windows & Durations**  
  Assessments must support both strict scheduled availability windows (`start_time` to `end_time`) and individual countdown timers (`duration_minutes`) starting upon test initiation.
- **FR-035: Anti-Cheating & Integrity Telemetry**  
  The assessment runner must capture and log client-side integrity events:
  - Tab switches / browser window blur events (`tab_switch_count`).
  - Fullscreen exit events (`fullscreen_exit_count`).
  - Copy/paste interception into code editors.
- **FR-036: Attempt Limits & Single Active Attempt Rule**  
  Students are restricted to a maximum number of attempts (typically 1). A student cannot start a new attempt while an active attempt remains unsubmitted.
- **FR-037: Proctor Unlock & Administrative Overrides**  
  Faculty or Administrators can issue an `AssessmentAuthorization` to unlock a test or grant additional attempts to students experiencing verified technical glitches.
- **FR-038: Auto-Submission on Timer Expiry**  
  When an attempt's countdown reaches zero, the client and server must automatically finalize and grade all saved answers.
- **FR-039: Instant MCQ Scoring & Code Grading Aggregation**  
  MCQ questions must be scored immediately upon completion. Coding scores must be aggregated based on the proportion of passed hidden test cases.
- **FR-040: Comprehensive Grading Audit History**  
  Every score calculation and manual adjustment must be recorded in `GradingHistory` with grader identity, previous score, new score, and adjustment reason.

---

### 4.5. Strategic Betting Assessments & Wager Rules (FR-041 – FR-050)

- **FR-041: Sprint Session Lifecycle**  
  Coordinators must initiate `EliteSprintSession` instances with predefined entry windows, active testing windows, and evaluation cutoffs.
- **FR-042: Point Commitment & Lock-in Mechanism**  
  Participating students must lock a fixed wager amount (standard: 700 points) into escrow from their point balance before test initiation.
- **FR-043: Strategic Scoring Matrix Compliance**  
  The payout calculation must strictly adhere to the verified institutional matrix based on percentage of total marks:

| Performance Tier | Score Percentage | Escrow Return | Attendance Incentive | Total Points Earned | Net Delta |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **High Distinction** | $> 80\%$ | 700 pts | 100 pts | **800 pts** | **+100 pts** |
| **Satisfactory** | $40\% - 80\%$ | 350 pts | 100 pts | **450 pts** | **-250 pts** |
| **Low Performance** | $1\% - 39\%$ | 0 pts | 100 pts | **100 pts** | **-600 pts** |
| **Attended Zero** | $\le 0\%$ (Attended) | 0 pts | 50 pts | **50 pts** | **-650 pts** |
| **Absent / No-Show** | Did not attempt | 0 pts | 0 pts | **0 pts** | **-700 pts (Total Loss)** |

- **FR-044: Escrow Insufficiency Guard**  
  A student whose balance is below the minimum required stake cannot enter a betting assessment unless granted an administrative subsidy or scholarship exemption.
- **FR-045: Atomic Point Settlement**  
  Upon assessment finalization, the system must execute an atomic transaction releasing escrowed points and crediting earned incentive tiers directly into `PointLedger`.
- **FR-046: Batch Settlement Automation**  
  At sprint window close, a background worker must identify all unattempted registered students and settle their records as `absent` (forfeiting the escrowed balance).
- **FR-047: Sprint Leaderboard Generation**  
  The system must generate sprint-specific leaderboards ranking students by net point yield and percentage scores.
- **FR-048: Dispute Window for Sprint Scores**  
  Students must be allowed a 24-hour dispute window post-settlement to raise appeals against compilation failures or miscalculated MCQs.
- **FR-049: Transparent Sprint Audit Trail**  
  The student ledger must clearly itemize both the initial escrow debit (`sprint_lock`) and the final resolution credit (`sprint_payout`).
- **FR-050: Coordinator Session Analytics**  
  Coordinators must access summary metrics: total wager pool, average score percentage, distribution across the 5 performance tiers, and total institutional points awarded.

---

### 4.6. Points Ledger, Rewards & Leaderboards (FR-051 – FR-060)

- **FR-051: Double-Entry Immutable Ledger**  
  All point modifications must be recorded in `PointLedger` with `student_id`, `points` (positive or negative), `category` (task, quiz, sprint, penalty, bonus, adjustment), `description`, and `created_at`.
- **FR-052: Prohibited In-Place Mutation**  
  The system must strictly prohibit in-place updates or deletions of existing ledger rows. Corrections must be applied as offsetting compensatory transactions.
- **FR-053: Real-Time Total Points Aggregation**  
  A student's total balance is dynamically aggregated using:  
  $$\text{Total Points} = \sum \text{PointLedger.points}$$
- **FR-054: Global Institutional Leaderboard**  
  The global leaderboard must rank all active students across all domains by total points, displaying rank, name, department, points, streak count, and golden stars.
- **FR-055: Domain-Specific Leaderboards**  
  Students must be viewable on domain-filtered leaderboards showing performance strictly derived from activities within that domain.
- **FR-056: Weekly and Monthly Ranking Snapshots**  
  The system must compute periodic leaderboards (Current Week, Current Month) to encourage ongoing participation regardless of historical rank disadvantages.
- **FR-057: Tie-Breaking Hierarchy**  
  Ties in total points must be broken sequentially by:  
  1. Higher number of Golden Stars.  
  2. Higher current active streak.  
  3. Earlier timestamp of the latest earned point.
- **FR-058: Point Rule Authoring Engine**  
  Administrators can configure point values dynamically via `PointRule` (e.g., standard daily task = 100 pts, quiz question = 10 pts, streak milestone = 200 pts).
- **FR-059: Penalty Assessment Mechanisms**  
  Faculty and Admins can assess demerit penalties (negative points) for late submissions, code plagiarism, or unexcused absences.
- **FR-060: Exportable Ranking Reports**  
  Coordinators and Administrators must be able to export leaderboard standings to CSV and Excel formats.

---

### 4.7. Appeals, Support & Communications (FR-061 – FR-070)

- **FR-061: Student Grade Appeals**  
  Students can lodge formal appeals (`Appeal`) against rejected tasks or disputed assessment marks within 48 hours of grade posting.
- **FR-062: Appeal Review Workflow**  
  Faculty mentors must review the appeal statement, re-examine the original evidence, and either uphold the grade or approve the appeal with a point adjustment.
- **FR-063: General Support Ticket System**  
  Students can submit inquiries or bug reports (`StudentRequest`) categorized by subject (technical issue, domain inquiry, attendance query).
- **FR-064: Threaded Ticket Messaging**  
  Tickets must support threaded two-way conversations (`RequestMessage`) between the student and assigned coordinators/administrators.
- **FR-065: Ticket Status Transitions**  
  Tickets must transition through states: `open` $\rightarrow$ `in_progress` $\rightarrow$ `resolved` $\rightarrow$ `closed`.
- **FR-066: Broadcast Announcements**  
  Administrators and Coordinators can publish priority announcements (`Announcement`) targeting all students or specific domain cohorts.
- **FR-067: In-App User Notifications**  
  The system must generate in-app alerts (`Notification`) for key events: task approved/rejected, appeal decision, new assessment available, point penalty applied.
- **FR-068: Notification Read/Unread State Tracking**  
  Users must be able to mark individual notifications or all notifications as read.
- **FR-069: System Activity Audit Trail**  
  All administrative actions, role modifications, point adjustments, and account status changes must be logged in `AuditLog` with actor ID, IP address, action code, and target entity.
- **FR-070: System Configuration Controls**  
  Administrators can modify runtime platform settings (`SystemSetting`) such as maintenance mode, domain change deadlines, and storage bucket configs without restarting the application server.

---

## 5. Non-Functional Requirements (NFR)

### 5.1. Performance & Latency SLAs (NFR-001 – NFR-008)
- **NFR-001:** API response times for standard read operations (`GET`) must be under 150ms at 95th percentile under normal institutional load (500 concurrent active users).
- **NFR-002:** Critical mutating endpoints (`POST /login`, `POST /tasks/submit`) must complete in under 350ms (excluding external file upload network transfer).
- **NFR-003:** Frontend First Contentful Paint (FCP) must occur within 1.2 seconds, and Largest Contentful Paint (LCP) within 2.5 seconds on a standard 4G broadband connection.
- **NFR-004:** The code execution engine must compile and execute student code with hard timeouts: 5.0 seconds maximum execution duration per test case.
- **NFR-005:** Static assets (JS, CSS, images) must be bundled with Brotli/Gzip compression and served with HTTP cache headers allowing 1-year immutable caching for fingerprinted assets.
- **NFR-006:** Database connection pooling must maintain pre-ping checks (`pool_pre_ping=True`) and connection recycling (`pool_recycle=300`) to eliminate dropped serverless connection errors.
- **NFR-007:** Pagination must be enforced on all tabular endpoints (default: 20 records, maximum: 100 records per page) to prevent unbounded memory consumption.
- **NFR-008:** Complex analytical queries (leaderboard generation) must execute in under 300ms by leveraging composite indexes on `(student_id, points)` and materialized cache strategies.

### 5.2. Security, Integrity & Compliance (NFR-009 – NFR-016)
- **NFR-009:** All network transport must be encrypted via TLS 1.3 in production.
- **NFR-010:** Passwords must be hashed using `scrypt` with parameters $N=32768, r=8, p=1$.
- **NFR-011:** Session cookies must be configured with `HttpOnly`, `Secure` (in production), and `SameSite=Lax`.
- **NFR-012:** Every mutating API request must validate a cryptographic `X-CSRF-Token` header.
- **NFR-013:** File uploads must undergo file extension validation, MIME type checking, and file size limits (5MB for avatars, 50MB for video evidence).
- **NFR-014:** Direct object references to files (`/api/v1/files/{key}`) must enforce access controls, preventing unauthorized students from accessing peers' submitted evidence.
- **NFR-015:** Server responses must emit security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`.
- **NFR-016:** Error responses must never leak stack traces, database schemas, internal file paths, or raw SQL queries to clients.

### 5.3. Scalability, Concurrency & Availability (NFR-017 – NFR-024)
- **NFR-017:** The backend architecture must be stateless, allowing horizontal scaling across multiple Uvicorn worker instances behind a reverse proxy.
- **NFR-018:** The PostgreSQL connection pool must accommodate peak concurrent submissions during morning task deadlines without connection exhaustion.
- **NFR-019:** The code runner must execute each compilation in an isolated, unprivileged temporary process workspace with directory auto-cleanup.
- **NFR-020:** The platform must achieve 99.5% uptime during academic operating hours (07:00 AM – 11:00 PM IST).
- **NFR-021:** Server readiness (`/ready`) and liveness (`/health`) probes must respond in under 50ms for container orchestrator health checks.
- **NFR-022:** Roster import must support bulk processing of up to 1,000 student records in a single administrative transaction without request timeout.
- **NFR-023:** In-memory rate limiting must gracefully shed abusive traffic bursts targeting authentication endpoints.
- **NFR-024:** Database migration scripts (Alembic) must support forward and backward compatibility to ensure zero-downtime schema upgrades.

---

## 6. User Stories & Acceptance Criteria

### US-001: Student Daily Task Submission
- **As a** student,  
  **I want to** submit photo and video evidence for my assigned daily task,  
  **So that** my faculty mentor can verify my work and award my daily points and streak.
- **Acceptance Criteria:**
  - `AC-001.1:` The task view displays title, description, submission guidelines, and remaining countdown time for the current business day.
  - `AC-001.2:` Attempting to submit after the daily cutoff (11:59 PM IST) rejects the upload with error `deadline_passed`.
  - `AC-001.3:` The student can upload up to 2 image proofs, 1 video clip, and an optional GitHub repository URL.
  - `AC-001.4:` If a submission already exists for the current task on the current date, the system prevents duplicate submission with error `already_submitted`.
  - `AC-001.5:` Upon submission, the task status updates immediately to `pending_review` in the student UI.

### US-002: Faculty Task Evidence Review
- **As a** faculty mentor,  
  **I want to** inspect pending student submissions with media previews and single-click decision buttons,  
  **So that** I can grade submissions quickly and provide feedback.
- **Acceptance Criteria:**
  - `AC-002.1:` The faculty dashboard displays a filterable list of pending submissions for students assigned to the faculty’s domain.
  - `AC-002.2:` Clicking a submission renders high-resolution image previews and embedded video player.
  - `AC-002.3:` Clicking "Approve" instantly credits the student’s point ledger, updates the submission status to `approved`, and increments the student streak.
  - `AC-002.4:` Clicking "Reject" requires entering a mandatory text feedback reason explaining the rejection.
  - `AC-002.5:` Checking "Award Golden Star" credits an additional 50 bonus points and records the badge in the grading history.

### US-003: Student Coding Assessment
- **As a** student,  
  **I want to** solve programming challenges in an online IDE with automated test case validation,  
  **So that** I can demonstrate my algorithm skills and earn assessment marks.
- **Acceptance Criteria:**
  - `AC-003.1:` The student can select from Python 3, C, C++, Java, or JavaScript.
  - `AC-003.2:` Clicking "Run Code" compiles and executes the solution against public sample test cases within 3 seconds.
  - `AC-003.3:` Clicking "Submit Test" evaluates the solution against hidden test cases and records the score atomically.
  - `AC-003.4:` If the student exits fullscreen or changes tabs, the UI increments the violation counter and displays a security warning.
  - `AC-003.5:` When the duration timer expires, the code in the editor is automatically submitted and graded.

### US-004: Betting Assessment Wager & Settlement
- **As a** student,  
  **I want to** wager 700 points to participate in an Elite Sprint Assessment,  
  **So that** I can win up to 800 points by scoring above 80%.
- **Acceptance Criteria:**
  - `AC-004.1:` Pre-flight screen clearly details the wager amount (700 pts) and the 5-tier scoring payout table.
  - `AC-004.2:` Confirming entry debits 700 points to escrow (`sprint_lock`) and initiates the assessment attempt.
  - `AC-004.3:` Scoring $>80\%$ credits 800 points (net gain: +100 pts).
  - `AC-004.4:` Scoring between $40\%$ and $80\%$ credits 450 points (net loss: -250 pts).
  - `AC-004.5:` Scoring below $40\%$ credits 100 points (net loss: -600 pts).
  - `AC-004.6:` Zero score with attendance credits 50 points; unattempted status yields 0 points (total loss of 700 pts).

---

## 7. Revision History & Approval Sign-Off

| Date | Version | Primary Author / Contributor | Summary of Changes |
| :--- | :--- | :--- | :--- |
| 2026-10-20 | 1.0.0 | Lead Architecture Team | Initial Flask-based product specification and data schema. |
| 2026-11-05 | 1.5.0 | Systems Integration Team | Migration blueprint to FastAPI and dual-channel session authentication. |
| 2026-11-08 | 2.0.0 | Senior Product Manager & QA Architect | Complete baseline PRD matching actual implemented FastAPI codebase, multi-compiler runner, betting assessment rules, and security controls. |
