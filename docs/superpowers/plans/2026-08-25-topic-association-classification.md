# Topic & Public Association Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic, evidence-first topic/account-type/public-association classification to locally stored X accounts and extend Following Fingerprint with semantic summaries.

**Architecture:** Derived semantic data is stored separately from raw `Account`/snapshot data. A bilingual rule engine produces versioned classifications, a transactional service persists/rebuilds one classifier version, REST APIs expose run/detail/aggregate results, and Fingerprint v2 aggregates the selected classifier version over active following relationships.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, SQLite, Pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-08-25-topic-association-classification-design.md`

## Global Constraints

- Local-first; no external HTTP calls from the classification subsystem.
- Rule-v1 is deterministic and bilingual (Korean/English).
- No external AI dependency in rule-v1.
- Every persisted semantic result stores evidence, confidence, source, and classifier version.
- No semantic result below confidence `0.70` is persisted.
- Follow relationships must never be converted into sensitive personal-attribute labels.
- `declared_affiliation` requires explicit public bio wording; never infer it from graph structure.
- Raw accounts and snapshot JSON remain unchanged source-of-truth data.
- GitHub Actions are not required; verify locally with pytest and compileall.

---

### Task 1: Classification Persistence Models

**Files:**
- Modify: `src/xni/models.py`
- Test: `tests/test_classification_models.py`

**Interfaces:**
- Produces ORM models `AccountTopic`, `AccountClassification`, `AccountAssociation`, and `ClassificationRun`.
- Later tasks rely on uniqueness constraints by account/version and association normalized value.

- [ ] **Step 1: Write failing table/constraint tests**

```python
from sqlalchemy import inspect
from xni.db import create_engine_for_path, init_database


