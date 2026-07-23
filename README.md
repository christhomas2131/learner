# Learner — verified, low-hallucination learning

Learner answers questions **only from approved source material**, verifies **every
factual claim** against a cited quotation, shows its evidence, and **abstains when
the evidence isn't there.** The guarantee is not "the model is right." The
guarantee is: *nothing is released as verified unless the approved evidence
actually supports it.*

The core idea: a **deterministic Python state machine is in charge**, not the
model. The model drafts and judges; Python owns stage order, matches every
quotation character-for-character against an approved passage, and is the sole
authority at the release gate. The model can never mark its own output verified.

---

## What you get

Four possible outcomes for any question:

| Status | Meaning |
| --- | --- |
| **Verified** | Every material claim is supported by an approved source quotation. |
| **Insufficient Evidence** | The approved materials don't support an answer. It abstains. |
| **Contradiction Detected** | Approved sources conflict; no side is silently chosen. |
| **Error** | Verification could not complete safely. |

Two ways to ask, both through the identical Python gate:

- **Grounded** (default, always on): an instant answer assembled from exact
  quotes of approved passages. No model, no API key, fully deterministic. Blunt
  prose, zero hallucination.
- **Premium**: a fluent answer drafted and verified by a running **Claude Code
  worker session** — your Claude subscription, no API key. The harness still
  validates every quotation and applies the release gate.

---

## Architecture

```
Question
  │
  ▼  (Python owns every transition)
VALIDATE_INPUT → RESOLVE_DETERMINISTIC → RETRIEVE → DRAFT → EXTRACT_CLAIMS
   → VERIFY_CLAIMS → REVISE → RELEASE_GATE → PERSIST_AUDIT → COMPLETE
```

- **Deterministic resolvers** answer arithmetic / percentages / dates / unit
  conversions / exact definitions / answer-keys with no model at all (`Decimal`
  precision).
- **Retrieval** returns only passages whose source is `APPROVED` (SQLite FTS5).
- **Draft** produces atomic claims, each citing approved passage IDs. Malformed
  drafts are rejected and retried within a bounded limit.
- **Verify** is an independent pass: each claim is classified `SUPPORTED` /
  `CONTRADICTED` / `INSUFFICIENT_EVIDENCE`, and **every quotation is checked by
  normalized substring match** against the cited approved passage. A "supported"
  verdict with no real quotation is downgraded automatically.
- **Release gate** (pure Python) decides the final status. It cannot be bypassed.
- **Audit** persists an immutable snapshot of every answer.

```
backend/   FastAPI + SQLAlchemy + Alembic + the verification engine
frontend/  Next.js (App Router) + Tailwind + the answer workspace
```

### Verification guarantees — and their limits

- Learner guarantees only that **released claims are supported by the approved
  evidence available to it.** No AI system can guarantee universal truth.
- **Incomplete or incorrect approved sources can still produce incomplete or
  incorrect conclusions.** Learner therefore abstains aggressively.
- **Contradiction detection** works in Grounded (no-model) mode via a
  conservative deterministic detector: a claim is flagged when a *different*
  approved source negates it with enough shared content. Subtler semantic
  conflicts (e.g. "dwarf planet" vs "planet" without an explicit negation) are
  caught by the model verifier in Premium mode.
- Grounded answers are **extractive** (stitched exact quotes); they may read
  bluntly and occasionally include source formatting.

---

## Quick start (no Docker, no API key)

Prereqs: Python 3.11+, Node 20+.

```bash
# 1. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m app.cli seed            # creates SQLite DB + demo data
uvicorn app.main:app --reload --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local        # points at http://localhost:8000
npm run dev                       # http://localhost:3000
```

Open http://localhost:3000 and ask *"What is photosynthesis?"* (Grounded).

### With Make

```bash
make install        # both projects
make seed
make dev            # backend + frontend together
make test           # backend + frontend unit tests
make lint typecheck build
```

Windows PowerShell (no Make): run the commands in the Quick start block
directly (use `.venv\Scripts\Activate.ps1` to activate the venv).

### Try it from the terminal

```bash
cd backend && source .venv/bin/activate
python -m app.cli ask "What is 15% of 240?"          # deterministic → VERIFIED
python -m app.cli ask "What is photosynthesis?"      # cited → VERIFIED
python -m app.cli ask "Who won the 2050 World Cup?"  # abstains → INSUFFICIENT
```

---

## Premium answers via your Claude subscription (no API key)

Premium answers are drafted and verified by Claude Code — **powered by your
subscription, no API key**. There are two ways it runs:

