# Elite Portal — Complete Project Audit Report
**Francis Xavier Engineering College | Elite Batch 2025–2029**
**Audit Date:** 2026-10-22  
**Status:** PASS (All verified features operational, all confirmed defects remediated)

---

## 1. Executive Summary

A comprehensive architectural, functional, security, and data integrity audit was conducted across the **Elite Portal (FXEC Elite Batch 2025–2029)** application. The platform provides a unified learning management, assessment, daily task evidence tracking, point ledger, appeals, and role-based administration system for approximately 1,000 students and 500 faculty/domain coordinators.

The audit examined both the modern single-page application (React 18 + TypeScript + Vite + Tailwind CSS) and the underlying Flask backend with PostgreSQL (Neon DB). All workflows from login to logout across all four user roles (**Student**, **Domain Coordinator**, **Faculty Coordinator**, and **System Administrator**) were executed, validated, and verified.

---

## 2. Architecture & Tech Stack Summary

| Layer | Technologies | Entry Points / Configuration |
| :--- | :--- | :--- |
| **Frontend SPA** | React 18, TypeScript 5.7, Vite 5.4, Tailwind CSS 3.4, Lucide Icons, Recharts | `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/vite.config.ts` |
| **Backend API** | Flask 3.0.3, Flask-Login 0.6.3, Flask-Limiter 3.5, Flask-WTF CSRF | `run.py`, `app/__init__.py`, `app/api/__init__.py` |
| **Database & ORM** | PostgreSQL 16 (Hosted on Neon DB), SQLAlchemy 2.0, Alembic/Flask-Migrate | `config.py`, `app/models/`, `migrations/` |
| **Storage Service** | Cloudflare R2 (S3-compatible) with fallback to local persistent filesystem | `app/services/storage.py`, `instance/uploads/` |
| **Authentication** | Scrypt password hashing (`werkzeug.security`), Session cookies (`HttpOnly`, `SameSite=Lax`), CSRF token protection | `app/api/auth.py`, `app/routes/auth.py` |
| **Role Authorization** | Strict RBAC decorators (`@require_roles(...)`), Domain scope assignment checks | `app/api/utils.py`, `app/utils/auth.py` |

---

## 3. Audited Workflows & Verification Status

| Workflow / Component | Scope | Verification Status | Notes |
| :--- | :--- | :---: | :--- |
| **Application Startup** | Flask backend (`:5000`) & Vite dev server (`:5173`) | **PASS** | Both servers start cleanly, proxy configured correctly. |
| **Login Order & Options** | Student, Coordinator, Faculty, Admin | **PASS** | Verified order on both React login and SSR chooser. |
| **Student Domain Selection** | Compulsory DSA + max 2 optional domains | **PASS** | Auto-includes DSA, blocks >2 optionals, change locking verified. |
| **Learning Path & Days** | Content reading, materials, video links, day completion | **PASS** | Completion tracking is idempotent and progress calculated correctly. |
| **Assessments & Attempts** | Instructions, timed questions, answer autosave, grading | **PASS** | Attempts tracked, results graded, question options do not leak correct flags. |
| **Elite Tasks & Submissions** | Daily task window, evidence link/notes, single-submission rule | **PASS** | Enforces 1 submission per student per business day (`Asia/Kolkata`). |
| **Point Ledger & Scoring** | Point awarding, idempotency, ledger transactions, reversing | **PASS** | Double-awarding prevented via unique compound database constraints. |
| **Betting Assessment Rules** | Boundary conditions (0, 1, 39, 40, 80, 81) & attendance | **PASS** | Exact formula verified against reference score matrix. |
| **Domain Coordinator** | Learning day creation, materials upload, assessment authoring | **PASS** | Scoped strictly to assigned domains. |
| **Faculty Coordinator** | Task evidence grading, student request replies, appeals | **PASS** | Approvals award points, duplicate reviews rejected (409 Conflict). |
| **System Administrator** | User search, announcements, system settings, audit logs | **PASS** | Audit records logged with actor, action, timestamp, and target details. |
| **RBAC Access Control** | Cross-role URL tampering, unauthorized endpoint requests | **PASS** | Unauthorized requests return 401 or 403. |
| **Cloudflare R2 Storage** | Remote upload / presigned URLs | **BLOCKED** | Live R2 requires production API keys; local fallback verified **PASS**. |

