# Financial Mirror

Financial Mirror is a governed, non-advisory financial insight and engagement engine for the GoTyme Hackathon 2026 Financial Services Track II, combining P5 integrated financial life insights and P6 adaptive engagement challenges.

## Problem Statement

Banks and digital finance apps hold rich customer data across spending, saving, borrowing, investing, and app usage, but customers rarely see that data translated into useful, safe, and explainable financial-health observations.

At the same time, static rewards and campaigns do not adapt well to different user behaviors. A beginner may feel overwhelmed, while a power user may disengage.

The core constraint: the product must never provide personalized financial advice. It should surface factual observations, educational nudges, and safe challenges only.

## Solution

Financial Mirror turns raw customer data into:

- Evidence-backed financial observations.
- Non-advisory educational nudges.
- Behavior-adaptive engagement challenges.
- Full policy, safety, and audit traces for explainability.

The system is not a generic chatbot. Facts, policy, safety, and audit decisions are deterministic and traceable. LLMs are only used for constrained action selection and wording generation after rule-based gates approve the candidate.

## Architecture

```text
User Browser
  -> Next.js Frontend
  -> FastAPI Backend
     -> FinancialMirrorAgent
        -> Customer Data Provider: mock or Supabase
        -> Data Checker
        -> Fact / Pattern Engine
        -> Policy Engine
        -> LLM Action Selector
        -> LLM Wording Generator
        -> Safety Gate 1: observation and nudge
        -> Engagement Engine
        -> Safety Gate 2: challenge and reward wording
        -> Audit Logger / Supabase Persistence
```

## Agentic Workflow

1. Load customer data from mock fixtures or Supabase.
2. Check whether required data groups are present.
3. Generate deterministic facts with evidence IDs or evidence notes.
4. Evaluate policy eligibility and product scope.
5. Ask the LLM to choose only from governed candidate actions.
6. Generate non-advisory wording only for policy-approved facts.
7. Run Safety Gate 1 before any observation or nudge is publishable.
8. If wording fails Safety Gate 1, run one governed rewrite retry using the same fact and policy result.
9. Generate adaptive challenges only after safe nudges pass.
10. Run Safety Gate 2 for challenge and reward wording.
11. Persist traceable run and audit entries when enabled.

Safety retry applies only to observation and nudge wording. Challenge safety failures are blocked immediately in this MVP.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Pydantic |
| Frontend | Next.js, React, Tailwind CSS |
| Data | Mock fixtures or Supabase Postgres via REST |
| LLM | Mock provider, Gemini, Groq fallback |
| Persistence | Supabase `pipeline_runs` and `audit_entries` |
| Deployment | Docker, Docker Compose, Render/Railway/Fly/Cloud Run, Vercel |

## Environment Variables

Create `backend/.env` from `backend/.env.example`.

```bash
copy backend\.env.example backend\.env
```

Backend variables:

| Variable | Default | Description |
|---|---:|---|
| `DATA_SOURCE` | `mock` | `mock` or `supabase`. |
| `PERSIST_RUNS` | `false` | Set `true` to write `pipeline_runs` and `audit_entries` to Supabase. |
| `ALLOW_MOCK_FALLBACK` | `false` | Set `true` to fallback to mock data if Supabase has no customer row. |
| `SUPABASE_URL` | none | Supabase Project URL, for example `https://your-project.supabase.co`. |
| `SUPABASE_ANON_KEY` | none | Optional publishable key for read-only/public Supabase client paths if enabled. |
| `SUPABASE_SERVICE_ROLE_KEY` | none | Backend-only key used for Supabase runtime loading and persistence. Never expose this in frontend. |
| `LLM_PROVIDER` | `mock` | `mock`, `gemini`, or `groq`. |
| `GEMINI_API_KEY` | none | Required when `LLM_PROVIDER=gemini`. |
| `LLM_FALLBACK_PROVIDER` | none | Optional fallback, for example `groq`. |
| `GROQ_API_KEY` | none | Required when using Groq. |

Frontend variable:

| Variable | Default | Description |
|---|---:|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api` | Public browser API base URL. |

Local mock mode:

```env
DATA_SOURCE=mock
PERSIST_RUNS=false
ALLOW_MOCK_FALLBACK=false
LLM_PROVIDER=mock
```

Supabase demo mode:

```env
DATA_SOURCE=supabase
PERSIST_RUNS=true
ALLOW_MOCK_FALLBACK=false
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_optional_publishable_key
SUPABASE_SERVICE_ROLE_KEY=your_backend_service_role_key
LLM_PROVIDER=mock
```

## How To Run Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend URLs:

- API root: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## How To Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

- Dashboard: `http://localhost:3000`

If the backend is not running at `http://localhost:8000`, set:

