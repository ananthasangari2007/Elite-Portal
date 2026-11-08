# ELITE PORTAL — SYSTEM ARCHITECTURE & TECHNICAL DESIGN

**Document Version:** 2.0.0  
**Status:** Approved Reference  
**Platform:** Francis Xavier Engineering College | Elite Batch (2025–2029)  
**Backend:** FastAPI (ASGI) on Python 3.10+ / Uvicorn  
**Frontend:** React 18 SPA / TypeScript / Vite / Tailwind CSS  
**Database:** PostgreSQL 16 (Neon DB Serverless) with Local SQLite3 Fallback  
**Storage:** Cloudflare R2 (S3-compatible) with Local Disk Fallback  

---

## 1. High-Level System Architecture

The Elite Portal is engineered as a decoupled client-server web application. The frontend is a high-performance single-page application (SPA) built on React 18 and Vite. The backend is an asynchronous, high-throughput ASGI application built on FastAPI, serving structured JSON APIs and delegating resource-intensive operations (such as code compilation and file storage) to dedicated backend subsystems.

```mermaid
flowchart TD
    subgraph Clients["Client Tier (Web & Mobile Browsers)"]
        Browser["React 18 SPA (TypeScript + Vite)"]
    end

    subgraph CDN["Edge & Delivery Tier"]
        Cloudflare["Cloudflare Edge / Reverse Proxy (SSL, DDoS, Edge Cache)"]
    end

    subgraph Backend["Application Server Tier (FastAPI / ASGI)"]
        Uvicorn["Uvicorn ASGI Server"]
        FastAPIApp["FastAPI Core Application (app/fastapi/app.py)"]
        
        subgraph Middlewares["Request Middleware Pipeline"]
            CORS["CORSMiddleware (Configured Origins)"]
            Lifecycle["Request Lifecycle & Audit Middleware"]
            CSRF["CSRF Verification Engine (check_csrf)"]
            RateLimit["In-Memory Sliding Window Rate Limiter"]
        end
        
        subgraph Routers["API Route Controllers"]
            AuthR["/api/v1/auth (Session, Login, Register)"]
            StudentR["/api/v1/student (Tasks, Learning, Assessments)"]
            FacultyR["/api/v1/faculty (Reviews, Grading, Golden Stars)"]
            CoordR["/api/v1/coordinator (Curriculum, Sprints, Analytics)"]
            AdminR["/api/v1/admin (Users, Roles, Settings, Audit)"]
            CommonR["/api/v1/common (Files, Notifications, Help)"]
        end

        subgraph Services["Core Business Services"]
            PortalSvc["Portal Business Logic (app/services/portal.py)"]
            CodeRunner["Multi-Compiler Sandbox (app/services/code_runner.py)"]
            StorageSvc["Cloudflare R2 Storage (app/services/storage.py)"]
            PointsSvc["Points & Ledger Engine (app/services/points.py)"]
            RosterSvc["Institutional Roster Service (app/services/roster.py)"]
        end
    end

    subgraph Persistence["Persistence & Infrastructure Tier"]
        DB[(PostgreSQL 16 / Neon DB / Local SQLite3)]
        R2Bucket[("Cloudflare R2 Object Store (Media Proofs)")]
        LocalSubprocess[["Sandboxed Local Subprocesses (GCC, G++, Python, Node, Java)"]]
    end

    Browser <-->|HTTPS / JSON / WSS| Cloudflare
    Cloudflare <--> Uvicorn
    Uvicorn --> FastAPIApp
    FastAPIApp --> Middlewares
    Middlewares --> Routers
    Routers --> Services
    Services --> DB
    StorageSvc --> R2Bucket
    CodeRunner --> LocalSubprocess
```

---

## 2. Frontend Architecture (React 18 SPA)

The user interface is built as a modular React 18 application in `frontend/src/` configured with strict TypeScript typing, Tailwind CSS utility styling, and Vite bundling.

### 2.1. Component & Layout Architecture

```mermaid
flowchart TD
    App["App.tsx (Root Component)"]
    AuthProvider["AuthProvider (auth.tsx) - Manages User State & Session"]
    BrowserRouter["BrowserRouter (react-router-dom)"]
    
    subgraph Routing["Route Layout & Protection"]
        AppShell["AppShell.tsx (Header, Sidebar, User Profile, Notifications)"]
        ProtectedRoute["ProtectedRoute.tsx (RBAC Role Checks: student, faculty, coordinator, admin)"]
        PublicRoutes["Public Pages: Login, Register, Forgot Password, Reset Password"]
    end

    subgraph StudentViews["Student Portal Views"]
        StudentDash["StudentDashboard.tsx"]
        LearningPath["LearningPath.tsx"]
        DailyTasks["DailyTasks.tsx"]
        Assessments["Assessments.tsx"]
        AssessmentRunner["AssessmentRunner.tsx (Monaco/Ace IDE + Telemetry)"]
        SprintSession["SprintSession.tsx (Betting Assessment)"]
        Leaderboard["Leaderboard.tsx"]
        Appeals["Appeals.tsx"]
    end

    subgraph StaffViews["Staff & Admin Portals"]
        FacultyDash["FacultyDashboard.tsx (Evidence Review Queue)"]
        CoordDash["CoordinatorDashboard.tsx (Syllabus & Sprints)"]
        AdminDash["AdminDashboard.tsx (User Mgmt, Audit Logs, Settings)"]
    end

    App --> AuthProvider
    AuthProvider --> BrowserRouter
    BrowserRouter --> PublicRoutes
    BrowserRouter --> ProtectedRoute
    ProtectedRoute --> AppShell
    AppShell --> StudentViews
    AppShell --> StaffViews
```

