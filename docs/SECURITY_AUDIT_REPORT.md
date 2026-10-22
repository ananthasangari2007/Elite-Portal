# Elite Portal — Security Audit Report
**Francis Xavier Engineering College | Elite Batch 2025–2029**
**Audit Date:** 2026-10-22  
**Scope:** Backend APIs, Authentication & Authorization, Session Handling, Data Exposure, File Uploads

---

## 1. Security Overview

The Elite Portal architecture was audited for compliance with modern web application security standards (OWASP Top 10 guidelines). The testing included static analysis, endpoint authorization probing, privilege escalation testing, session manipulation, and input validation checks.

---

## 2. Threat Vector Assessment & Findings

### 2.1 Authentication & Password Handling
- **Password Storage:** Uses modern `scrypt` key derivation function via `werkzeug.security.generate_password_hash` (`scrypt:32768:8:1`). Passwords are never stored in plain text or using deprecated algorithms (such as MD5 or SHA1).
- **Brute Force Protection:** Flask-Limiter is applied to authentication endpoints (`@limiter.limit("10 per minute")` on `/api/v1/auth/login`).
- **Credential Leakage:** User serializer (`user_public()` in `app/api/utils.py`) strictly omits `password_hash`, `reset_token`, and other internal security markers.
- **Portal Selection Enforcement:** Selecting a specific login portal option (e.g., Coordinator) never elevates a user's role. Authentication resolves against the actual database `user.role` record.

### 2.2 Role-Based Access Control (RBAC) & Authorization
- **Endpoint Protection:** All sensitive routes are gated with `@require_roles("role")`.
- **Vertical Privilege Escalation:** Tested student credentials against administrator endpoints (`/api/v1/admin/users`, `/api/v1/admin/settings`). The server returned `403 Forbidden` (`{"error":{"code":"forbidden"}}`).
- **Horizontal Privilege Escalation:** Domain coordinators are strictly scoped to their assigned domain IDs via `domain_ids_for(user_id)`. Requests to view or edit unassigned domains return `403 Forbidden`.
- **Student Record Isolation:** Students can only view their own submissions, attempts, and point ledger entries.

### 2.3 Injection & Tampering
- **SQL Injection:** All database operations use SQLAlchemy ORM with bound parameters and prepared statements. No raw, unescaped SQL string concatenation was identified in user input pathways.
- **Cross-Site Scripting (XSS):**
  - **Frontend:** React's JSX automatically encodes variables before rendering to the DOM.
  - **Server-rendered Templates:** Jinja2 autoescaping is enabled for all `.html` templates.
- **Cross-Site Request Forgery (CSRF):**
  - Mutating API methods (`POST`, `PUT`, `PATCH`, `DELETE`) require the `X-CSRF-Token` header validated against the session cookie.
  - Public authentication routes (`/login`, `/register`) are explicitly managed without leaking session tokens.

### 2.4 Session Security & Cookies
- `SESSION_COOKIE_HTTPONLY = True`: Prevents client-side scripts from reading session cookies.
- `SESSION_COOKIE_SAMESITE = "Lax"`: Protects cookies from cross-site request forgery during top-level navigation.
- `SESSION_COOKIE_SECURE = is_production`: Ensures cookies are only transmitted over HTTPS in staging/production environments.

### 2.5 File Upload & Storage Security
- **Extension Whitelist:** Uploads are strictly validated against `ALLOWED_EXTENSIONS` (`pdf`, `png`, `jpg`, `zip`, etc.) in `app/services/storage.py`. Disallowed executable extensions (`.exe`, `.sh`, `.bat`, `.php`) are rejected with `ValueError`.
- **Directory Traversal:** Filenames are sanitized using `werkzeug.utils.secure_filename` and prefixed with unique UUID4 strings (`uuid4().hex_{safe_name}`).
- **Payload Size Limits:** `MAX_CONTENT_LENGTH` is capped at 50MB; `MAX_UPLOAD_BYTES` defaults to 25MB.
- **Untrusted Code Execution:** The server does not execute uploaded student code files. Code submissions are stored as static files or text strings for review.

### 2.6 Sensitive Data Exposure
- **Assessment Integrity:** The `AssessmentOption` model includes an `is_correct` field. In the student-facing `_attempt_payload` function, options are serialized with `option_public()`, which strips `is_correct` until the assessment attempt is submitted and finalized.
- **Audit Trails:** Sensitive operations (account creation, role alterations, deactivations, grade modifications, point adjustments, domain updates) are recorded in `AuditLog` with `actor_id`, `action`, `target_type`, `target_id`, `old_value`, `new_value`, and UTC timestamp.

---

## 3. Vulnerability Severity Matrix

| Risk / Vector | Severity | Finding / Mitigation | Status |
| :--- | :---: | :--- | :---: |
| **Bypass of Portal Gate** | Critical | Role validated strictly against database user record. | **SECURE** |
| **SQL Injection** | High | SQLAlchemy parameter binding used universally. | **SECURE** |
| **Assessment Answer Leaks** | High | `is_correct` stripped from student attempt payloads. | **SECURE** |
| **CSRF on API Endpoints** | High | Enforced via `X-CSRF-Token` header. | **SECURE** |
| **Unrestricted File Upload** | High | Whitelist validation + UUID path generation. | **SECURE** |
| **Brute Force on Login** | Medium | Rate-limited at 10 requests/minute per IP. | **SECURE** |
| **Unsigned Storage Keys** | Low | Local storage fallback is contained in `instance/uploads`. | **SECURE** |

---

## 4. Recommendations for Production Deployment

1. **Enable HTTPS / SSL:** Ensure `SESSION_COOKIE_SECURE = True` in production by setting `FLASK_ENV=production`.
2. **Configure Cloudflare R2:** Set `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `R2_BUCKET_NAME` for scalable multi-region file storage.
3. **Configure Mail Server:** Supply `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, and `MAIL_PASSWORD` for password reset functionality.
