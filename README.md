# Human–AI Interaction Lab (HAI-Lab)

A full-stack behavioral research platform for designing controlled human–AI interaction experiments, enforcing informed consent and persistent random assignment, logging deterministic AI dialogues, and exporting analysis-ready datasets.

---

## Table of Contents
1. [System Architecture & How HAI-Lab Works](#system-architecture--how-hai-lab-works)
2. [Tech Stack](#tech-stack)
3. [Repository Structure](#repository-structure)
4. [Quick Start: Local Development](#quick-start-local-development)
5. [Quick Start: Full Docker Compose Stack](#quick-start-full-docker-compose-stack)
6. [Complete End-to-End Study Walkthrough (Copy-Paste Example)](#complete-end-to-end-study-walkthrough-copy-paste-example)
7. [REST API Reference](#rest-api-reference)
8. [Analytics, Data Quality & CSV Exports](#analytics-data-quality--csv-exports)
9. [Automated Verification (Pytest & Next.js Build)](#automated-verification-pytest--nextjs-build)
10. [Development Milestones](#development-milestones)

---

## System Architecture & How HAI-Lab Works

HAI-Lab enforces strict experimental validity across two isolated portals backed by a 12-table PostgreSQL relational schema:

### 1. Researcher Workbench (`/login`, `/dashboard`, `/experiments/[id]`)
* **Authentication & Ownership Isolation:** Researchers register or sign in using Argon2id password hashing and signed JWT bearer tokens. Every API query enforces strict owner isolation so researchers can only read, modify, publish, pause, close, or export studies they own.
* **Draft vs. Immutable Version Snapshots:** Researchers configure multi-arm studies in a mutable **draft** state. Clicking **Publish Immutable Version** validates that at least **2 conditions** exist and every condition has at least **1 task**, then clones the configuration into an immutable `ExperimentVersion` (`v1`, `v2`, …). Subsequent edits to the draft never mutate active or historical participant sessions.
* **Tokenized Invitations:** Researchers generate single-use or multi-use participant invitation links (`/study/<token>`) with configurable expiration windows. Only the SHA-256 hash of each invitation token is stored in PostgreSQL.

### 2. Participant Study Portal (`/study`, `/study/[token]`)
* **Strict Informed Consent Gate:** Participants open an invitation link, receive a pseudonymous identifier (`P-XXXXXXXX`), and review the study information sheet. The backend blocks access to conditions, tasks, and AI chat until consent is explicitly granted. Declining terminates the session cleanly without exposing experimental arms.
* **Persistent Random Assignment:** Upon consent, the server assigns the participant uniformly at random (`secrets.choice`) to one condition in the published version and persists that assignment (`UniqueConstraint(participant_id, version_id)`). Refreshing the browser, reconnecting, or retrying always returns the exact same condition—never re-randomizing.
* **Controlled Deterministic AI Provider:** Instead of introducing live-LLM non-determinism as a confounding variable, the AI chat panel uses a deterministic `ControlledMockProvider` that delivers each condition's configured `ai_answer_template` (and optional `ai_explanation_template`), persisting every message with UTC timestamps.
* **Validated Post-Task Ratings & Telemetry:** Participants complete structured Likert (1–7) and free-text questions with server-side range and required-field validation, while every lifecycle milestone (`experiment_opened`, `consent_submitted`, `condition_assigned`, `task_started`, `message_sent`, `response_received`, `rating_submitted`, `task_completed`, `experiment_completed`) is logged to the `events` table.

---

## Tech Stack

* **Frontend:** Next.js 16 (App Router), React, TypeScript, Tailwind CSS
* **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Pandas, Pytest
* **Database:** PostgreSQL 16
* **Infrastructure:** Docker & Docker Compose

---

## Repository Structure

```text
human-ai-interaction-lab/
├── backend/
│   ├── alembic/                  # Database migrations
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py           # JWT & RBAC dependencies
│   │   │   └── v1/               # auth, experiments, participant, analytics, health
│   │   ├── core/                 # config, database engine, Argon2id/JWT/SHA-256 security
│   │   ├── models/               # 12 SQLAlchemy 2.0 relational models & enums
│   │   ├── schemas/              # Pydantic v2 request/response contracts
│   │   ├── services/             # Business logic, mock AI provider, pandas analytics, CSV export
│   │   └── main.py               # FastAPI application entrypoint
│   ├── tests/
│   │   └── test_hai_lab_flow.py  # End-to-end integration & security tests
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
├── database/
│   └── seed/
│       └── seed_demo.py          # Seeds demo researcher & sample two-arm experiment
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── dashboard/        # Researcher study list & creation
│   │   │   ├── experiments/[id]/ # Design, Recruitment & Analytics/CSV Studio
│   │   │   ├── login/            # Researcher sign-in & registration
│   │   │   ├── study/            # Participant token entry
│   │   │   └── study/[token]/    # Guided consent, AI chat & Likert evaluation runner
│   │   └── lib/
│   │       └── api.ts            # Typed fetch client & authenticated CSV downloader
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── README.md
```

---

## Quick Start: Local Development

### 1. Environment Variables
Ensure these two local environment files are present:

* **`backend/.env`**
  ```env
  APP_ENV=development
  DATABASE_URL=postgresql+psycopg://app_user:change_me@localhost:5432/hai_lab
  SECRET_KEY=dev_secret_key_replace_in_production_987654321
  ACCESS_TOKEN_EXPIRE_MINUTES=60
  FRONTEND_ORIGIN=http://localhost:3000
  ```
* **`frontend/.env.local`**
  ```env
  NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
  ```

### 2. Start PostgreSQL
```powershell
docker compose up -d db
```

### 3. Run Migrations, Seed Demo Data & Start the Backend API
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
python ..\database\seed\seed_demo.py
uvicorn app.main:app --reload --port 8000
```
* **Swagger API Documentation:** `http://localhost:8000/docs`

### 4. Start the Next.js Frontend (in a second terminal)
```powershell
cd frontend
npm install
npm run dev
```
* **Web Application:** `http://localhost:3000`

### 5. Demo Researcher Credentials (Seeded)
* **Email:** `researcher@hailab.org`
* **Password:** `Researcher123!`

---

## Quick Start: Full Docker Compose Stack

Build and launch PostgreSQL, the FastAPI backend (which automatically runs `alembic upgrade head` on startup), and the Next.js frontend together:

```powershell
docker compose up --build -d
```

Open **`http://localhost:3000`** once `hai_lab_db`, `hai_lab_backend`, and `hai_lab_frontend` are healthy.

---

## Complete End-to-End Study Walkthrough (Copy-Paste Example)

Use the inputs below to create, publish, run, and analyze a complete two-arm study in your browser:

### Step 1: Sign In & Create a Draft Study
1. Open **`http://localhost:3000/login`** and sign in with `researcher@hailab.org` / `Researcher123!`.
2. On the Dashboard, click **+ New Experiment** and enter:
   * **Study Title:** `Credit Underwriting AI Explanation Study`
   * **Internal Description:** `Between-subjects comparison of answer-only vs. explained AI recommendations.`
   * **Participant Information Sheet:** `You are invited to evaluate an AI decision-support assistant on a financial underwriting case. Participation takes ~3 minutes and all data is stored pseudonymously.`
3. Click **Create Study**.

### Step 2: Add Two Experimental Conditions (**Design** Tab)

**Condition 1 (Control Arm — Answer Only):**
* **Condition Name:** `Condition A: Answer Only`
* **Short description:** `Control group receiving only the AI recommendation without rationale.`
* **Fixed AI Answer Template:** `Recommendation: Approve Loan Application #8841.`
* **Optional AI Explanation Template:** *(leave completely blank)*
* Click **Save Condition**.

**Condition 2 (Treatment Arm — Answer + Explanation):**
* **Condition Name:** `Condition B: Answer + Explanation`
* **Short description:** `Treatment group receiving the AI recommendation plus a structured explanation.`
* **Fixed AI Answer Template:** `Recommendation: Approve Loan Application #8841.`
* **Optional AI Explanation Template:** `Explanation: The applicant meets all three underwriting thresholds (debt-to-income ratio of 24% vs. 36% max limit, 740 credit score, and 4 years of verified employment).`
* Click **Save Condition**.

### Step 3: Attach a Task to Both Conditions (**Design** Tab)
In **Add Task to Condition**, add the task once for `Condition A: Answer Only` and once for `Condition B: Answer + Explanation` (every condition must have at least one task before publishing):
* **Task Title:** `Credit Underwriting Review`
* **Participant instructions:** `Read the applicant summary below, ask the AI assistant for its recommendation, and rate your trust and confidence in the decision.`
* **Decision scenario prompt:** `Applicant #8841 is requesting a €15,000 personal loan. Credit score: 740. Debt-to-income ratio: 24%. Employment tenure: 4 years. Should this application be approved?`
* Click **Add Task** for each condition.

### Step 4: Publish Version `v1` & Generate an Invitation Link
1. Click **Publish Immutable Version** in the top-right header. The badge updates from `draft` to `published` (`v1`).
2. Switch to the **Recruitment** tab, enter a batch label (e.g., `Cohort 1`), and click **Generate Participant Link**.
3. Copy the generated `http://localhost:3000/study/<token>` URL.

### Step 5: Complete a Participant Session
1. Open the copied link in a private/incognito browser tab.
2. Review the study disclosures and click **I Consent & Begin Study**.
3. In the AI chat panel, ask: `What is your recommendation for Applicant #8841?` and click **Send**.
4. Rate the 1–7 Likert items (`trust_rating`, `confidence_rating`, `usefulness_rating`) and click **Submit Responses & Complete Study**.

### Step 6: Inspect Analytics & Download CSV Datasets
1. Return to the researcher tab, refresh the page, and open **Analytics & CSV Exports**.
2. Inspect the live recruitment funnel, condition balance table, per-condition Likert summary statistics (`n`, `mean`, `median`, `SD`, `min–max`), and data-quality flags.
3. Click any dataset button (`participants.csv`, `assignments.csv`, `responses.csv`, `messages.csv`, `events.csv`, `experiment_summary.csv`) to download clean CSV files.

---

## REST API Reference

Base URL: `http://localhost:8000/api/v1`

| Area | Method & Endpoint | Description |
| :--- | :--- | :--- |
| **Health** | `GET /health` | Service and PostgreSQL connectivity check |
| **Auth** | `POST /auth/register` | Register a new researcher account |
| **Auth** | `POST /auth/login` | Authenticate and receive a JWT access token |
| **Auth** | `GET /auth/me` | Retrieve current researcher profile |
| **Experiments** | `GET /experiments` | List experiments owned by the authenticated researcher |
| **Experiments** | `POST /experiments` | Create a new draft experiment |
| **Experiments** | `GET /experiments/{id}` | Get full draft conditions, tasks, and published versions |
| **Experiments** | `POST /experiments/{id}/conditions` | Add an experimental arm to a draft study |
| **Experiments** | `POST /experiments/{id}/tasks` | Attach a task and questionnaire schema to a draft condition |
| **Experiments** | `POST /experiments/{id}/publish` | Validate and freeze an immutable `ExperimentVersion` |
| **Experiments** | `POST /experiments/{id}/pause` / `close` / `archive` | Lifecycle state transitions |
| **Invitations** | `POST /experiments/{id}/invitations` | Generate a SHA-256 hashed participant invitation link |
| **Participant** | `POST /participant/session` | Validate invitation token and issue/resume pseudonymous session |
| **Participant** | `POST /participant/consent` | Record explicit informed consent or decline |
| **Participant** | `POST /participant/assign` | Perform or retrieve persistent uniform random condition assignment |
| **Participant** | `GET /participant/flow` | Fetch current participant step, tasks, chat history, and responses |
| **Participant** | `POST /participant/messages` | Send participant prompt and receive deterministic condition response |
| **Participant** | `POST /participant/responses` | Validate and store Likert/text post-task responses |
| **Participant** | `POST /participant/complete` | Mark study session complete and log completion event |
| **Analytics** | `GET /experiments/{id}/analytics` | Compute funnel, condition balance, descriptive stats, and quality flags |
| **Analytics** | `GET /experiments/{id}/export?dataset=...` | Download formula-escaped, secret-free CSV dataset |

---

## Analytics, Data Quality & CSV Exports

* **Non-Destructive Quality Diagnostics:** Surfaces `INCOMPLETE_SESSION` (consented without completing) and `SPEEDING_DURATION` (completed in under 10 seconds) without mutating or deleting underlying research records.
* **Spreadsheet Formula-Injection Protection:** All CSV exports strip sensitive hashes (`password_hash`, `token_hash`), preserve empty cells rather than coercing missing values to zero, and prefix leading formula triggers (`=`, `+`, `-`, `@`) with a single quote (`'`).

---

## Automated Verification (Pytest & Next.js Build)

### Backend Integration & Unit Tests
```powershell
cd backend
pytest -v
```

### Frontend Production Build Verification
```powershell
cd frontend
npm run build
```

---

## Development Milestones

* [x] **Task 01:** Repository initialization and folder structure
* [x] **Task 02:** PostgreSQL Docker service and FastAPI `/api/v1/health` skeleton
* [x] **Task 03:** Complete 12-table relational schema and initial Alembic migration
* [x] **Task 04:** Researcher authentication (Argon2id + JWT), RBAC, and demo seed script
* [x] **Task 05:** Experiment CRUD, conditions, tasks, and immutable version publishing
* [x] **Task 06:** Participant workflow (invitations, consent gate, persistent random assignment, mock AI chat, ratings, UTC event log)
* [x] **Task 07:** Descriptive analytics, data-quality flags, safe CSV exports, and automated Pytest suite
* [x] **Task 08:** Next.js researcher & participant web interfaces + full Docker Compose stack