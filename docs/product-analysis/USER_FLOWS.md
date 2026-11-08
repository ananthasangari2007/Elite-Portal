# ELITE PORTAL — END-TO-END USER FLOWS & WORKFLOW SPECIFICATION

**Document Version:** 2.0.0  
**Status:** Approved Reference  
**Platform:** Francis Xavier Engineering College | Elite Batch (2025–2029)  
**Roles Covered:** Student, Faculty Mentor, Faculty Coordinator, Domain Coordinator, Administrator  

---

## 1. Student User Journeys

### 1.1. Student Onboarding & Domain Selection Journey
- **Entry Point:** Public Landing Page (`/login`)
- **Frontend Views:** `LoginPage.tsx` $\rightarrow$ `RegisterPage.tsx` $\rightarrow$ `StudentDashboard.tsx` $\rightarrow$ `DomainSelectionModal.tsx`
- **Backend API Calls:**
  1. `POST /api/v1/auth/roster-lookup` (Validates registration number against college roster)
  2. `POST /api/v1/auth/upload-avatar` (Pre-registration avatar upload)
  3. `POST /api/v1/auth/register` (Account creation)
  4. `POST /api/v1/auth/login` (Authentication)
  5. `GET /api/v1/domains` (Fetch available domains)
  6. `POST /api/v1/student/domains` (Select up to 2 optional domains)

```mermaid
flowchart TD
    Start([Student Visits Portal]) --> RosterCheck{Enter Register No.}
    RosterCheck -->|Found in Roster| FillForm[Enter Email, Password, Social URLs, Avatar]
    RosterCheck -->|Not in Roster| Blocked[Display Error: Register Number Not in Master Roster]
    
    FillForm --> SubmitReg[POST /api/v1/auth/register]
    SubmitReg --> ApprovalCheck{Admin Approval Status}
    ApprovalCheck -->|Pending| WaitScreen[Display: Awaiting Administrator Approval]
    ApprovalCheck -->|Approved| LoginScreen[Sign in via Student Login Portal]
    
    LoginScreen --> AutoDSA[Auto-Enroll in Compulsory DSA Domain]
    AutoDSA --> OptionalDomains{Select Optional Domains?}
    OptionalDomains -->|Select 1 or 2 Domains| SaveDomains[POST /api/v1/student/domains]
    SaveDomains --> DeadlineCheck{Before Change Deadline?}
    DeadlineCheck -->|Yes| Enrolled[Enrollment Active]
    DeadlineCheck -->|No| Locked[Domain Changes Locked]
    Enrolled --> Dashboard([Enter Student Dashboard])
```

---

### 1.2. Daily Task Evidence Submission Journey
- **Entry Point:** Student Dashboard $\rightarrow$ Daily Tasks Tab
- **Frontend Views:** `DailyTasks.tsx` $\rightarrow$ `TaskSubmissionModal.tsx`
- **Business Constraint:** Strictly 1 submission per task per business day (`Asia/Kolkata`).

```mermaid
flowchart TD
    A([Open Daily Tasks View]) --> B[Fetch GET /api/v1/student/tasks]
    B --> C{Task Active & Before 11:59 PM IST?}
    C -->|No| D[Task Closed / Deadline Expired]
    C -->|Yes| E{Already Submitted Today?}
    E -->|Yes| F[Show Submitted Status & Read-Only Proofs]
    E -->|No| G[Select Proof Types: Images, Video, GitHub URL]
    
    G --> H[Upload Media to Cloudflare R2 via POST /api/v1/uploads]
    H --> I[Submit Task via POST /api/v1/student/tasks/:id/submit]
    I --> J{Unique Constraint Check}
    J -->|Pass| K[Create TaskEvidence record in DB status='pending']
    J -->|Duplicate Caught| L[Return 400: already_submitted]
    K --> M[Student UI updates to 'Pending Faculty Review']
```

---

### 1.3. Assessment Pre-Flight, Code Runner & Proctoring Journey
- **Entry Point:** Student Dashboard $\rightarrow$ Assessments Tab
- **Frontend Views:** `Assessments.tsx` $\rightarrow$ `AssessmentInstructions.tsx` $\rightarrow$ `AssessmentRunner.tsx`

