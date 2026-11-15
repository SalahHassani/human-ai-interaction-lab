# Human–AI Interaction Lab (HAI-Lab)

A full-stack research platform for designing controlled human–AI interaction experiments, collecting participant responses, logging interactions, and analysing experimental outcomes.

## Tech Stack
- **Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS
- **Backend:** Python 3.12, FastAPI, Pydantic, SQLAlchemy 2.0, Alembic, Pandas, Pytest
- **Database:** PostgreSQL 16
- **Infrastructure:** Docker & Docker Compose

## Progress & Roadmap
- [x] **Task 01:** Repository initialization and folder structure
- [x] **Task 02:** PostgreSQL Docker service and FastAPI `/api/v1/health` skeleton
- [x] **Task 03:** Complete 12-table relational schema and initial Alembic migration
- [x] **Task 04:** Researcher authentication (Argon2id + JWT), RBAC, and demo seed script
- [x] **Task 05:** Experiment CRUD, conditions, tasks, and immutable version publishing
- [x] **Task 06:** Participant workflow (invitations, consent gate, persistent random assignment, mock AI chat, ratings, UTC event log)
- [x] **Task 07:** Descriptive analytics, data-quality flags, safe CSV exports, and automated Pytest suite
- [x] **Task 08:** Next.js researcher & participant web interfaces + full Docker Compose stack

## Demo Credentials (Seeded)
- **Email:** `researcher@hailab.org`
- **Password:** `Researcher123!`

## Running Locally (Development)
1. **Start PostgreSQL:** `docker compose up -d db`
2. **Backend API:**
   ```powershell
   cd backend
   .\.venv\Scripts\Activate.ps1
   alembic upgrade head
   python ..\database\seed\seed_demo.py
   uvicorn app.main:app --reload --port 8000