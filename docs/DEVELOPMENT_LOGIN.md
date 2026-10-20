# Development Login Accounts

These accounts are for **local development and testing only**. They are created
by `scripts/seed_dev_accounts.py`, which refuses to run when `FLASK_ENV`/`APP_ENV`
is `production` or `staging`.

## 1. Seed the accounts

```powershell
python scripts\seed_dev_accounts.py
```

The script is idempotent — running it again does not create duplicates and does
not change existing passwords. To also reset the passwords of existing accounts:

```powershell
python scripts\seed_dev_accounts.py --reset-passwords
```

It also seeds the four learning domains (DSA is compulsory) if they are missing.

## 2. Credentials

Each email maps to exactly one portal option on the login screen. The portal
option order is fixed: Student, Domain Coordinator, Faculty Coordinator, Admin.

| Portal option             | Email                            | Password (default)      | Domain assignment                         |
| ------------------------- | -------------------------------- | ----------------------- | ----------------------------------------- |
| Student Login             | `student@example.com`            | `DevStudent@1234`       | Enrolled in DSA (compulsory) + Full Stack |
| Domain Coordinator Login  | `domain.coordinator@example.com` | `DevCoordinator@1234`   | DSA (primary), Full Stack                 |
| Faculty Coordinator Login | `faculty.coordinator@example.com`| `DevFaculty@1234`       | DSA, Full Stack, AI/ML, Embedded Systems  |
| Admin Login               | `admin@example.com`              | `DevAdmin@1234`         | Not applicable                            |

### Overriding the passwords

Set any of the following environment variables before running the seed script to
use your own development passwords (recommended if you want non-default values):

| Environment variable                | Account                            |
| ----------------------------------- | ---------------------------------- |
| `DEV_STUDENT_PASSWORD`              | `student@example.com`              |
| `DEV_DOMAIN_COORDINATOR_PASSWORD`   | `domain.coordinator@example.com`   |
| `DEV_FACULTY_COORDINATOR_PASSWORD`  | `faculty.coordinator@example.com`  |
| `DEV_ADMIN_PASSWORD`                | `admin@example.com`                |

Example:

```powershell
$env:DEV_ADMIN_PASSWORD = "MyLocalOnlyPassword!"
python scripts\seed_dev_accounts.py --reset-passwords
```

## 3. Demo content accounts

`scripts\seed_demo.py` separately creates richer demo data (learning days,
assessments, Elite Tasks, progress). Its accounts use the password `Elite@1234`:

| Email                       | Role        |
| --------------------------- | ----------- |
| `admin@elite.edu`           | admin       |
| `coordinator@elite.edu`     | coordinator |
| `coordinator.fs@elite.edu`  | coordinator |
| `faculty@elite.edu`         | faculty     |
| `aarthi@elite.edu`          | student     |
| `bharath@elite.edu`         | student     |
| `charu@elite.edu`           | student     |
| `dinesh@elite.edu`          | student     |
| `ezhil@elite.edu`           | student     |

The default admin password is taken from `ADMIN_PASSWORD` in `.env`
(`Admin@1234` in the sample environment).

## Safety notes

- These are **development** credentials. Do not reuse them in production, and do
  not commit real secrets to the repository.
- The test suite must never run against a real database. `tests/conftest.py`
  forces every test run onto a throwaway SQLite database and fails fast if the
  resolved database is not SQLite. Tests call `db.drop_all()`, so this guard is
  essential — see `tests/conftest.py`.