**Hands-off (default).** If the `claude` CLI is installed and logged in, the API
auto-drains the premium queue in-process via headless `claude -p`. Just pick
**Premium** in the UI and ask — the worker badge shows online and the answer
appears on its own. Nothing to run. (Toggle with `PREMIUM_AUTODRAIN`.)

**Manual worker** (fallback / no CLI, or to drive drafting yourself):

```bash
cd backend && source .venv/bin/activate
python -m app.cli worker-serve                 # keep-alive loop: heartbeat + auto-answer
# — or step through one item —
python -m app.cli worker-prep <queue_id>       # retrieves passages, prints the draft prompt
python -m app.cli worker-finish <queue_id> draft.json verify.json
```

Either way the identical harness validates every quotation and applies the
release gate. The `claude -p` path uses your subscription login (non-`--bare`
mode); no `ANTHROPIC_API_KEY` is set. A key-based path
(`MODEL_PROVIDER=anthropic`) is scaffolded but disabled by default.

---

## API overview

Base: `/api/v1`. OpenAPI docs at `http://localhost:8000/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/answers` | Ask (grounded inline, or enqueue premium) |
| POST | `/answers/stream` | Ask with SSE pipeline events |
| GET | `/answers/{id}` | Fetch a persisted answer |
| GET/POST | `/sessions` … | Session CRUD |
| GET/POST | `/sources` … | Library: upload, approve, reject, reindex, passages |
| GET/POST | `/subjects` | Subjects |
| GET | `/analytics` | Learning + operational metrics |
| GET | `/queue`, `/queue/{id}` | Premium queue status |
| GET | `/health`, `/ready` | Liveness / readiness |

---

## Source approval workflow

Uploaded material is **never trusted automatically**. Every source moves
`UPLOADED → PROCESSING → PENDING_APPROVAL`, and must be explicitly **approved**
in the Knowledge Library before retrieval can use it. Files are stored outside
any public folder, deduplicated by content hash, and empty documents are
rejected. Supported types: Markdown, TXT, PDF, DOCX, plus structured records and
answer keys.

---

## Database & migrations

SQLite by default (zero setup). Timestamps are UTC; primary keys are UUIDs.

```bash
cd backend
alembic upgrade head                          # apply migrations
alembic revision --autogenerate -m "message"  # new migration
```

Retrieval works on **both** backends, chosen by DB dialect: **SQLite FTS5**
locally, **Postgres `tsvector`/`ts_rank`** (GIN-indexed) for `DATABASE_URL`
pointing at Postgres (`pip install -e ".[postgres]"` for the async driver).
Semantic vectors are DB-agnostic, so hybrid retrieval works on both.

---

## Docker

> ⚠️ The Docker/Compose files are written but **not run-verified** (Docker was
> not available in the build environment). Treat them as a starting point.

```bash
docker compose up --build        # backend :8000 (SQLite volume), frontend :3000
```

---

## Testing

```bash
make test-backend     # pytest — engine, gate, resolvers, ingestion, API, SSE, queue
make test-frontend    # vitest + React Testing Library
make test-e2e         # Playwright (run `npx playwright install chromium` first)
```

All tests run with **no paid API** (`MODEL_PROVIDER=none`) on deterministic
fixtures. CI (GitHub Actions) runs backend lint/type/test, frontend
lint/type/test/build, and Playwright E2E.

---

## Security notes

Restricted CORS, secure HTTP headers, request-size and upload-size limits,
filename sanitization, MIME/extension checks, content-hash validation,
parameterized queries, ownership checks, safe structured errors (no stack traces
to clients), no secrets in the repo, no unsafe HTML rendering, no executable
uploads, uploads never publicly served. Developer diagnostics show only safe
metadata (request/audit IDs, timing) — never prompts, keys, or model reasoning.

---

## Troubleshooting

- **"Cannot reach the backend"** — start the backend on :8000; check
  `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local`.
- **Empty answers / everything abstains** — you probably have no *approved*
  sources. Run `python -m app.cli seed`, or approve sources in the Library.
- **Premium question stuck "Queued"** — start a Claude Code worker and run
  `worker-prep` / `worker-finish` (see above). Nothing else can produce Premium
  answers.

---

## Known limitations

- Grounded contradiction detection is a conservative negation heuristic; subtle
  semantic conflicts need Premium (the model verifier).
- Grounded answers are extractive, not fluent.
- Single-user, no authentication (personal local deployment by design).
- Docker artifacts unverified in this environment.
