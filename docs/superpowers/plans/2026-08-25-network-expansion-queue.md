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

**Interfaces:**
- Consumes: `find_new_account_candidates(Session, as_of, new_account_days, low_following_max)`.
- Produces: `refresh_expansion_queue`, `list_expansion_queue`, `promote_expansion_candidate`.

- [ ] Write a failing test that imports observed accounts, refreshes the queue, verifies deduplication, and lists pending candidates.
- [ ] Run the test and confirm failure because the queue model/service does not exist.
- [ ] Implement `ExpansionCandidate` and minimal refresh/list behavior.
- [ ] Run the focused test and full suite.
- [ ] Write a failing promotion test that verifies candidate status and target linkage.
- [ ] Implement promotion without external network calls.
- [ ] Run focused and full tests.

### Task 2: Batch Import + Auto Reanalysis

**Files:**
- Create: `src/xni/analysis/summary.py`
- Modify: `src/xni/analysis/__init__.py`
- Create: `src/xni/services/batch.py`
- Modify: `src/xni/services/__init__.py`
- Test: `tests/test_batch_import.py`

**Interfaces:**
- Consumes: `import_manual_snapshot`, queue refresh, existing similarity/cohort/centrality analyzers.
- Produces: `import_manual_batch(engine, payloads, ...) -> BatchImportResult` and `build_network_summary`.

- [ ] Write a failing test for two target payloads imported sequentially.
- [ ] Verify failure before implementation.
- [ ] Implement batch import by reusing the existing single-snapshot service.
- [ ] Add a query-time summary containing target count, active relationships, queue counts, similarity/cohort counts, and top central nodes.
- [ ] Run focused and full tests.

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

- [ ] Write failing endpoint tests for queue refresh/list/promotion and batch import.
- [ ] Run endpoint tests and confirm expected 404 failures.
- [ ] Wire the services with validation and response models.
- [ ] Run full suite.
- [ ] Document the local workflow and clarify that promotion only creates a local tracking target.