```mermaid
flowchart TD
    A([Select Assessment]) --> B[GET /api/v1/assessments/:id/instructions]
    B --> C{Within Window & Attempts Remaining?}
    C -->|No| D[Display: Assessment Closed or Max Attempts Reached]
    C -->|Yes| E[Click 'Start Assessment']
    
    E --> F[POST /api/v1/assessments/:id/start]
    F --> G[Initialize AssessmentAttempt & Start Countdown Timer]
    G --> H[Enter Fullscreen Mode in Browser]
    
    subgraph TestingSession["Active Testing Session"]
        H --> QType{Question Type}
        QType -->|MCQ| AnswerMCQ[Select Option -> PATCH /api/v1/attempts/:id/answers]
        QType -->|Coding| CodeIDE[Write Code in Monaco/Ace Editor]
        
        CodeIDE --> RunSample[POST /api/v1/attempts/:id/run-code]
        RunSample --> CompileSandbox[Sandboxed Subprocess: GCC/Python/Node/Java]
        CompileSandbox --> SampleResult[Display stdout, stderr, execution time]
        
        H --> TelemetryMonitor[Monitor Window Blur / Tab Switch]
        TelemetryMonitor -->|Tab Switch Detected| LogViolation[POST /api/v1/attempts/:id/integrity]
        LogViolation --> IncrementCount[Increment tab_switch_count in DB]
    end
    
    TestingSession --> SubmitTrigger{Submit Clicked OR Timer Expired}
    SubmitTrigger --> Finalize[POST /api/v1/attempts/:id/submit]
    Finalize --> GradeHidden[Auto-Grade Coding against Hidden Test Cases]
    GradeHidden --> RecordScore[Calculate Total Score & Record in GradingHistory]
    RecordScore --> ResultView[Display Assessment Result Summary]
```

---

### 1.4. Strategic Betting Assessment (Sprint Session) Journey
- **Entry Point:** Student Dashboard $\rightarrow$ Active Sprints
- **Frontend Views:** `SprintSession.tsx`
- **Wager Mechanism:** 700 point escrow stake with stratified 5-tier return.

```mermaid
flowchart TD
    A([Open Sprint Assessment]) --> B[Inspect 5-Tier Payout Matrix]
    B --> CheckBalance{Current Points >= 700?}
    CheckBalance -->|Insufficient Points| BlockEntry[Cannot Enter: Balance Below Wager Amount]
    CheckBalance -->|Sufficient| ConfirmWager[Confirm Wager of 700 Points]
    
    ConfirmWager --> LockEscrow[Debit 700 pts to PointLedger category='sprint_lock']
    LockEscrow --> CreateBid[Create EliteSprintBid status='locked']
    CreateBid --> StartExam[Complete Assessment Sitting]
    
    StartExam --> ExamClosed[Testing Window Closes & Settlement Runs]
    ExamClosed --> TierEval{Evaluate Final Marks %}
    
    TierEval -->|> 80%| Tier1[Tier 1: Above 80% -> Escrow 700 + Att 100 = 800 pts (Net +100)]
    TierEval -->|40% to 80%| Tier2[Tier 2: 40-80% -> Escrow 350 + Att 100 = 450 pts (Net -250)]
    TierEval -->|1% to 39%| Tier3[Tier 3: 1-39% -> Escrow 0 + Att 100 = 100 pts (Net -600)]
    TierEval -->|Attended & 0%| Tier4[Tier 4: Attended Zero -> Escrow 0 + Att 50 = 50 pts (Net -650)]
    TierEval -->|Absent| Tier5[Tier 5: Absent -> Total Forfeiture = 0 pts (Net -700)]
    
    Tier1 --> SettlePayout[Credit Payout to PointLedger category='sprint_payout']
    Tier2 --> SettlePayout
    Tier3 --> SettlePayout
    Tier4 --> SettlePayout
    Tier5 --> SettlePayout
    SettlePayout --> UpdateStatus[Mark EliteSprintBid settled=True]
```

---