### 2.2. State Management & API Integration
- **Authentication State:** Provided by `frontend/src/context/auth.tsx`. Stores user object, authentication status, and CSRF token.
- **API Client:** Encapsulated in `frontend/src/lib/api.ts`. Provides typed helper methods (`get`, `post`, `put`, `delete`, `upload`).
- **Dual-Token Transmission:** Automatically includes `credentials: "include"` for cookie delivery and sends `Authorization: Bearer <token>` from `localStorage` as a fallback. It automatically attaches `X-CSRF-Token` to all mutating requests.
- **Route-Level Code Splitting:** Implemented using `React.lazy()` and `Suspense` across 32 page components, reducing the initial JavaScript payload by over 60%.

---

## 3. Backend Layered Architecture (FastAPI)

The backend follows a clean, four-layer architecture ensuring strict separation of concerns, testability, and maintainability.

```mermaid
flowchart TD
    subgraph Layer1["1. Transport & Routing Layer (app/fastapi/routers/)"]
        direction TB
        R_Auth["auth.py"]
        R_Student["student.py"]
        R_Faculty["faculty.py"]
        R_Coord["coordinator.py"]
        R_Admin["admin.py"]
        R_Common["common.py"]
    end

    subgraph Layer2["2. Security & Dependency Layer (app/fastapi/auth.py)"]
        direction TB
        Dep_User["get_current_user / get_current_user_optional"]
        Dep_Role["require_roles('student', 'faculty', 'coordinator', 'admin')"]
        Dep_CSRF["check_csrf / verify_csrf"]
        Dep_Rate["rate_limit(bucket, limit, window)"]
    end

    subgraph Layer3["3. Service & Business Logic Layer (app/services/)"]
        direction TB
        S_Portal["portal.py (Scores, Streaks, Days, Enrollments)"]
        S_Runner["code_runner.py (Multi-language compilation & sandbox)"]
        S_Storage["storage.py (R2 S3 client, MIME validation, Key gen)"]
        S_Points["points.py (Ledger transactions, Reversals, Rules)"]
        S_Roster["roster.py (Institutional student validation)"]
    end

    subgraph Layer4["4. Data Access & Persistence Layer (app/models/ & app/database.py)"]
        direction TB
        ORM_Models["SQLAlchemy Declarative Models (User, Domain, Task, Assessment, PointLedger, etc.)"]
        ScopedSession["scoped_session(SessionLocal) / db.session"]
        DBDriver["asyncio threadpool / psycopg2 / sqlite3"]
    end

    Layer1 --> Layer2
    Layer2 --> Layer3
    Layer3 --> Layer4
```

---

## 4. Authentication, Session & CSRF Lifecycle

The platform uses a robust dual-channel authentication architecture designed to eliminate browser cross-site tracking restrictions while maintaining strict CSRF defenses.

```mermaid
sequenceDiagram
    autonumber
    actor Student as Student Browser
    participant API as FastAPI Backend (/api/v1/auth)
    participant AuthEngine as Auth & Crypto Engine
    participant DB as Database (PostgreSQL)

    Student->>API: POST /api/v1/auth/login {portal, email, password, remember}
    API->>DB: User.query.filter_by(email=email).first()
    DB-->>API: User record (scrypt hash)
    API->>AuthEngine: user.check_password(password)
    AuthEngine-->>API: Password verified (True)
    API->>API: Verify portal role == user.role
    API->>AuthEngine: secrets.token_urlsafe(32) (Generate CSRF token)
    API->>AuthEngine: URLSafeTimedSerializer.dumps({_user_id, api_csrf, rem})
    AuthEngine-->>API: Signed Session Token
    API->>DB: Update user.last_login = now_utc(); COMMIT
    API-->>Student: HTTP 200 OK<br/>Set-Cookie: session=<token>; HttpOnly; SameSite=Lax<br/>Set-Cookie: elite_session=1; SameSite=Lax (hint)<br/>Body: {data: {token: <token>, csrf_token: <csrf>, user: {...}}}

    Note over Student: Browser stores csrf_token & token in localStorage

    rect rgb(240, 248, 255)
        Note over Student,API: Authenticated Mutating Request (e.g. Task Submission)
        Student->>API: POST /api/v1/student/tasks/1/evidence<br/>Header: X-CSRF-Token: <csrf><br/>Header: Authorization: Bearer <token><br/>Cookie: session=<token>
        API->>API: check_csrf(request) -> validate X-CSRF-Token matches session.api_csrf
        API->>AuthEngine: decode_session_token() -> verify signature & timestamp
        API->>DB: db.session.get(User, user_id)
        API->>API: Process task submission & write evidence
        API-->>Student: HTTP 200 OK {data: {submission_id: 101, status: "pending"}}
    end
```

