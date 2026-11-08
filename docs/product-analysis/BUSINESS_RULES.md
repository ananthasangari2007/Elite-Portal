# ELITE PORTAL — EXHAUSTIVE BUSINESS RULES & SCORING LOGIC SPECIFICATION

**Document Version:** 2.0.0  
**Status:** Approved Reference  
**Platform:** Francis Xavier Engineering College | Elite Batch (2025–2029)  
**Timezone Standard:** Indian Standard Time (`Asia/Kolkata`, UTC+05:30)  

---

## 1. Student Eligibility, Identity & Registration Rules

### Rule BR-001: Institutional Email Domain Restriction
- All student and staff accounts must be registered under the official institutional domain: `@francisxavier.ac.in`.
- Any registration attempt with an external email provider (`@gmail.com`, `@yahoo.com`, `@outlook.com`) is rejected with HTTP 400 `invalid_email_domain`.

### Rule BR-002: Roster Verification Gate
- Student self-registration requires entering an institutional student registration number (e.g., `950725104001`).
- The backend queries the institutional master roster table (`RosterEntry`). If the register number is not present, registration is blocked with error `roster_entry_not_found`.
- If the register number is present, the student's legal name, department, year, and section are auto-populated from the roster to prevent identity spoofing.

### Rule BR-003: Register Number Uniqueness
- The database enforces a strict unique constraint on register numbers: `uq_user_register_number`.
- A register number cannot be associated with more than one active user account under any circumstance.

### Rule BR-004: Student Account Approval Status
- Student accounts are created with `approval_status = 'approved'` (if roster pre-verification matches) or `approval_status = 'pending'` (if flagged for manual administrative verification).
- A student with `approval_status = 'pending'` cannot authenticate; login yields HTTP 403 `pending_approval`.

---

## 2. Domain Selection & Curricular Progression Rules

### Rule BR-005: Compulsory Domain Auto-Enrollment (DSA)
- Every student enrolled in the Elite Portal is automatically enrolled in **Data Structures & Algorithms (`dsa`)** upon account creation.
- The `is_compulsory` database flag on domain `dsa` prevents students from dropping, un-enrolling, or swapping this domain.

### Rule BR-006: Maximum Optional Domains Cap
- Students may select a maximum of **2 optional domains** (e.g., Full Stack Development, AI/Data Science, Cloud Computing).
- This cap is controlled dynamically via `SystemSetting: max_optional_domains` (default: 2).
- Attempting to submit 3 or more optional domains yields HTTP 400 `too_many_domains`.

### Rule BR-007: Domain Change Deadline Enforcement
- Domain selections can be freely modified by students until the institutional cutoff date defined in `SystemSetting: domain_change_allowed_until`.
- Once the current UTC timestamp surpasses this deadline, student self-service modifications are locked with HTTP 403 `domain_changes_locked`.
- Post-deadline modifications require explicit administrative intervention or an authorized faculty request ticket.

### Rule BR-008: Sequential Learning Day Progression
- Curricular days within a domain (`LearningDay`) are numbered sequentially ($1, 2, 3, \dots, N$).
- Student access to `LearningDay N+1` is strictly gated: Day $N+1$ unlocks only after all mandatory `LearningMaterial` items in Day $N$ are recorded as completed in `ContentCompletion`.

---

## 3. Daily Task Submission & Business Day Rules

### Rule BR-009: Timezone & Business Day Boundary
- All daily deadlines, submission records, and streak calculations are evaluated relative to **Indian Standard Time (`Asia/Kolkata`, UTC+05:30)**.
- A business day begins at `00:00:00 IST` and concludes at `23:59:59 IST`.

### Rule BR-010: Strict Single-Submission Constraint
- A student is strictly permitted **one submission per task per business day**.
- This is enforced at the database layer via compound unique constraint:
  ```sql
  CONSTRAINT uq_daily_task_evidence_per_task 
  UNIQUE (task_id, student_id, submission_date);
  ```
- Any secondary submission attempt on the same calendar day returns HTTP 400 `already_submitted`.

### Rule BR-011: Evidence Media Validation
- Every task submission (`TaskEvidence`) must include valid verifiable proof conforming to strict storage constraints:
  - **Image Evidence:** PNG, JPG, JPEG, WEBP. Maximum file size: 10MB.
  - **Video Evidence:** MP4, WEBM. Maximum file size: 50MB.
  - **Repository Proof:** Valid URL string pointing to an authorized external code host (`github.com`, `gitlab.com`).
- Uploaded files are verified via magic byte inspection before persistence to Cloudflare R2.

### Rule BR-012: Faculty Evaluation Window & Resubmission Grace Period
- If a submission is reviewed and marked `rejected` by faculty, the student is granted a 24-hour grace window from the rejection timestamp to submit corrected evidence.
- Once marked `approved`, the submission cannot be edited or resubmitted by the student.

---

## 4. Strategic Betting Assessments (Elite Sprints) — Scoring Matrix

The platform includes a high-stakes gamified testing mechanism (`EliteSprintSession`) with an escrow point commitment.

