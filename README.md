# Human–AI Interaction Lab (HAI-Lab)

A full-stack research platform for designing controlled human–AI interaction experiments, collecting participant responses, logging interactions, and analysing experimental outcomes.

## Tech Stack
- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Backend:** Python 3.12, FastAPI, Pydantic, SQLAlchemy 2.0, Alembic
- **Database:** PostgreSQL 16
- **Infrastructure:** Docker & Docker Compose

## Progress & Roadmap
- [x] **Task 01:** Repository initialization and folder structure
- [x] **Task 02:** PostgreSQL Docker service and FastAPI `/api/v1/health` skeleton
- [x] **Task 03:** Complete 12-table relational schema and initial Alembic migration
- [x] **Task 04:** Researcher authentication (Argon2id + JWT), RBAC, and demo seed script
- [x] **Task 05:** Experiment CRUD, conditions, tasks, and immutable version publishing
- [ ] **Task 06:** Participant workflow (invitations, consent gate, persistent random assignment, mock AI chat, ratings, UTC event log)
- [ ] **Task 07:** Descriptive analytics, data-quality flags, and CSV exports
- [ ] **Task 08:** Next.js researcher & participant web interfaces + full Docker Compose stack

## Demo Credentials (Seeded)
- **Email:** `researcher@hailab.org`
- **Password:** `Researcher123!`

## Quick Local Setup
1. Start PostgreSQL: `docker compose up -d db`
2. Activate Python environment: `.\backend\.venv\Scripts\Activate.ps1`
3. Run migrations: `cd backend && alembic upgrade head && cd ..`
4. Seed demo data: `python database\seed\seed_demo.py`
5. Start API: `cd backend && uvicorn app.main:app --reload --port 8000`