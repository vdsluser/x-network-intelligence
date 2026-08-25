# Manual Import + Snapshot Diff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import a Sorsa-style following JSON payload manually, persist every account and raw snapshot in SQLite, and return added/removed/unchanged following relationships compared with the previous snapshot.

**Architecture:** `ManualImportProvider` validates and normalizes a pasted JSON object into `NetworkAccount` models while retaining raw user records. A snapshot service performs one SQLAlchemy transaction that upserts target/accounts, stores snapshot membership and raw JSON, updates current relationships, and records relationship events. FastAPI exposes this through `POST /api/import/manual`.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2, Pydantic 2, SQLite, pytest

**Spec:** `docs/PROJECT_PLAN.md`

## Global Constraints

- Local-first; SQLite remains the source of truth.
- Preserve source JSON needed for later re-analysis.
- Provider-specific shapes must not leak into analysis modules.
- A missing account in one snapshot is reported as a relationship removal observation, not as proof of why the follow ended.
- Tests must cover first import and a second changed snapshot.

---

### Task 1: ManualImportProvider

**Files:**
- Create: `src/xni/providers/manual.py`
- Modify: `src/xni/providers/__init__.py`
- Test: `tests/test_manual_provider.py`

- [ ] Write tests for Sorsa field mapping and mode validation.
- [ ] Run tests and confirm they fail because the provider does not exist.
- [ ] Implement minimal validation and normalization.
- [ ] Run provider tests and full suite.

### Task 2: Snapshot persistence and diff

**Files:**
- Modify: `src/xni/models.py`
- Create: `src/xni/services/__init__.py`
- Create: `src/xni/services/snapshots.py`
- Test: `tests/test_snapshot_import.py`

- [ ] Write first-import test asserting account metadata, raw JSON, active relationships and all-added diff.
- [ ] Run test and confirm failure from missing models/service.
- [ ] Implement schema and transactional import.
- [ ] Write second-import test with one retained, one removed and one added account.
- [ ] Run test and confirm the expected diff and event history.
- [ ] Run full suite.

### Task 3: FastAPI manual import endpoint

**Files:**
- Modify: `src/xni/app.py`
- Test: `tests/test_app.py`
- Modify: `README.md`

- [ ] Write endpoint test using a temporary SQLite database.
- [ ] Run test and confirm failure before endpoint exists.
- [ ] Add endpoint using the existing configured SQLite engine.
- [ ] Run endpoint test and full suite.
- [ ] Document curl/import usage and explain that raw payloads are retained locally.
