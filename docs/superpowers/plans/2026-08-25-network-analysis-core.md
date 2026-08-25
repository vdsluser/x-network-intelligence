# Network Analysis Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first on-demand analysis engine for new-account candidates, following similarity/cohort candidates, and central nodes from locally stored SQLite relationship data.

**Architecture:** Analysis remains read-only and computed on demand from `Account`, `Target`, and active `TargetRelationship` rows. `profiles.py` handles account-age/following heuristics, `network.py` converts active target→account relations into comparable following sets and Jaccard scores, and `centrality.py` uses NetworkX on the bipartite target/account graph to rank hubs and bridge candidates. FastAPI exposes read-only endpoints; no analysis tables are added yet.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2, SQLite, Pydantic 2, NetworkX 3.4+, pytest

**Spec:** `docs/PROJECT_PLAN.md`

## Global Constraints

- Local-first; SQLite remains the source of truth.
- Analysis must use observable profile/network facts and must not label an account as an organization, coordinated actor, or political ideology.
- New-account and low-following cutoffs are heuristics and must be explicit/configurable in function/API parameters.
- Similarity is based on active following relationships and returns evidence: shared count, union count, Jaccard, and per-side overlap ratios.
- Central-node output must include the measurable reason for ranking: target coverage/in-degree and betweenness where available.
- No GitHub Actions workflows are added or run.

---

### Task 1: New-account candidate analysis

**Files:**
- Create: `src/xni/analysis/__init__.py`
- Create: `src/xni/analysis/profiles.py`
- Test: `tests/test_profile_analysis.py`

**Interfaces:**
- Consumes: `Account.created_at`, `Account.following_count`, `Account.followers_count`, `Account.tweets_count`
- Produces: `AccountProfileSignal`, `analyze_account_profile(account, *, as_of, new_account_days, low_following_max)` and `find_new_account_candidates(session, ...)`

- [ ] **Step 1: Write failing tests** for deterministic `age_days`, `is_new_account`, `is_low_following`, and candidate filtering with explicit thresholds.
- [ ] **Step 2: Run** `pytest tests/test_profile_analysis.py -v` and confirm import/function failures.
- [ ] **Step 3: Implement minimal profile analysis** without any sensitive-attribute inference.
- [ ] **Step 4: Run** `pytest tests/test_profile_analysis.py -v` and then `pytest -q`.

### Task 2: Following similarity and cohort candidates

**Files:**
- Create: `src/xni/analysis/network.py`
- Test: `tests/test_network_analysis.py`

**Interfaces:**
- Consumes: active `TargetRelationship` rows joined to `Target` and `Account`
- Produces: `FollowingSimilarity`, `get_active_following_sets(session)`, `compare_following_sets(...)`, `find_similarity_pairs(session, *, min_jaccard, min_shared)`

- [ ] **Step 1: Write failing tests** with three targets whose active following sets have known overlaps.
- [ ] **Step 2: Run** `pytest tests/test_network_analysis.py -v` and confirm failure.
- [ ] **Step 3: Implement exact Jaccard and overlap ratios**, excluding self/duplicate pair output.
- [ ] **Step 4: Run** `pytest tests/test_network_analysis.py -v` and `pytest -q`.

### Task 3: Central node and bridge candidate analysis

**Files:**
- Create: `src/xni/analysis/centrality.py`
- Test: `tests/test_centrality.py`

**Interfaces:**
- Consumes: active following sets from `get_active_following_sets(session)`
- Produces: `CentralNodeScore`, `rank_central_nodes(session, *, limit)`

- [ ] **Step 1: Write failing tests** where one account is followed by every target and another connects otherwise separate target groups.
- [ ] **Step 2: Run** `pytest tests/test_centrality.py -v` and confirm failure.
- [ ] **Step 3: Build a bipartite NetworkX graph** and return account-node coverage, in-degree count, and betweenness score.
- [ ] **Step 4: Run** `pytest tests/test_centrality.py -v` and `pytest -q`.

### Task 4: Read-only analysis API

**Files:**
- Modify: `src/xni/app.py`
- Test: `tests/test_app.py`
- Modify: `README.md`

**Interfaces:**
- Produces: `GET /api/analysis/new-accounts`, `GET /api/analysis/similarity`, `GET /api/analysis/central-nodes`

- [ ] **Step 1: Write failing endpoint tests** using a temporary SQLite DB with seeded target/account relationships.
- [ ] **Step 2: Run** endpoint tests and confirm 404s before implementation.
- [ ] **Step 3: Add read-only endpoints** with explicit query parameters for heuristic thresholds.
- [ ] **Step 4: Run** `pytest -q` and document endpoint examples and interpretation limits.