def test_classification_tables_are_created(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    names = set(inspect(engine).get_table_names())
    assert {"account_topics", "account_classifications", "account_associations", "classification_runs"} <= names
```

Add a uniqueness test that inserting the same `(account_id, topic, classifier_version)` twice raises `IntegrityError`.

- [ ] **Step 2: Run tests and confirm RED**

Run: `pytest tests/test_classification_models.py -q`
Expected: FAIL because the four ORM models/tables do not exist.

- [ ] **Step 3: Implement models**

Use SQLAlchemy mapped classes with fields from the spec. Important constraints:

```python
UniqueConstraint("account_id", "topic", "classifier_version", name="uq_account_topic_version")
UniqueConstraint("account_id", "classifier_version", name="uq_account_classification_version")
UniqueConstraint(
    "account_id", "association_type", "normalized_value", "classifier_version",
    name="uq_account_association_version",
)
```

`ClassificationRun.parameters_json` is JSON; counts are integers; `started_at` and `completed_at` are timezone-aware datetimes.

- [ ] **Step 4: Run tests and confirm GREEN**

Run: `pytest tests/test_classification_models.py -q`
Expected: PASS.

---

### Task 2: Taxonomy and Deterministic Topic/Account-Type Rules

**Files:**
- Create: `src/xni/analysis/classification/__init__.py`
- Create: `src/xni/analysis/classification/taxonomy.py`
- Create: `src/xni/analysis/classification/rules.py`
- Create: `src/xni/analysis/classification/classifier.py`
- Test: `tests/test_classifier_rules.py`

**Interfaces:**
- Produces `TopicMatch`, `AccountTypeMatch`, `classify_topics(text)`, `classify_account_type(text)`.
- The service task consumes these pure functions.

- [ ] **Step 1: Write failing bilingual rule tests**

```python
def test_ai_bio_matches_ai_and_technology_topics():
    matches = classify_topics("AI researcher | LLM | Python")
    assert {m.topic for m in matches} >= {"AI", "Technology"}


def test_korean_media_role_wins_account_type():
    match = classify_account_type("경제 전문 기자 | 뉴스룸")
    assert match.account_type == "Media"


def test_empty_bio_is_unknown():
    assert classify_topics("") == []
    assert classify_account_type("").account_type == "Unknown"
```

Also test deterministic priority when multiple account-type phrases match.

- [ ] **Step 2: Run and confirm RED**

Run: `pytest tests/test_classifier_rules.py -q`
Expected: import/function failures.

- [ ] **Step 3: Implement taxonomy and rule representation**

Use immutable rule objects such as:

```python
@dataclass(frozen=True)
class KeywordRule:
    output: str
    any_keywords: tuple[str, ...] = ()
    all_keywords: tuple[str, ...] = ()
    confidence: float = 0.85
    source: str = "bio_rule"
```

Normalize Unicode whitespace/case before matching. Start with high-precision Korean/English terms for the spec taxonomy. Avoid broad ambiguous words unless paired with another signal.

- [ ] **Step 4: Implement pure classifier output models**

Each match includes normalized output, confidence, source, and evidence substring/text. Account type returns exactly one winning result using deterministic priority.

- [ ] **Step 5: Run tests and confirm GREEN**

Run: `pytest tests/test_classifier_rules.py -q`
Expected: PASS.

---

### Task 3: Explicit Public Association Extractor

**Files:**
- Create: `src/xni/analysis/classification/associations.py`
- Test: `tests/test_association_extractor.py`

**Interfaces:**
- Produces `AssociationMatch` and `extract_associations(description, raw_json=None)`.
- Service persists these matches.

- [ ] **Step 1: Write failing extractor tests**

Cover explicit roles, @mentions, domains, and explicit affiliation syntax only:

```python
def test_extracts_role_and_org_mention():
    rows = extract_associations("CEO @ExampleAI | AI builder")
    assert ("role", "CEO") in {(r.association_type, r.value) for r in rows}
    assert ("organization", "ExampleAI") in {(r.association_type, r.value) for r in rows}


def test_declared_affiliation_requires_explicit_phrase():
    rows = extract_associations("member of Example Association")
    assert any(r.association_type == "declared_affiliation" for r in rows)


def test_plain_topic_text_does_not_create_declared_affiliation():
    rows = extract_associations("politics society news")
    assert not any(r.association_type == "declared_affiliation" for r in rows)
```

- [ ] **Step 2: Run and confirm RED**

Run: `pytest tests/test_association_extractor.py -q`
Expected: missing module/function.

- [ ] **Step 3: Implement normalization and extraction**

Normalize association values for dedupe using trimmed, collapsed, casefolded text while preserving display `value` and exact evidence. Extract `domain` from `bio_urls` in latest raw JSON when present; do not fetch URLs.

- [ ] **Step 4: Run and confirm GREEN**

Run: `pytest tests/test_association_extractor.py -q`
Expected: PASS.

---

### Task 4: Transactional Classification/Re-analysis Service

**Files:**
- Create: `src/xni/analysis/classification/service.py`
- Test: `tests/test_classification_service.py`

**Interfaces:**
- Produces `ClassificationRunRequest`, `ClassificationRunSummary`, `run_classification(session, request)` and `get_account_classification_detail(...)`.
- API task calls these functions.

- [ ] **Step 1: Write failing persistence/idempotency tests**

Seed accounts with English/Korean bios and latest `SnapshotMember.raw_json`. Assert:

```python
summary = run_classification(session, ClassificationRunRequest())
assert summary.accounts_processed == 3
assert summary.classifier_version == "rule-v1"
assert summary.topics_created > 0
```

Run a second `replace_version=True` classification and assert counts in derived tables do not double. Run `classifier_version="rule-v2-test"` only through a test-injected/allowed version path if supported; otherwise test that unknown versions are rejected per spec.

- [ ] **Step 2: Run and confirm RED**

Run: `pytest tests/test_classification_service.py -q`
Expected: missing service.

- [ ] **Step 3: Implement rule-v1 transaction**

For `replace_version=True`, delete only derived rows for the selected version, classify all stored accounts, insert one primary account classification per account/version, topic rows only for non-Unknown matches, association rows above threshold, and one `ClassificationRun` audit row.

Use the latest `SnapshotMember.raw_json` per account when optional fields are needed. Never mutate `Account` or snapshot rows.

- [ ] **Step 4: Implement detail query**

Return primary type + topic rows + associations with source/evidence/confidence/version. Missing account raises `ValueError` for API translation to 404.

- [ ] **Step 5: Run and confirm GREEN**

Run: `pytest tests/test_classification_service.py -q`
Expected: PASS.

---

### Task 5: Topic/Association Aggregates and REST API

**Files:**
- Modify: `src/xni/app.py`
- Modify: `src/xni/analysis/classification/service.py`
- Test: `tests/test_classification_api.py`

**Interfaces:**
- Adds:
  - `POST /api/analysis/classify`
  - `GET /api/analysis/topics`
  - `GET /api/analysis/associations`
  - `GET /api/accounts/{account_id}/classification`

- [ ] **Step 1: Write failing API tests**

Test a local DB seeded through manual import, call classification, then assert topic aggregate, association aggregate, and detail evidence. Also assert invalid classifier version returns 400 and missing account returns 404.

- [ ] **Step 2: Run and confirm RED**

Run: `pytest tests/test_classification_api.py -q`
Expected: endpoint 404s.

- [ ] **Step 3: Implement aggregate query models/functions**

Topic aggregate returns topic + account_count + coverage where coverage denominator is total stored accounts. Association aggregate accepts validated association type and limit and returns normalized value, display value, account_count, evidence_count.

- [ ] **Step 4: Add FastAPI endpoints**

Translate service `ValueError` into HTTP 400/404 according to the spec. Keep all work local to the SQLite engine.

- [ ] **Step 5: Run and confirm GREEN**

Run: `pytest tests/test_classification_api.py -q`
Expected: PASS.

---

### Task 6: Following Fingerprint v2 Semantic Metrics

**Files:**
- Modify: `src/xni/analysis/fingerprint.py`
- Test: `tests/test_fingerprint_semantics.py`

**Interfaces:**
- Extends `FollowingFingerprint` with:
  - `topic_distribution`
  - `account_type_distribution`
  - `top_topics`
  - `topic_concentration`
  - `topic_diversity`
  - `public_associations`
  - `classified_account_count`
  - `unclassified_account_count`
  - `unclassified_ratio`
  - `classifier_version`

- [ ] **Step 1: Write failing semantic fingerprint tests**

Seed a target following three classified accounts with overlapping topic tags. Assert display topic percentages use `tagged_accounts / following_count`, while HHI/entropy use normalized tag assignments. Assert unclassified coverage follows the design definition.

- [ ] **Step 2: Run and confirm RED**

Run: `pytest tests/test_fingerprint_semantics.py -q`
Expected: new fields absent.

- [ ] **Step 3: Implement semantic summary helpers**

Use pure helpers for HHI and normalized Shannon entropy:

```python
def topic_concentration(counts: list[int]) -> float:
    total = sum(counts)
    return sum((count / total) ** 2 for count in counts) if total else 0.0
```

Entropy returns `0.0` for fewer than two nonzero topics.

- [ ] **Step 4: Extend single/all fingerprint builders**

Default `classifier_version="rule-v1"`. Existing network metrics must remain byte-for-byte semantically unchanged. Missing classifications produce empty distributions and `unclassified_ratio` based on following count, not an exception.

- [ ] **Step 5: Run and confirm GREEN**

Run: `pytest tests/test_fingerprint_semantics.py tests/test_fingerprint.py -q`
Expected: PASS.

---

### Task 7: Fingerprint API Version Selection and Regression

**Files:**
- Modify: `src/xni/app.py`
- Test: `tests/test_fingerprint.py`
- Test: `tests/test_classification_api.py`

**Interfaces:**
- Existing fingerprint endpoints accept `classifier_version=rule-v1` and return semantic v2 fields.

- [ ] **Step 1: Add failing API assertion**

After classification, request `/api/analysis/fingerprints/{target}?classifier_version=rule-v1` and assert topic/type/association semantic fields plus all previous network fields.

- [ ] **Step 2: Run and confirm RED**

Run: `pytest tests/test_fingerprint.py -q`
Expected: query parameter/semantic assertion failure.

- [ ] **Step 3: Wire classifier version through API to builders**

Do not auto-run classification from a GET request; GET only reads persisted derived results.

- [ ] **Step 4: Run focused and full regression tests**

Run:

```bash
pytest tests/test_fingerprint.py tests/test_classification_api.py -q
pytest -q
python -m compileall -q src
```

Expected: all tests PASS and compileall exit code 0.

---

### Task 8: Documentation and Stored-data Validation

**Files:**
- Modify: `README.md`
- Modify: `docs/PROJECT_PLAN.md`
- Test: no production test file; use a local validation script/pytest fixture with Sorsa-style JSON.

**Interfaces:**
- Documents the rule-v1 workflow and prepares STEP 7 Graph UI.

- [ ] **Step 1: Validate with Sorsa-style stored JSON**

Import representative stored payloads containing Korean/English bios and optional `bio_urls`, run rule-v1, and print/assert classification counts plus one Fingerprint v2 response. No external network access.

- [ ] **Step 2: Update README**

Document the four classification endpoints, evidence-first semantics, `Unknown`, and Fingerprint v2 fields. Explicitly state that `topic_concentration` is public topic-tag concentration, not ideology/belief concentration.

- [ ] **Step 3: Update project plan/status**

Mark Topic/Association Classification and Fingerprint v2 complete; set the next planned subsystem to Local Cytoscape Relationship Graph UI.

- [ ] **Step 4: Final verification**

Run:

```bash
pytest -q
python -m compileall -q src
```

Expected: zero test failures and compileall exit code 0.
