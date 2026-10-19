# Project Status — Placement Readiness & Career Intelligence Portal

**Last updated**: 2026-10-20
**Backend tests**: 238 passing (`cd backend && pytest -q`)
**Frontend**: `tsc` clean, `next build` passes; lint has no new errors versus the original pages.

---

## Lab progress (Chapter 9, §9.10)

| Lab | Title | Status | Where | Tests |
|-----|-------|--------|-------|-------|
| 1 | Planner loop (clarify → plan → revise) | ✅ | `services/planner.py`, `POST /planner/clarify`, Career Goal section on `/onboarding` | `test_gap_fixes.py` (clarifying questions) |
| 2 | Tool-using agent | ✅ | Resume parser, role requirements, coding platforms read through typed connectors | `test_pipeline_contract.py` |
| 3 | Reusable skills | ✅ | `agents/coordinator.build_plan` (locked plan), `graph.assemble_draft` (formatter) | `test_lab7_smoke.py` |
| 4 | Memory & retrieval | ✅ | Run state (LangGraph) vs stored knowledge (`knowledge_documents`); tag filters + full-text, re-ranked by a local sentence-embedding model (bge-small, meaning-based); anonymised similar prior students | `test_gap_fixes.py` (retrieval, similar students) |
| 5 | Governed connector | ✅ | `connectors/hub.py` — every agent reads consent, profile, coding data, requirements, jobs and knowledge through it | `tests/fakes.FakeHub` swaps the source with no agent change |
| 6 | Governed runtime | ✅ | Budgets, plan lock, audit log; progress saved to SQLite after every node — interrupted runs resume from the last completed step (on startup, or `POST /workflows/{id}/resume`) | `test_checkpoint_resume.py` |
| 7 | Full node graph | ✅ | `agents/graph.py` — bounded validation → regenerate back-edge | `test_lab7_smoke.py` |
| 8 | Parallel | ✅ | Skill Gap ‖ Coding Analytics per student; batch re-run of many students; best-of-N: 4 roadmap candidates built in parallel, the best by plan alignment is kept | `test_gap_fixes.py`, `test_checkpoint_resume.py` |
| 9 | Evidence grounding | ✅ | Evidence record per output; `GET /evidence` scoped to the owner | `test_pipeline_contract.py` |
| 10 | Self-healing | ✅ | Diagnose → regenerate the failing part → escalate | `test_lab10.py` |
| 11 | Acceptance suite as gate | ✅ | 19 checks; only fully passing runs enter the officer queue (`validation_failed` otherwise) | `test_gap_fixes.py` (validation gate) |
| 12 | Safety & governance | ✅ | Officer-only approve / edit / override (warnings only, reason ≥ 20 chars); versioned publish; rollback re-validated against current consent; server-side sign-out | `test_gap_fixes.py` |
| 13 | Domain specialists | ✅ | Software / analytics / core / higher-studies packs applied in the graph | `test_gap_fixes.py` (specialists) |
| 14 | Capstone | ✅ | Student flow, officer console with inline report, admin page, audit trail | Full suite |

## What changed in this round

- **Chat** answers only from the signed-in student's own published plan.
- **Preparedness self-check** uses the student's own published plan (or own run); with no data it says so instead of scoring a sample profile. Cohort analytics use real published plans only, officer-only.
- **Drives are stored in the database.** Officer-created drives survive restarts and are exactly what the Job Matching Agent matches against; closed drives and passed deadlines are not matched. The five sample companies are now an optional seed (`scripts/seed_sample_drives.py`), labelled "[Sample company]".
- **Rollback** re-runs validation on the old version and refuses (409, audited) if required checks fail or the student has withdrawn a consent the version relies on.
- **Sign-out** revokes the token on the server (`POST /auth/logout`, `revoked_tokens` table); refresh tokens can be revoked too.
- **Admin page** (`/admin`): system stats, create / activate / deactivate staff accounts, audit log. Admins cannot approve plans.
- **Officer report view**: inline readiness signals, cited gaps, matches with confidence and reasoning (low-confidence flagged), roadmap, mock-interview plan, validation results.
- **Mock-interview practice**: students answer questions from their published plan and get feedback — model-generated and labelled when an LLM key is set, otherwise a transparent rubric. Answers are not stored.
- **Roadmap export**: "Download roadmap" on the student roadmap tab.
- **Batch re-run** (Lab 8) is Placement Cell only and uses each student's own resume, roles and current consent.
- Code execution endpoints require sign-in.

## Data sources

| Source | How | Limits |
|--------|-----|--------|
| Resume | Student upload, consent required | — |
| GitHub | Public REST API, consent required | 60 requests/hour without `GITHUB_TOKEN`, 5,000 with |
| LeetCode | Public GraphQL endpoint, consent required | Unofficial; can change without notice — reported as "unavailable", never guessed |
| Academic records | Self-entered CGPA, used only with consent | Not connected to a college system |
| Role requirements | Placement Cell benchmark library (seeded) + drive skill lists | No edit UI for benchmarks yet |
| Knowledge base | PostgreSQL full-text + local hashed embeddings | pgvector supported but not installed |

## Latest additions

- **Resume interrupted runs (Lab 6):** LangGraph progress is saved to `backend/data/checkpoints.sqlite` after every node. A run cut off by a crash resumes from the last completed step automatically when the server starts; a failed run can be resumed by the Placement Cell (`POST /api/v1/workflows/{run_id}/resume`, progress at `GET .../progress`). Earlier steps are not repeated.
- **Best-of-N roadmap (Lab 8):** the Interview Agent builds four roadmap candidates in parallel (gaps first, student priorities first, quick wins first, fit the timeline) and keeps the one that best fits the locked plan (required-gap coverage, ordering, priorities, timeline). All candidate scores are stored and shown in the officer report.
- **Skill benchmark editor:** Placement Cell console → *Skill Benchmarks* — change level / importance, add or remove skills per role; every change is audited and applies to the next analysis.
- **Meaning-based similarity (Lab 4):** a local embedding model (`BAAI/bge-small-en-v1.5` via fastembed, ~64 MB, downloaded once to `backend/data/models`, no API key) re-ranks retrieval and finds similar prior students. Falls back to lexical hashing if the model can't load.
- **Sessions renew automatically:** the 30-minute sign-in token is renewed with a one-time refresh token, so long sessions (e.g. a 45-minute mock test) aren't cut off; refresh tokens rotate and are revoked on sign-out.
- **Mock Interview:** aptitude, verbal, CS fundamentals (DBMS/OS/CN/OOPs), coding, spoken English, essay — chosen question count and timer, graded results, attempt history.

## Known remaining gaps

1. **LLM key** — `LLM_API_KEY` in `.env` is a placeholder; the chat assistant needs a real key, and AI-written summaries / resume extraction / open-answer feedback switch on with it.
2. **Question bank size** — 15 aptitude, 15 verbal, 32 CS, 5 coding, 10 spoken, 8 essay prompts.
3. **Deployment** — runs locally; `docker-compose.yml` has not been tested.
4. Old demo accounts `officer@demo.com` / `student@demo.com` (password `password123`) should be deactivated from `/admin`.
