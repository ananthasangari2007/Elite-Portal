# Elite Portal — Known Issues & External Dependencies
**Francis Xavier Engineering College | Elite Batch 2025–2029**

This document tracks known limitations, external dependencies, non-blocking runtime warnings, and recommended configurations.

---

## 1. External Services Required for Full Production Operation

### 1.1 Cloudflare R2 / S3-Compatible Durable Storage
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

### 1.2 SMTP Mail Server (Password Reset Emails)
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

## 2. Network Latency with Remote Cloud Database

- **Observation:** When developing locally against the Neon PostgreSQL cloud database (`ep-wild-mouse-b4cbjh2h-pooler.c-6.us-east-2.aws.neon.tech`), latency over WAN connection to AWS us-east-2 is approximately 200–300ms per round-trip. Multi-query test scripts (`api_smoke.py`) take 1–3 minutes to execute over remote pooler connections.
- **Mitigation for Development:** For rapid local testing and development, use the SQLite fallback by omitting or commenting out `DATABASE_URL` in `.env`. The app seamlessly falls back to `instance/elite_portal.sqlite3`.
- **Note on Neon Cold Starts:** Neon serverless compute instances may experience a brief 3–5 second cold-start latency on the first query after idle periods.

---

## 3. Runtime Warnings (Python 3.14 & Dependencies)

### 3.1 `datetime.utcnow()` Deprecation Warning
- **Warning:** `DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).`
- **Impact:** Informational only. Occurs in SQLAlchemy default generator functions. Datetimes continue to operate normally.

### 3.2 Flask-Limiter In-Memory Storage Warning
- **Warning:** `UserWarning: Using the in-memory storage for tracking rate limits as no storage was explicitly specified. This is not recommended for production use.`
- **Production Recommendation:** Configure Redis for distributed rate-limiting:
  ```env
  RATELIMIT_STORAGE_URL=redis://localhost:6379/0
  ```

---

## 4. Student Domain Change Lockout

- **Rule:** Once a student has saved their domain selection and the change window has elapsed, the student cannot unilaterally swap optional domains. The API returns `403 Forbidden` (`domain_change_locked`).
- **Resolution for Coordinators:** An administrator or faculty coordinator can update student domain assignments from the Admin Users management panel (`/admin/users`).
