# Financial Mirror

> **GoTyme Hackathon 2026 — Financial Services Track II (P5/P6)**

A **governed non-advisory financial insight platform** that transforms raw transaction data into safe, compliant educational nudges and engagement challenges — without ever giving personalized financial advice.

---

## 🏗 Architecture

```
User Browser
  → Next.js Frontend (port 3000)
  → FastAPI Backend (port 8000)
     → FinancialMirrorAgent (governed agentic pipeline)
        → Data Checker → Fact Engine → Policy Engine
        → LLM Action Selector (Gemini / Groq fallback)
        → LLM Wording Generator → Safety Gate 1
        → Engagement Engine → Safety Gate 2
        → Audit Logger
```

## 🚀 Quick Start

### 1. Install dependencies

```bash
# Python (backend)
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r backend/requirements.txt

# Node (frontend)
cd frontend
npm install
```

### 2. Configure environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and fill in your API keys
```

Required variables:
| Variable | Description |
|---|---|
| `LLM_PROVIDER` | `gemini` or `groq` or `mock` |
| `GEMINI_API_KEY` | Google Gemini API key |
| `LLM_FALLBACK_PROVIDER` | `groq` (auto-fallback when Gemini 503/429) |
| `GROQ_API_KEY` | Groq API key |

### 3. Run locally

```bash
# From project root
python run_app.py
```

- **Backend API**: http://localhost:8000  
- **Frontend Dashboard**: http://localhost:3000  
- **API Docs**: http://localhost:8000/docs

### 4. Run demo CLI

```bash
cd backend
python run_demo.py --customer maria   # published
python run_demo.py --customer dana    # blocked_by_safety
python run_demo.py --customer juan    # rejected_by_policy
python run_demo.py --customer fina    # safety retry → recovered
```

---

## 🧪 Tests

```bash
pytest backend/tests/test_main.py -v
```

13 tests covering all 9 personas + audit logs.

---

## 🔑 Key Design Principles

1. **No LLM for rule engines** — Fact/Policy/Safety engines are 100% deterministic rule-based.
2. **Every fact has evidence** — fully traceable to raw transaction data.
3. **Safety Gate is mandatory** — no user-facing output bypasses the safety check.
4. **No financial advice** — prohibited phrases enforced at engine level.
5. **LLM fallback resilience** — Gemini → Groq automatic failover.
6. **MOCK_LLM=true always works** — demo never depends on cloud availability.

---

## 📁 Project Structure

```
financial-mirror/
├── backend/
│   ├── app/
│   │   ├── agents/         # FinancialMirrorAgent (governed agentic pipeline)
│   │   ├── data/           # Mock customer data, product catalog, audit store
│   │   ├── engines/        # Fact, Policy, Safety, LLM, Engagement engines
│   │   └── models/         # Pydantic schemas
│   ├── tests/
│   ├── run_demo.py
│   └── .env.example
├── frontend/               # Next.js governance & explainability dashboard
├── run_app.py              # One-command local runner
└── AGENTS.md               # Rules for AI coding agents working in this repo
```
