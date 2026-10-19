# NEXUS

NEXUS is an AI-assisted placement-readiness platform. It combines deterministic
profile analysis with optional LLM-generated summaries, company matching,
personalized roadmaps, mock interviews, and placement-cell workflows.

## Features

- Resume, GitHub, and LeetCode profile analysis
- Evidence-backed skill-gap and placement-readiness assessments
- Company-drive matching and preparedness scoring
- Personalized learning roadmaps
- Mock interview practice and feedback
- Student, placement-officer, and administrator workflows
- Audit-friendly approvals, versioning, and rollback

## Stack

- **Backend:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, LangGraph
- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Infrastructure:** Docker Compose

## Prerequisites

- Python 3.9+
- Node.js and npm
- Docker Desktop with Docker Compose

## Quick start

From the repository root:

```bash
docker compose up -d
```

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set a unique `SECRET_KEY` in `backend/.env`. `LLM_API_KEY` is optional; the
application uses deterministic fallbacks when it is not configured. Optional
connector credentials such as `GITHUB_TOKEN` can also be added there.

Initialize the database and reference data:

```bash
PYTHONPATH=. alembic upgrade head
python -m scripts.seed_reference_data
python -m scripts.seed_sample_drives  # optional demo data
```

Start the API:

```bash
PYTHONPATH=. python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API documentation is available at <http://localhost:8000/docs>.

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The web application is available at <http://localhost:3000>. Set
`NEXT_PUBLIC_API_URL` in `frontend/.env.local` only when the API is not running
at `http://127.0.0.1:8000`.

## Staff accounts

Students register from `/login`. Create administrative or placement-cell
accounts with a password supplied interactively or through the shell:

```bash
cd backend
python -m scripts.create_user --email admin@college.edu \
  --name "Portal Admin" --role admin
python -m scripts.create_user --email tpo@college.edu \
  --name "Placement Cell" --role placement_officer
```

Never put passwords, API keys, or production secrets in source control.

## Tests and checks

```bash
cd backend
pytest -q

cd ../frontend
npm run lint
npm run build
```

Backend tests require a reachable PostgreSQL instance. Docker Compose provides
the expected local PostgreSQL and Redis services.

## Repository layout

```text
backend/
  app/                 FastAPI application, agents, connectors, and services
  alembic/             Database migrations
  scripts/             Setup and seed commands
  tests/               Unit, integration, and acceptance tests
frontend/
  src/app/             Next.js routes and pages
  src/components/      Reusable UI components
  src/lib/             Frontend API and utility modules
docs/                  Architecture, API, security, and delivery documentation
docker-compose.yml     Local PostgreSQL and Redis services
```

## Git hygiene

Local environment files, uploads, checkpoints, databases, caches, build
outputs, and editor configuration are ignored. Commit source code,
migrations, tests, documentation, and lockfiles; do not commit `.env`,
credentials, generated runtime data, or dependency directories.