```bash
set NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

## One-Command Local Runner

From the project root:

```bash
python run_app.py
```

This starts the FastAPI backend and Next.js frontend together for local demos.

## Docker

```bash
docker compose up --build
```

Backend only:

```bash
docker build -t financial-mirror-backend ./backend
docker run --env-file backend/.env -p 8000:8000 financial-mirror-backend
```

Frontend only:

```bash
docker build -t financial-mirror-frontend ./frontend --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000/api
docker run -p 3000:3000 financial-mirror-frontend
```

## Supabase Setup

The Supabase project should contain these seeded tables:

- `customers`
- `customer_profiles`
- `transactions`
- `savings_balances`
- `borrowings`
- `investment_holdings`
- `app_usage_events`
- `persona_registry`
- `pipeline_runs`
- `audit_entries`

Runtime behavior:

- `DATA_SOURCE=mock` uses local mock personas.
- `DATA_SOURCE=supabase` resolves persona keys such as `maria` through `persona_registry`.
- `PERSIST_RUNS=true` writes one row to `pipeline_runs` and related rows to `audit_entries`.

## LLM Setup

For local or reliable demo mode, use:

```env
LLM_PROVIDER=mock
```

For real LLM mode:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key
LLM_FALLBACK_PROVIDER=groq
GROQ_API_KEY=your_key
```

LLM usage is constrained:

- No LLM in Fact Engine.
- No LLM in Policy Engine.
- No LLM in Safety Engine.
- LLM only selects from allowed agent actions and drafts wording after policy approval.

## Demo Personas

| Persona | Expected Path | Purpose |
|---|---|---|
| `maria` | `published` | Happy path with safe nudges and challenges. |
| `elena` | `published` | Power user adaptive engagement path. |
| `fina` | `published` | Safety retry recovery path. |
| `dana` | `blocked_by_safety` | Unsafe wording remains blocked after retry. |
| `juan` | `rejected_by_policy` | User opted out of education nudges. |
| `alex` | `rejected_by_policy` | Out-of-scope crypto product path. |
| `carlo` | `rejected_by_policy` | KYC incomplete policy rejection. |
| `niko` | `rejected_by_policy` | Under-18 eligibility rejection. |
| `bea` | `no_facts` | Missing data path. |

CLI examples:

```bash
cd backend
python run_demo.py --customer maria
python run_demo.py --customer elena
python run_demo.py --customer fina
python run_demo.py --customer dana
python run_demo.py --customer juan
python run_demo.py --customer alex
python run_demo.py --customer carlo
python run_demo.py --customer niko
python run_demo.py --customer bea
```

## Tests

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest tests
```

Current expected result: `13 passed`.

## Current Validation Status

- Backend tests: `13 passed`.
- Real LLM mode: Gemini primary with Groq fallback.
- Supabase runtime data source: Maria loads from Supabase and publishes successfully.
- Supabase persistence: `pipeline_runs` and `audit_entries` are written when `PERSIST_RUNS=true`.
- Governance stress test: 9 personas validated across published, retry recovery, safety block, policy rejection, and no-facts paths.

## Deployment Notes

Backend deployment environment:

```env
APP_ENV=demo

DATA_SOURCE=supabase
PERSIST_RUNS=true
ALLOW_MOCK_FALLBACK=true

SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...

LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GEMINI_API_KEY=...

LLM_FALLBACK_PROVIDER=groq
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
```

`ALLOW_MOCK_FALLBACK=true` keeps the deployed demo resilient if Supabase data is temporarily unavailable. The execution trace still records whether fallback was used.

Frontend deployment environment:

```env
NEXT_PUBLIC_API_URL=https://your-backend.example.com/api
```

Production smoke checks:

```bash
curl https://your-backend.example.com/
curl https://your-backend.example.com/api/customers
```

Then open the frontend URL, select Maria, run the pipeline, and verify the final status is `published`.

## Security Before Push

This repository is intended to be public for submission. Before pushing, verify no secrets are tracked:

```bash
git status --short
git ls-files | findstr /i ".env"
git grep -n "GEMINI_API_KEY\|GROQ_API_KEY\|SUPABASE_SERVICE_ROLE_KEY\|DATABASE_URL\|sb_publishable_"
```

Do not commit:

- `.env`
- `backend/.env`
- `frontend/.env.local`
- real `GEMINI_API_KEY`
- real `GROQ_API_KEY`
- real `SUPABASE_SERVICE_ROLE_KEY`
- real `DATABASE_URL`

Only commit safe examples such as `backend/.env.example`.

## Disclosure

Some initial project planning, schema design, mock data scaffolding, and local prototype work were prepared before the final submission period. During the hackathon build, the project was extended into a working governed agentic pipeline with Supabase-backed runtime data loading, deterministic policy and safety gates, LLM-assisted wording/action selection, audit logging, and a Next.js governance dashboard.

No external proprietary code or private third-party assets are included. All demo data is fictional and used only for hackathon demonstration purposes.

## Demo Recording Checklist

1. Start from a clean browser tab on the deployed frontend.
2. Show the persona list and select Maria.
3. Click `Run Pipeline`.
4. Show `published`, facts, policy decisions, safety gates, and challenge cards.
5. Open execution trace or LLM decisions to show governed agent behavior.
6. Refresh audit logs and show persisted audit rows.
7. Optional contrast: run Juan for policy rejection or Dana for safety block.
