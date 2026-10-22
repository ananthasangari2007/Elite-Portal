# Elite Portal — End-to-End Test Report
**Francis Xavier Engineering College | Elite Batch 2025–2029**
**Execution Date:** 2026-10-22  
**Test Suites:** Pytest Automated Suite, API End-to-End Smoke Suite, Frontend Production Build

---

## 1. Test Execution Summary

| Test Suite | Total Checks | Passed | Failed | Blocked | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **API End-to-End Smoke Suite** (`scripts/api_smoke.py`) | 47 | 47 | 0 | 0 | **PASS** |
| **Unit & Integration Suite** (`python -m pytest tests`) | 29 | 29 | 0 | 0 | **PASS** |
| **Frontend Production Build** (`npm run build`) | 1 | 1 | 0 | 0 | **PASS** |
| **Cloudflare R2 Live Bucket Test** | 1 | 0 | 0 | 1 | **BLOCKED** (Missing API keys; local fallback PASSED) |

---

## 2. Phase-by-Phase Verification Matrix

### Phase 3: Login and Authentication
| Check | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :---: |
| **Login Option Order** | Student (1), Coordinator (2), Faculty (3), Admin (4) | Exact order verified on `/api/v1/public/config` and `/login` | **PASS** |
| **Anonymous Access** | Protected student/faculty/admin routes return 401 | Returns HTTP 401 `{"error":{"code":"unauthenticated"}}` | **PASS** |
| **Role Mismatch Prevention** | Student selecting Coordinator login option is blocked | Returns HTTP 403 `{"error":{"code":"role_mismatch"}}` | **PASS** |
| **Invalid Credentials** | Incorrect password returns 401 | Returns HTTP 401 `{"error":{"code":"invalid_credentials"}}` | **PASS** |
| **Inactive Account Block** | `is_active_account=False` is rejected | Returns HTTP 403 `{"error":{"code":"account_inactive"}}` | **PASS** |
| **Coordinator Assignment Gate** | Unassigned coordinator blocked from logging in | Returns HTTP 403 `{"error":{"code":"no_domain_assignment"}}` | **PASS** |
| **Session Persistence** | Cookie persists session across `/auth/me` calls | Authenticated user returned on subsequent calls | **PASS** |
| **Secure Logout** | Calling `/auth/logout` invalidates session | Subsequent requests return 401 | **PASS** |

### Phase 4: Student Domain Selection
| Check | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :---: |
| **Compulsory DSA Inclusion** | Empty selection `{"domain_ids": []}` enrolls DSA | DSA (ID 1) enrolled automatically server-side | **PASS** |
| **Optional-Only Payload** | Submitting only Full Stack `{"domain_ids": [2]}` | Server unions DSA: both DSA and Full Stack enrolled | **PASS** |
| **Exceeding Optional Limit** | Selecting > 2 optional domains is rejected | Returns HTTP 400 `{"error":{"code":"too_many_optional"}}` | **PASS** |
| **Invalid Domain IDs** | Non-existent domain ID rejected | Returns HTTP 400 `{"error":{"code":"invalid_domains"}}` | **PASS** |
| **Idempotent Saves** | Resubmitting identical selections creates no duplicates | Existing row retained; no duplicate constraint violations | **PASS** |
| **Domain Change Lockout** | Modifying optional domains after cutoff is blocked | Returns HTTP 403 `{"error":{"code":"domain_change_locked"}}` | **PASS** |

### Phase 5: Student End-to-End Workflow
| Check | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :---: |
| **Student Dashboard** | Loads metrics, enrolled domains, progress bars | Returns metrics with total points and domain progress | **PASS** |
| **Learning Path & Days** | Loads ordered curriculum days for enrolled domains | Returns day hierarchy with active/completed status | **PASS** |
| **Day Detail & Materials** | Returns video links, articles, documents | Materials returned with URLs and titles | **PASS** |
| **Mark Day Completed** | Records completion for student | Returns 200 OK; second call returns `already_completed: true` | **PASS** |
| **Assessment Instructions** | Displays duration, total marks, attempt limit | Returns assessment metadata without answer leaks | **PASS** |
| **Assessment Taking** | Timed attempt creation, autosave question answers | Answers autosaved via PATCH `/attempts/<id>/answers` | **PASS** |
| **Assessment Submission** | Auto-grades MCQ and records score | Returns score; answers graded against database key | **PASS** |
| **Option Privacy** | `is_correct` not exposed in active attempts | Checked all options: `is_correct` field absent | **PASS** |
| **Elite Tasks List** | Displays active daily challenges with states | Tasks list loaded with status and due date | **PASS** |
| **Points History** | Displays ledger breakdown and running total | Summary returned with category totals | **PASS** |
| **Leaderboard Scope** | Displays rank, name, points by overall/monthly/domain | Overall leaderboard returns ranked student entries | **PASS** |
| **Student Requests** | Student raises general or appeal request | Creates `StudentRequest` with HTTP 201 | **PASS** |

### Phase 6: Domain Coordinator Workflow
| Check | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :---: |
| **Coordinator Dashboard** | Loads enrolled student count and domain metrics | Metrics returned correctly | **PASS** |
| **Assigned Scope Enforcement** | Coordinator only sees assigned domains | Filtered strictly to assigned domain IDs | **PASS** |
| **Create Learning Day** | Creates a new curriculum day | Creates `LearningDay` with HTTP 201 | **PASS** |
| **Add Learning Material** | Adds video or document resource to day | Creates `LearningMaterial` with HTTP 201 | **PASS** |
| **Publish Learning Day** | Publishes day for enrolled students | Day status updated to published | **PASS** |
| **Review Submissions** | Lists student assessment submissions | Filtered by assessment and domain | **PASS** |

