# Elite Portal — Known Issues & System Limitations
**Francis Xavier Engineering College | Elite Batch 2025–2029**

This document tracks known external dependencies, environment requirements, resolved issues, and operational notes.

---

## 1. Resolved Issues in Latest Audit & Implementation

| ID | Issue Description | Root Cause | Resolution | Status |
|----|-------------------|------------|------------|--------|
| **FIX-01** | Jinja2 500 error on `/auth/choose-portal` | Template iterated over dict directly expecting key/value unpacking | Fixed iteration to `{% for item in portals %}` with `portal=item.key` | **Resolved** |
| **FIX-02** | Administrator login failed with HTTP 401 | Neon PostgreSQL password hash did not match `Admin@1234` | Re-hashed password in database; verified login across UI & API | **Resolved** |
| **FIX-03** | Assessment start button missing in instructions modal | `assessment_instructions` API did not return `available` field | Updated `assessment_public` and `assessment_instructions` to compute and return `available` & `lock_reason` | **Resolved** |
| **FIX-04** | Monolithic frontend bundle latency | Eager imports of all 32 pages in `App.tsx` | Implemented route-level dynamic code-splitting using `React.lazy` and `Suspense` | **Resolved** |
| **FIX-05** | Lack of single-student assessment unlock override | No authorization model existed | Added `AssessmentAuthorization` table (migration `5b8f1d2a4e90`) and Faculty Desk | **Resolved** |
| **FIX-06** | Betting assessments locked without proctor authorization | No proctor open mechanism existed | Added `POST /api/v1/faculty/assessments/<id>/open-proctor` and Faculty Desk controls | **Resolved** |
| **FIX-07** | Learning day assessment link bypassed modal | `LearningDay.tsx` linked to generic list `/student/assessments` | Updated link to `/student/assessments?id=${a.id}` with auto-open pre-flight modal | **Resolved** |
| **FIX-08** | Missing proctored monitoring during test taking | Runner had no copy/paste or tab switch detection | Implemented Unstop-style proctored runner with copy/paste prevention, tab switch tracking, fullscreen enforcement, and camera feed | **Resolved** |
| **FIX-09** | "Invalid or missing CSRF token" on mutating requests | Frontend held stale in-memory CSRF token after restarts/login, `/api/v1/auth/logout` was not exempt from CSRF checks, and no retry mechanism existed | Added CSRF token synchronization to `login`, `logout`, and `me`, added `/api/v1/auth/logout` to exemptions, deduplicated in-flight CSRF fetches, and added transparent single-retry on 403 `csrf_failed` | **Resolved** |
| **FIX-10** | High application latency and delayed results | Cold connections to remote Neon DB on every request, N+1 queries in `student_dashboard`, and lack of client-side cache causing full-page loaders on navigation | Configured SQLAlchemy connection pooling with keep-alives, batch-aggregated domain progress queries, and added SWR in-memory caching in `useApi` | **Resolved** |
| **FIX-11** | Assessment window did not feel or look like a dedicated exam interface | Assessment runner was nested inside `AppShell` with the portal's navigation sidebar visible, and lacked exam-grade question controls | Moved route outside `AppShell` into a distraction-free full-height interface with exam header, timer, live webcam preview, standard question palette status colors, and Save & Next flow | **Resolved** |
| **FIX-12** | Student leaderboard showed all 4 domains rather than registered domains | Tabs were hardcoded to all domain codes | Replaced with dynamic tabs showing "Overall" and the student's enrolled domains only, and updated backend leaderboard query to filter dynamically | **Resolved** |

---

## 2. External Services Required for Full Production Operation

### 2.1 Cloudflare R2 / S3-Compatible Durable Storage
- **Description:** File uploads currently fall back to the local filesystem (`instance/uploads/`). On ephemeral hosting platforms (such as Render or Heroku without persistent disks), uploaded files will not survive instance restarts or redeployments.
- **Required Configuration:**
  ```env
  R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
  R2_ACCESS_KEY_ID=<your_r2_access_key>
  R2_SECRET_ACCESS_KEY=<your_r2_secret_key>
  R2_BUCKET_NAME=elite-portal-files
  R2_PUBLIC_URL=https://<your_custom_domain_or_r2_subdomain>
  ```
- **Workaround:** In local development, the local fallback stores files durably in `instance/uploads/`.

### 2.2 SMTP Mail Server (Password Reset Emails)
- **Description:** If `MAIL_SERVER` is unconfigured, password reset links cannot be dispatched via email.
- **Development Fallback:** In development mode (`FLASK_ENV=development`), password reset tokens and links are printed directly to the Flask application logs.
- **Required Configuration for Production:**
  ```env
  MAIL_SERVER=smtp.sendgrid.net
  MAIL_PORT=587
  MAIL_USE_TLS=true
  MAIL_USERNAME=apikey
  MAIL_PASSWORD=<your_api_key>
  MAIL_DEFAULT_SENDER=noreply@college.edu
  ```

---

## 3. Network Latency with Remote Cloud Database

- **Observation:** When developing locally against the Neon PostgreSQL cloud database (`ep-wild-mouse-b4cbjh2h-pooler.c-6.us-east-2.aws.neon.tech`), latency over WAN connection to AWS us-east-2 is approximately 200–300ms per round-trip. Multi-query test scripts (`api_smoke.py`) take 1–2 minutes to execute over remote pooler connections.
- **Mitigation for Development:** For rapid local testing and development, use the SQLite fallback by omitting or commenting out `DATABASE_URL` in `.env`. The app seamlessly falls back to `instance/elite_portal.sqlite3`.
- **Note on Neon Cold Starts:** Neon serverless compute instances may experience a brief 3–5 second cold-start latency on the first query after idle periods.

---

## 4. Browser Permissions & Proctoring Environment

- **Camera / Webcam:** Web browsers require explicit user permission to access the webcam. If the user denies camera permission or has no connected webcam, the proctored runner falls back gracefully while recording the system state.
- **Fullscreen API:** Fullscreen entry requires a user gesture (such as clicking "Start Proctored Assessment"). If the student exits fullscreen mode, a warning banner is displayed and an integrity event (`fullscreen_exit`) is recorded.

---

## 5. Runtime Warnings (Python 3.14 & Dependencies)

### 5.1 `datetime.utcnow()` Deprecation Warning
- **Warning:** `DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.`
- **Impact:** Informational only. Occurs in SQLAlchemy default generator functions. Datetimes continue to operate normally.

### 5.2 Flask-Limiter In-Memory Storage Warning
- **Warning:** `UserWarning: Using the in-memory storage for tracking rate limits as no storage was explicitly specified. This is not recommended for production use.`
- **Production Recommendation:** Configure Redis for distributed rate-limiting:
  ```env
  RATELIMIT_STORAGE_URL=redis://localhost:6379/0
  ```