## 2. Faculty Mentor User Journey

### 2.1. Daily Task Review & Grading Journey
- **Entry Point:** Faculty Portal (`/faculty`)
- **Frontend Views:** `FacultyDashboard.tsx` $\rightarrow$ `EvidenceReviewModal.tsx`

```mermaid
flowchart TD
    A([Faculty Signs In]) --> B[Open Review Queue: GET /api/v1/faculty/task-evidence]
    B --> C[Filter Submissions by Domain and Date]
    C --> D[Select Student Submission]
    
    D --> E[Inspect Image / Play Video / Open GitHub Repository]
    E --> Decision{Evaluation Decision}
    
    Decision -->|Approve Standard| AppStandard[Award 100 Points]
    Decision -->|Approve with Golden Star| AppStar[Award 100 Points + 50 Golden Star Bonus]
    Decision -->|Reject| RejSub[Enter Mandatory Corrective Feedback Reason]
    
    AppStandard --> SubmitReview[POST /api/v1/faculty/task-evidence/:id/review]
    AppStar --> SubmitReview
    RejSub --> SubmitReview
    
    SubmitReview --> UpdateDB[Update TaskEvidence status='approved'/'rejected']
    UpdateDB --> LedgerCredit[Write PointLedger row for Student]
    UpdateDB --> StreakCalc[Update Student current_streak]
    UpdateDB --> NotifyStudent[Send In-App Notification to Student]
```

---

## 3. Coordinator User Journeys

### 3.1. Domain Curriculum & Learning Day Authoring Journey
- **Entry Point:** Coordinator Portal (`/coordinator`)
- **Frontend Views:** `CoordinatorDashboard.tsx` $\rightarrow$ `CurriculumManager.tsx` $\rightarrow$ `DayEditorModal.tsx`

```mermaid
flowchart TD
    A([Domain Coordinator Signs In]) --> B[Select Managed Domain]
    B --> C[Fetch Curricular Days: GET /api/v1/coordinator/domains/:id/days]
    C --> Action{Curriculum Action}
    
    Action -->|Create Day| AddDay[POST /api/v1/coordinator/domains/:id/days {day_number, title, description}]
    Action -->|Add Material| AddMat[POST /api/v1/coordinator/days/:id/materials {type, url, content}]
    Action -->|Reorder| Reorder[POST /api/v1/coordinator/days/reorder {ordering_map}]
    Action -->|Publish| PubDay[POST /api/v1/coordinator/days/:id/publish]
    
    AddDay --> DBCommit[Commit to Database]
    AddMat --> DBCommit
    Reorder --> DBCommit
    PubDay --> DBCommit
    DBCommit --> Audit[Log Action in AuditLog]
    Audit --> Realtime[Immediately Visible to Enrolled Students]
```

---

## 4. Administrator User Journey

### 4.1. Platform Governance & System Configuration Journey
- **Entry Point:** Admin Portal (`/admin`)
- **Frontend Views:** `AdminDashboard.tsx` $\rightarrow$ `UserManagement.tsx` $\rightarrow$ `SystemSettings.tsx` $\rightarrow$ `AuditViewer.tsx`

```mermaid
flowchart TD
    A([Administrator Signs In]) --> B[View Admin Metric Cards: Users, Sprints, Submissions, Storage]
    B --> AdminAction{Administrative Task}
    
    AdminAction -->|User Management| UserMgmt[Create User / Toggle Active / Approve Student]
    AdminAction -->|Domain Setup| DomainSetup[Create Technical Domain / Toggle Compulsory DSA]
    AdminAction -->|Settings Update| SysSettings[PUT /api/v1/admin/settings: Change Deadlines, Maintenance Mode]
    AdminAction -->|Audit Inspection| AuditLogs[Filter AuditLog by Actor, Entity, or Action Type]
    
    UserMgmt --> SaveAdmin[Atomic Database Mutation]
    DomainSetup --> SaveAdmin
    SysSettings --> SaveAdmin
    AuditLogs --> LogView[Display Immutable Security Audit Trail]
    SaveAdmin --> Audit[Record Administrator Action in AuditLog]
```
