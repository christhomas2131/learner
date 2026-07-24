# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The archetypal user is a **professional / analyst** — legal, medical, compliance,
or research work — who needs cited, defensible answers pulled only from an
approved corpus, and who is accountable for what those answers claim.

Currently Learner is operated as a **personal working tool**: a single expert
operator (the author) asking questions over their own approved materials.
Future work should optimize for one knowledgeable operator working a corpus they
control, not a polished multi-user launch. Function outranks polish.

## Product Purpose

Learner answers questions **only from approved source material**, verifies every
factual claim against a cited quotation, shows its evidence, and **abstains when
the evidence isn't there**. The guarantee is not "the model is right." It is:
*nothing is released as verified unless the approved evidence actually supports
it.* Success is a trustworthy, auditable answer with zero unsupported claims
released — aggressive abstention is preferred over confident error.

## Positioning

A **deterministic Python state machine owns the pipeline and the release gate**;
the model only drafts and judges and can never mark its own output verified.
Every quotation is checked character-for-character (normalized substring match)
against an approved passage before anything is called Verified. This
"Python-in-charge, model-can't-self-certify" mechanism is the differentiator a
neighboring RAG chatbot could not truthfully copy. It also runs with **no API
key** — Grounded mode uses no model at all; Premium mode uses a running Claude
Code worker session on the user's own Claude subscription.

## Operating Context

- Two ask modes run through the **identical Python gate**:
  - **Grounded** (default, always on): instant, deterministic, no model; answers
    are extractive, assembled from exact quotes of approved passages.
  - **Premium**: a fluent answer drafted and verified by a running Claude Code
    worker session; the harness still validates every quotation and applies the
    release gate.
- Every question resolves to one of **four outcomes**: Verified, Insufficient
  Evidence, Contradiction Detected, or Error.
- Pipeline stages (Python owns every transition): VALIDATE_INPUT →
  RESOLVE_DETERMINISTIC → RETRIEVE → DRAFT → EXTRACT_CLAIMS → VERIFY_CLAIMS →
  REVISE → RELEASE_GATE → PERSIST_AUDIT → COMPLETE.
- The corpus is **approved sources only** (source status `APPROVED`), retrieved
  via SQLite FTS5; the operator curates this material.
- Every released answer persists an **immutable audit snapshot**.
- Current surfaces: Ask workspace, Library (sources), Progress, Sessions
  (history), Settings.

## Capabilities and Constraints

- **Deterministic resolvers** handle arithmetic, percentages, dates, unit
  conversions, exact definitions, and answer-keys with `Decimal` precision and
  no model.
- **Retrieval** returns only `APPROVED` passages.
- **Verify** is an independent pass classifying each claim `SUPPORTED` /
  `CONTRADICTED` / `INSUFFICIENT_EVIDENCE`; a "supported" verdict with no real
  quotation is downgraded automatically.
- The **release gate is pure Python and cannot be bypassed.**
- **Contradiction detection**: a conservative deterministic detector in Grounded
  mode; subtler semantic conflicts are caught by the model verifier in Premium.
- **Honest limits future work must not overstate:** Learner guarantees only that
  *released claims are supported by the approved evidence available to it* — not
  universal truth. Incomplete or incorrect approved sources can still yield
  incomplete or incorrect conclusions (hence aggressive abstention). Grounded
  answers are extractive and may read bluntly or carry source formatting.
- Stack: FastAPI + SQLAlchemy + Alembic + the verification engine (backend);
  Next.js App Router + Tailwind (frontend); SQLite. A desktop packaging target
  also exists.

## Brand Commitments

None binding yet. The name "Learner," voice, and identity are current working
choices, not locked constraints — future work is free to decide them. (Recorded
so this is not re-asked; not an invitation to fabricate identity.)

## Evidence on Hand

- `README.md` — authoritative description of the architecture and guarantees.
- Demo/seed data via `python -m app.cli seed` (e.g. the "What is
  photosynthesis?" example).
- **No** real customers, testimonials, benchmarks, pricing, or production
  deployment claims exist. Future work must not fabricate any of these.

## Product Principles

1. **Evidence over eloquence.** A claim without a matching approved quotation
   does not ship; abstention beats confident error.
2. **Python owns the verdict.** The model drafts and judges but never
   self-certifies; the release gate is authoritative and unbypassable.
3. **Show the work.** Every released answer exposes its citations, status, and
   audit trail — trust is earned by visible evidence, not asserted.
4. **Honest about limits.** The interface states what "Verified" does and does
   not mean; it never implies universal truth.
5. **Single-operator, corpus-first.** Optimized for one expert working over
   their own approved materials; the source corpus is the product's spine.