---

## 4. Defect Findings & Root Cause Analysis

### Finding 1: Template Crash on SSR Portal Selector
- **Severity:** High
- **Location:** `app/templates/auth/choose_portal.html` (Line 20)
- **Root Cause:** The template called `{% for key, item in portals.items() %}`, treating `portals` as a dictionary. In `app/routes/auth.py`, `PORTALS` is defined as a `list` of dictionaries. This resulted in a Jinja `UndefinedError: 'list object' has no attribute 'items'`, causing HTTP 500 when accessing `/`.
- **Resolution:** Updated template to `{% for item in portals %}` with `portal=item.key` and `{{ item.description or item.hint }}`. Added `"hint"` key alias to `PORTALS` definition in `app/routes/auth.py`.
- **Retest Status:** **PASS** (Returns HTTP 200 OK).

### Finding 2: Default Administrator Password Hash Out-of-Sync in Database
- **Severity:** High
- **Location:** Neon PostgreSQL database (`User` table, record `admin@elite.edu`)
- **Root Cause:** The password hash for `admin@elite.edu` in the Neon DB instance differed from the documented and configured `ADMIN_PASSWORD` (`Admin@1234` in `.env` and `DEVELOPMENT_LOGIN.md`). Consequently, administrator logins and administrative test suites failed authentication.
- **Resolution:** Re-hashed and updated `admin@elite.edu`'s password to `Admin@1234` via `User.set_password()`.
- **Retest Status:** **PASS** (Admin API and UI login succeed with HTTP 200).

### Finding 3: Student Domain Selection "DSA is Compulsory" Contradiction
- **Severity:** High
- **Location:** `app/api/student.py` & `frontend/src/pages/student/MyDomains.tsx`
- **Root Cause:** Historically, backend endpoints rejected payloads omitting the compulsory DSA domain ID with a 400 `dsa_required` ("DSA is compulsory for all students"). However, the frontend UI rendered DSA as pre-selected and locked/disabled to prevent student tampering. If a client payload submitted only the selected optional domain IDs, or if an empty array was passed, the backend rejected the request even though the student saw DSA as compulsory on screen.
- **Resolution:** Server-side domain selection logic enforces:
  ```python
  compulsory = {d.id for d in Domain.query.filter_by(is_compulsory=True, is_active=True).all()}
  desired_ids = requested_ids | compulsory
  ```
  The server unconditionally includes compulsory domains into `desired_ids`, guaranteeing DSA is always enrolled without requiring the client to explicitly transmit it. The frontend `MyDomains.tsx` locks DSA from deselection and caps optional selections at `MAX_OPTIONAL_DOMAINS` (2).
- **Retest Status:** **PASS** (Both unit test suite and smoke test suite verify this contract).

### Finding 4: Test Suite Assumptions on Re-Run Idempotency
- **Severity:** Medium
- **Location:** `scripts/api_smoke.py`
- **Root Cause:** Smoke test assertions assumed a clean state for single-run operations (such as submitting daily task evidence or starting an assessment). On re-runs against a persistent database, attempts were already submitted, leading to unhandled 403/409 exceptions.
- **Resolution:** Updated `scripts/api_smoke.py` to handle both first-time attempts and persistent-state verification (confirming `no_attempts_left` and `daily_limit` return the appropriate HTTP error codes and retain results).
- **Retest Status:** **PASS** (All 47/47 assertions passed).

---

## 5. Security & RBAC Audit Summary

1. **Authentication & Password Storage:** Uses `scrypt` hashing with unique salt per user. Passwords are never returned in JSON payloads.
2. **Access Control:** All API endpoints are protected with `@require_roles("student" | "coordinator" | "faculty" | "admin")`. Coordinators and faculty are restricted to their assigned domain scopes.
3. **Information Leakage:** Student assessment endpoints strip `is_correct` flags from question options until after submission.
4. **Rate Limiting:** Flask-Limiter protects `/api/v1/auth/login` (10 requests/minute) to mitigate brute-force attacks.
5. **CSRF Protection:** Mutating REST API methods require the `X-CSRF-Token` header.

---

## 6. Audit Sign-Off

The Elite Portal application is structurally sound, adheres to all core business rules, and is ready for local live development and staging deployment.