---

## 5. Multi-Compiler Code Execution Engine

The code runner (`app/services/code_runner.py`) provides secure, isolated compilation and execution for 5 programming languages against automated test cases.

```mermaid
flowchart TD
    Client["Client Submission (code, language, test_cases)"]
    Service["code_runner.py (execute_code)"]
    TempDir["Unique Isolated Temporary Directory (/tmp/elite_code_uuid/)"]
    
    subgraph CompilerSandbox["Compilation & Sandboxing Phase"]
        PythonRunner["python3 -u solution.py (Direct Interpretation)"]
        CRunner["gcc -O2 -w solution.c -o solution.exe (C Compiler)"]
        CppRunner["g++ -O2 -w -std=c++17 solution.cpp -o solution.exe (C++ Compiler)"]
        JavaRunner["javac Solution.java (Java Compiler) -> java Solution"]
        NodeRunner["node solution.js (Node.js Engine)"]
    end

    subgraph ExecutionLimits["Resource & Security Enforcements"]
        Timeout["Subprocess Timeout Monitor (Hard Limit: 2.0s per test case)"]
        Memory["Process Working Set Cap (128MB)"]
        Cleanup["Strict Finally Block: shutil.rmtree(temp_dir)"]
    end

    Client --> Service
    Service --> TempDir
    TempDir --> CompilerSandbox
    CompilerSandbox --> ExecutionLimits
    ExecutionLimits --> Result["Execution Result (status, stdout, stderr, execution_time_ms, passed_count)"]
    Result --> Client
```

---

## 6. Secure Object Storage Architecture

The platform separates file uploads into public user assets (avatars) and confidential evidence assets (daily task proofs, video recordings).

```mermaid
flowchart LR
    subgraph UploadPipeline["Upload Pipeline"]
        UploadReq["User Upload Request (Multipart Form)"]
        Validate["validate_upload (MIME Check, Extension Check, Size Limit)"]
        UUIDGen["Unique Key Generation: tasks/{year}/{month}/{uuid}_{filename}"]
        R2Upload["Upload to Cloudflare R2 (S3 API Client)"]
        DiskFallback["Fallback: instance/uploads/ (Local Disk)"]
        DBRecord["Record TaskEvidence (file_key, file_type, file_size)"]
    end

    subgraph RetrievalPipeline["Secure Retrieval Pipeline"]
        FileReq["GET /api/v1/files/{key}"]
        AuthCheck["Access Control Check (Student Owner / Assigned Faculty / Admin)"]
        R2Fetch["Fetch Object Stream from R2"]
        StreamResponse["StreamingResponse with Content-Type & Security Headers"]
    end

    UploadReq --> Validate
    Validate --> UUIDGen
    UUIDGen --> R2Upload
    R2Upload -.->|If R2 Fails| DiskFallback
    R2Upload --> DBRecord

    FileReq --> AuthCheck
    AuthCheck --> R2Fetch
    R2Fetch --> StreamResponse
```

---

## 7. Database Connection & Pooling Strategy

To prevent connection exhaustion and handle serverless connection dormancy (Neon DB PostgreSQL), the database layer is configured with robust pooling parameters:

```python
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_size": 10,           # Persistent active pool connections
    "max_overflow": 20,         # Burst connections allowed during spikes
    "pool_recycle": 300,        # Recycle connections every 5 minutes
    "pool_pre_ping": True,      # Test connection viability before issuing query
    "pool_timeout": 30,         # Maximum wait time for an available connection
}
```

Each HTTP request is bound to a dedicated scoped database session via `request_scope`. Uncommitted transactions are automatically rolled back, and sessions are cleanly removed in the middleware `finally` block:

```python
@app.middleware("http")
async def request_lifecycle_middleware(request: Request, call_next):
    # Set unique request scope token
    scope_token = request_scope.set(f"req-{req_id}")
    try:
        response = await call_next(request)
    finally:
        await run_in_threadpool(remove_session)
        request_scope.reset(scope_token)
```

---

## 8. Summary Architecture Metrics

| Metric | Target SLA | Implemented Architecture Design |
| :--- | :--- | :--- |
| **API Framework** | ASGI Async | FastAPI 0.115+ running on Uvicorn |
| **Database Pool** | 10 base, 30 max | SQLAlchemy Scoped Session with `pool_pre_ping` |
| **Session Lifetime** | 8h standard, 30d remember | ItsDangerous `URLSafeTimedSerializer` with salt separation |
| **CSRF Defense** | 100% mutating routes | Session-bound and cookie-bound token comparison (`compare_digest`) |
| **Code Runner Timeout** | 2.0s per test case | `subprocess.run(timeout=2.0)` with subprocess tree kill |
| **File Storage** | Zero local disk coupling | Cloudflare R2 via `boto3` client with local fallback |
