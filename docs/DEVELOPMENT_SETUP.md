# Elite Portal — Local Development Setup Guide
**Francis Xavier Engineering College | Elite Batch 2025–2029**

This guide provides step-by-step instructions for running, testing, and developing the Elite Portal locally.

---

## 1. Prerequisites

- **Python:** 3.10, 3.11, 3.12, 3.13, or 3.14
- **Node.js:** 18, 20, 22, or 24 (with `npm`)
- **Git**

---

## 2. Quick Start

### 2.1 Backend Setup (Flask API)

1. Open PowerShell or Terminal in the project root (`Elite Portal-AS`):
   ```powershell
   python -m pip install -r requirements.txt
   ```

2. Configure environment file (`.env`):
   ```env
   SECRET_KEY=elite-portal-dev-secret-2025-fxec
   DATABASE_URL=postgresql://neondb_owner:npg_icJdzol1kM5Z@ep-wild-mouse-b4cbjh2h-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   FLASK_ENV=development
   INSTITUTION_NAME=Francis Xavier Engineering College
   INSTITUTION_TIMEZONE=Asia/Kolkata
   BATCH_NAME=Elite Batch 2025-2029
   ADMIN_PASSWORD=Admin@1234
   MAX_OPTIONAL_DOMAINS=2
   ```

3. Ensure database migrations are up-to-date:
   ```powershell
   python -m flask --app run.py db upgrade
   ```

4. Start the backend development server:
   ```powershell
   python -m flask --app run.py run --host 127.0.0.1 --port 5000
   ```
   *The backend will be live at `http://127.0.0.1:5000`.*

---

### 2.2 Frontend Setup (React SPA)

1. Open a second PowerShell terminal in `frontend/`:
   ```powershell
   cd frontend
   npm install
   ```

2. Ensure `frontend/.env` contains the API base path:
   ```env
   VITE_API_URL=/api/v1
   ```

3. Start the Vite development server:
   ```powershell
   npm run dev
   ```
   *The React SPA will be live at `http://localhost:5173`.*

---

## 3. Local Access URLs

| Interface | URL | Description |
| :--- | :--- | :--- |
| **Interactive React SPA** | `http://localhost:5173` | Modern portal interface with live client-side navigation. |
| **Flask Server-Rendered Portal** | `http://127.0.0.1:5000/` | Classic multi-portal authentication chooser and views. |
| **REST API v1 Base** | `http://127.0.0.1:5000/api/v1` | Versioned REST API endpoints. |

---

## 4. Development & Demo Credentials

Each role maps to exactly one portal option on the login screen. The portal option order is strictly fixed:
1. **Student Login**
2. **Domain Coordinator Login**
3. **Faculty Coordinator Login**
4. **Admin Login**

### Demo Accounts
| Role | Portal Option | Email | Password | Assigned Domain / Scope |
| :--- | :--- | :--- | :--- | :--- |
| **Administrator** | Admin Login | `admin@elite.edu` | `Admin@1234` | Full platform management |
| **Domain Coordinator** | Domain Coordinator Login | `coordinator@elite.edu` | `Elite@1234` | DSA |
| **Domain Coordinator** | Domain Coordinator Login | `coordinator.fs@elite.edu` | `Elite@1234` | Full Stack Development |
| **Faculty Coordinator** | Faculty Coordinator Login | `faculty@elite.edu` | `Elite@1234` | All domains (evaluation & appeals) |
| **Student** | Student Login | `aarthi@elite.edu` | `Elite@1234` | DSA (compulsory) + Full Stack + AI/ML |
| **Student** | Student Login | `bharath@elite.edu` | `Elite@1234` | DSA (compulsory) + Full Stack |

### Reserved Development Accounts
Created by `scripts/seed_dev_accounts.py`:
| Role | Email | Password |
| :--- | :--- | :--- |
| Student | `student@example.com` | `DevStudent@1234` |
| Coordinator | `domain.coordinator@example.com` | `DevCoordinator@1234` |
| Faculty | `faculty.coordinator@example.com` | `DevFaculty@1234` |
| Admin | `admin@example.com` | `DevAdmin@1234` |

---

## 5. Running Automated Tests

### 5.1 Pytest Unit & Business Rule Suite
Runs isolated unit tests on a throwaway in-memory SQLite database:
```powershell
python -m pytest tests
```

### 5.2 End-to-End API Smoke Test
Validates all 4 roles, domain rules, day completion, timed assessment taking, evidence submission, and admin endpoints:
```powershell
python scripts/api_smoke.py
```

### 5.3 Frontend Type Check & Build
Verifies TypeScript types and creates production bundle:
```powershell
cd frontend
npm run lint
npm run build
```