### Phase 7: Faculty Coordinator Workflow
| Check | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :---: |
| **Faculty Dashboard** | Displays total students, pending evidence count | Metrics returned successfully | **PASS** |
| **Task Evidence Review** | Review student submission, award points | Returns approved status; ledger entry generated | **PASS** |
| **Duplicate Review Protection** | Re-reviewing already-reviewed evidence blocked | Returns HTTP 409 Conflict | **PASS** |
| **Student Requests Inbox** | Displays incoming student tickets | Inbox loads tickets filtered by status | **PASS** |
| **Reply to Request** | Faculty posts message to student thread | Appends `RequestMessage` with HTTP 201 | **PASS** |
| **Appeals Queue** | Review student grade appeal | Returns active appeals list | **PASS** |

### Phase 8: System Administrator Workflow
| Check | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :---: |
| **Admin Dashboard** | System-wide statistics and enrollment distribution | Total students, coordinators, tasks returned | **PASS** |
| **User Management** | List and filter users by role and status | User records returned with profile info | **PASS** |
| **Announcements** | Create and publish platform-wide announcement | Creates and fans out announcement with HTTP 201 | **PASS** |
| **System Settings** | Read and update institutional configuration | Settings saved and persisted | **PASS** |
| **Audit Logging** | Sensitive actions recorded with actor and timestamp | Audit log entries queryable via `/admin/audit-logs` | **PASS** |
| **Student Access Block** | Student attempting admin route receives 403 | Returns HTTP 403 Forbidden | **PASS** |

### Phase 10: Points and Scoring Audit
| Score | Attended | Expected Locked | Expected Attendance | Total Points | Result |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **81** | True | 700 | 100 | **800** | **PASS** |
| **80** | True | 350 | 100 | **450** | **PASS** |
| **40** | True | 350 | 100 | **450** | **PASS** |
| **39** | True | 0 | 100 | **100** | **PASS** |
| **1** | True | 0 | 100 | **100** | **PASS** |
| **0** | True | 0 | 50 | **50** | **PASS** |
| **0 / any** | False | 0 | 0 | **0** | **PASS** |

### Phase 11: Daily Tasks & File Storage
| Check | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :---: |
| **One Task Per Business Day** | Single submission allowed per student per date | Submitting a second task returns HTTP 409 `daily_limit` | **PASS** |
| **Business Day Timezone** | Cutoff calculated using `Asia/Kolkata` (UTC+5:30) | `business_date()` converts timestamps to IST | **PASS** |
| **Allowed File Types** | Validates against `ALLOWED_EXTENSIONS` | Validates file extensions; blocks disallowed formats | **PASS** |
| **Storage Persistence** | Local file storage fallback | Files stored in `instance/uploads/` with UUID prefix | **PASS** |
| **Cloudflare R2 Storage** | Direct bucket upload | Missing production R2 environment variables | **BLOCKED** |

---

## 3. Real Output from Smoke Suite

```text
== Public config ==
  PASS  login order is student, coordinator, faculty, admin

== Auth & role checks ==
  PASS  anonymous cannot access student dashboard
  PASS  role mismatch is rejected
  PASS  wrong password rejected

== Student flow ==
  PASS  student login succeeds
  PASS  student dashboard returns metrics
  PASS  student dashboard has progress for DSA
  PASS  student domain list loads
  PASS  exceeding optional domain limit is rejected
  PASS  learning path loads with days
  PASS  learning day detail loads with materials
  PASS  learning day completion works
  PASS  duplicate completion is idempotent
  PASS  materials filter by type works
  PASS  assessments list includes MCQ
  PASS  assessment instructions load
  PASS  max attempts correctly enforced
  PASS  assessment result is readable
  PASS  elite tasks list loads
  PASS  daily task submission honors daily limit or state
  PASS  point history loads
  PASS  overall leaderboard loads
  PASS  student can create a request

== Coordinator flow ==
  PASS  coordinator login succeeds
  PASS  coordinator dashboard loads
  PASS  coordinator sees assigned domains only
  PASS  coordinator creates a learning day
  PASS  coordinator adds a material
  PASS  coordinator publishes the day
  PASS  coordinator submissions list loads

== Faculty flow ==
  PASS  faculty login succeeds
  PASS  faculty dashboard loads
  PASS  faculty sees pending task evidence endpoint
  PASS  task evidence approval awards points
  PASS  duplicate evidence review is blocked
  PASS  faculty request inbox loads
  PASS  faculty can open a student request
  PASS  faculty can reply to a request
  PASS  appeals list loads

== Admin flow ==
  PASS  admin login succeeds
  PASS  admin dashboard loads
  PASS  admin user list loads
  PASS  admin publishes an announcement
  PASS  admin settings load
  PASS  admin settings save
  PASS  audit logs recorded
  PASS  student cannot access admin endpoints

47 passed, 0 failed
All smoke checks passed.
```

---

## 4. Pytest Execution Output

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Elite Portal-AS
plugins: anyio-4.14.2
collected 29 items

tests\test_domain_selection_and_auth.py ..............                   [ 48%]
tests\test_portal_rules.py ............                                  [ 89%]
tests\test_submission_and_task_rules.py ...                              [100%]

====================== 29 passed, 132 warnings in 43.31s ======================
```