### Rule BR-013: Escrow Point Wager Lock-in
- Entering an Elite Sprint Assessment requires the student to commit a fixed stake of **700 points** into escrow.
- The system checks: $\text{Student Total Points} \ge 700$. If false, entry is blocked with HTTP 400 `insufficient_points`.
- Upon confirmation, 700 points are debited from the student balance to escrow:
  - `PointLedger` entry: `points = -700`, `category = 'sprint_lock'`.

### Rule BR-014: Five-Tier Performance Settlement Matrix
Upon assessment finalization or scheduled session closure, the payout is calculated based on the student's score percentage of total marks:

$$\text{Score Percentage} = \left(\frac{\text{Candidate Marks}}{\text{Assessment Total Marks}}\right) \times 100$$

The settlement calculation strictly complies with the verified institutional matrix:

| Performance Tier | Score Criteria | Escrow Return | Attendance Incentive | Total Points Awarded | Net Point Delta |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Above 80% (High Distinction)** | $> 80\%$ | 700 pts | 100 pts | **800 pts** | **+100 pts** |
| **40% to 80% (Satisfactory)** | $40\% \le \text{Score} \le 80\%$ | 350 pts | 100 pts | **450 pts** | **-250 pts** |
| **1% to 39% (Low Performance)** | $1\% \le \text{Score} < 40\%$ | 0 pts | 100 pts | **100 pts** | **-600 pts** |
| **Attended Zero (Participation)** | $\text{Score} \le 0\%$ (Attended) | 0 pts | 50 pts | **50 pts** | **-650 pts** |
| **Absent (No-Show)** | Did not attend | 0 pts | 0 pts | **0 pts** | **-700 pts (Total Loss)** |

### Rule BR-015: Atomic Settlement Transaction
- Payouts are credited via an atomic database transaction creating a positive `PointLedger` record:
  - `PointLedger` entry: `points = +payout_amount`, `category = 'sprint_payout'`.
- The sprint bid is marked `settled = True` and timestamped in `settled_at`.

---

## 5. Points Ledger & Double-Entry Accounting Rules

### Rule BR-016: Immutable Ledger Integrity
- The `PointLedger` table operates as an **append-only journal**.
- Modifying (`UPDATE`) or deleting (`DELETE`) existing rows in `PointLedger` is strictly prohibited by application services and database triggers.

### Rule BR-017: Compensatory Adjustments & Reversals
- Any correction, grade appeal outcome, or administrative refund must be executed by appending a new compensatory row to `PointLedger` with category `'adjustment'` and descriptive rationale.

### Rule BR-018: Real-Time Balance Derivation
- Student point balances are never stored as static cache numbers. The official balance is always computed as:
  $$\text{Balance} = \sum_{\text{student\_id} = U} \text{PointLedger.points}$$

---

## 6. Daily Streaks & Golden Star Badges

### Rule BR-019: Daily Streak Continuity
- A student’s `current_streak` increments by +1 when a daily task submitted for business day $D$ is approved.
- If a business day passes without an approved task submission, the student’s `current_streak` resets to 0 upon calculation of the subsequent business day.
- `longest_streak` is updated whenever `current_streak > longest_streak`.

### Rule BR-020: Streak Milestone Rewards
- Reaching designated streak milestones triggers automatic ledger bonuses:
  - **7-Day Streak:** +150 bonus points (`category = 'streak_bonus'`).
  - **14-Day Streak:** +350 bonus points.
  - **30-Day Streak:** +1,000 bonus points.

### Rule BR-021: Golden Star Excellence Badges
- Faculty members can award a `Golden Star` to submissions exhibiting exceptional code cleanliness, comprehensive documentation, or advanced optimization.
- Each Golden Star:
  1. Credits **+50 bonus points** to `PointLedger`.
  2. Increments `user.golden_star_count` by 1.
  3. Displays a golden badge on the student’s public profile and leaderboard entry.

---

## 7. Leaderboard Ranking & Tie-Breaking Hierarchy

### Rule BR-022: Multi-Tier Tie-Breaking Algorithm
When students possess identical total point balances on institutional leaderboards, ties are resolved deterministically using the following hierarchy:

1. **Primary Sort:** Total Points earned (Descending).
2. **Secondary Sort:** Total Golden Stars awarded (Descending).
3. **Tertiary Sort:** Current active streak length (Descending).
4. **Quaternary Sort:** Chronological timestamp of the earliest point earned (Ascending / Earlier achievement takes precedence).

---

## 8. Assessment Anti-Cheating & Integrity Rules

### Rule BR-023: Window Blur / Tab Switch Counter
- During an active assessment attempt, client-side event listeners track `visibilitychange` and `window.onblur` events.
- Each violation triggers a POST to `/api/v1/attempts/:id/integrity`, incrementing `tab_switch_count`.
- Reaching 5 tab switches flags the attempt as `suspicious` for coordinator review.

### Rule BR-024: Single Active Sitting Rule
- A student is strictly prohibited from holding more than one active `in_progress` assessment attempt at any given time across the entire portal.
- Attempting to start test $B$ while test $A$ is in progress yields HTTP 400 `active_attempt_exists`.
