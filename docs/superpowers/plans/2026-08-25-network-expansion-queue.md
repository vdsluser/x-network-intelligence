# Network Expansion Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn discovered new/low-following accounts into a persistent expansion queue, promote selected candidates to tracked targets, import multiple target snapshots in one request, and return a refreshed network-analysis summary after import.

**Architecture:** SQLite remains the source of truth. `ExpansionCandidate` stores a durable queue entry linked to an observed account; a queue service refreshes candidates from the existing new-account analyzer and promotes a queue item by creating/updating a `Target`. Batch manual import reuses the existing snapshot transaction per payload, then refreshes the queue and computes a lightweight query-time analysis summary instead of persisting derived scores.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2, Pydantic 2, SQLite, NetworkX, pytest

**Spec:** `docs/PROJECT_PLAN.md`

## Global Constraints

- Local-first; SQLite is the source of truth.
- Queue items are evidence-backed candidates, not claims that an account is coordinated or organizational.
- Promotion never follows an account or calls X; it only marks an observed account as a tracked local target.
- Existing snapshot/import behavior and analysis APIs must remain compatible.
- Derived network analysis stays query-time in this phase; do not persist centrality or similarity scores yet.

---

### Task 1: Persistent Expansion Queue

**Files:**
- Modify: `src/xni/models.py`
- Create: `src/xni/services/expansion.py`
- Modify: `src/xni/services/__init__.py`
- Test: `tests/test_expansion_queue.py`

### Task 2: Batch Import + Auto Reanalysis

**Files:**
- Create: `src/xni/analysis/summary.py`
- Modify: `src/xni/analysis/__init__.py`
- Create: `src/xni/services/batch.py`
- Modify: `src/xni/services/__init__.py`
- Test: `tests/test_batch_import.py`

### Task 3: FastAPI Expansion Workflow

**Files:**
- Modify: `src/xni/app.py`
- Modify: `README.md`
- Test: `tests/test_app.py`

**Interfaces:**
- `POST /api/expansion/queue/refresh`
- `GET /api/expansion/queue`
- `POST /api/expansion/queue/{candidate_id}/promote`
- `POST /api/import/manual/batch`
