# Topic & Public Association Classification — Design Spec

## 1. Purpose

This subsystem adds semantic meaning to the existing relationship graph without replacing the existing evidence-first network metrics. It classifies each observed X account by public topic signals, account type, and explicitly stated public associations, then extends Following Fingerprint with aggregate semantic distributions.

The subsystem must remain local-first, deterministic by default, re-analysis friendly, and conservative about sensitive attributes.

## 2. Goals

- Classify public account bios and metadata into reusable topic tags.
- Classify account type separately from topic.
- Extract explicitly stated public associations with supporting evidence.
- Persist classifier version, confidence, evidence, and analysis run metadata.
- Allow full re-analysis when rules change.
- Extend Following Fingerprint with topic/type distributions, top associations, and diversity/concentration measures.
- Keep AI optional and outside the initial implementation path.

## 3. Non-goals

- Do not infer a person's political ideology, religion, ethnicity, health, sexuality, or other sensitive traits from their network.
- Do not conclude that similar accounts belong to the same organization, faction, or coordinated group.
- Do not automatically scrape additional websites to enrich a profile in the first implementation.
- Do not add an external AI dependency in rule-v1.
- Do not build the graph UI in this subsystem.

## 4. Design Principles

### 4.1 Evidence First

Every classification result stores the exact public text fragment or metadata signal that caused the result.

Example:

```json
{
  "topic": "AI",
  "source": "bio_rule",
  "evidence": "AI researcher | LLM",
  "confidence": 0.95,
  "classifier_version": "rule-v1"
}
```

### 4.2 Topic and Account Type Are Different Dimensions

`topic` answers "what subject does this account publicly focus on?"

`account_type` answers "what kind of public account is this?"

An account can therefore be:

```text
account_type = Media
topics = [PoliticsSociety, EconomyFinance]
```

or:

```text
account_type = Individual
topics = [AI, Technology]
```

### 4.3 Unknown Is Valid

The engine must prefer `Unknown` over weak guesses. Coverage is measured explicitly so later rules or optional AI can focus only on unresolved accounts.

### 4.4 Sensitive Attributes

The system must not convert network structure into a sensitive personal attribute label.

For public bios, explicit self-description may be stored as a declared association only when the evidence itself is retained. Even then, the system reports the explicit statement, not an inferred ideology or belief.

## 5. Classification Taxonomy

### 5.1 Topic Tags

Initial rule-v1 topics:

- `PoliticsSociety`
- `MediaJournalism`
- `EconomyFinance`
- `Investment`
- `Business`
- `Technology`
- `AI`
- `Crypto`
- `Sports`
- `Entertainment`
- `Creator`
- `Organization`
- `PublicAffairs`
- `ScienceResearch`
- `Education`
- `CultureArts`
- `Unknown`

Multiple topic tags are allowed per account.

### 5.2 Account Types

Exactly one primary account type is returned by rule-v1:

- `Individual`
- `Media`
- `Company`
- `Organization`
- `PublicFigure`
- `Creator`
- `FanAccount`
- `Unknown`

Account type rules must be higher precision than topic rules. When multiple type rules match, deterministic priority is used and the evidence for the winning rule is stored.

## 6. Public Association Types

Initial association types:

- `organization`
- `company`
- `media`
- `project`
- `brand`
- `person_mention`
- `technology`
- `role`
- `domain`
- `declared_affiliation`

`declared_affiliation` is only emitted when the public bio text explicitly states the affiliation. It must never be produced from follow relationships or topic co-occurrence.

## 7. Rule Engine

### 7.1 Input

The rule engine consumes the existing normalized `Account` model, primarily:

- `username`
- `display_name`
- `description`
- `profile_image_url` only as metadata, never for image analysis
- latest raw snapshot user JSON when optional fields such as `bio_urls` or `location` are available

### 7.2 Rule Representation

Rules are Python data structures, not hard-coded nested conditionals.

Conceptual shape:

```python
@dataclass(frozen=True)
class KeywordRule:
    output: str
    keywords: tuple[str, ...]
    confidence: float
    evidence_source: str
```

Rules must support case-insensitive matching and normalized whitespace. Korean and English keywords are both supported from rule-v1.

### 7.3 Confidence

Rule-v1 confidence is deterministic and rule-defined, not probabilistic model confidence.

Suggested bands:

- explicit role phrase or explicit keyword pair: `0.95`
- strong single-domain keyword: `0.85`
- broad weak keyword: avoid or assign only if paired with another signal

No result below `0.70` is persisted in rule-v1.

### 7.4 Deduplication

For the same `account_id + topic + classifier_version`, keep one row with the strongest confidence and combined evidence where useful.

For associations, normalize values for deduplication while preserving the original evidence text.

## 8. Persistence Model

### 8.1 `account_topics`

Fields:

```text
id
account_id
topic
source
evidence
confidence
classifier_version
analyzed_at
```

Constraints:

- indexed by `account_id`
- indexed by `topic`
- unique logical result per `account_id + topic + classifier_version`

### 8.2 `account_classifications`

Stores the primary account type separately from topics.

Fields:

```text
id
account_id
account_type
source
evidence
confidence
classifier_version
analyzed_at
```

Constraint:

- one primary classification per `account_id + classifier_version`

### 8.3 `account_associations`

Fields:

```text
id
account_id
association_type
value
normalized_value
source
evidence
confidence
classifier_version
analyzed_at
```

Logical uniqueness:

```text
account_id + association_type + normalized_value + classifier_version
```

### 8.4 `classification_runs`

Fields:

```text
id
classifier_version
parameters_json
accounts_processed
accounts_with_topics
accounts_unknown
topics_created
associations_created
started_at
completed_at
```

This is the audit trail for re-analysis.

## 9. Re-analysis Semantics

Classification is derived data. Raw account and snapshot data remain the source of truth.

A classification run may operate in two modes:

- `replace_version`: delete and rebuild derived results for the selected classifier version.
- `new_version`: preserve old results and write a new classifier version.

Rule-v1 implementation uses `replace_version` by default so repeated runs are idempotent.

Historical raw JSON is not modified.

## 10. Service Boundaries

Planned modules:

```text
src/xni/analysis/classification/
├── __init__.py
├── taxonomy.py
├── rules.py
├── classifier.py
├── associations.py
└── service.py
```

Responsibilities:

- `taxonomy.py`: enums/constants and normalized labels.
- `rules.py`: deterministic bilingual keyword/phrase rule definitions.
- `classifier.py`: topic and account-type evaluation.
- `associations.py`: explicit public association extraction.
- `service.py`: database re-analysis transaction and run summary.

No module performs external HTTP requests.

## 11. Classification API

### 11.1 Run Classification

```text
POST /api/analysis/classify
```

Request:

```json
{
  "classifier_version": "rule-v1",
  "replace_version": true
}
```

Response:

```json
{
  "classifier_version": "rule-v1",
  "accounts_processed": 847,
  "accounts_with_topics": 691,
  "accounts_unknown": 156,
  "topics_created": 1234,
  "associations_created": 418
}
```

### 11.2 Topic Aggregate

```text
GET /api/analysis/topics
```

Returns topic counts and coverage across currently stored accounts.

### 11.3 Association Aggregate

```text
GET /api/analysis/associations?type=organization&limit=50
```

Returns normalized public association values with account counts and evidence count.

### 11.4 Account Classification Detail

```text
GET /api/accounts/{account_id}/classification
```

Returns primary type, topics, associations, evidence, confidence, and classifier version.

## 12. Following Fingerprint v2

The existing network fingerprint remains the base. Semantic fields are added without changing the meaning of existing metrics.

New fields:

```text
topic_distribution
account_type_distribution
top_topics
topic_concentration
topic_diversity
public_associations
classified_account_count
unclassified_account_count
unclassified_ratio
classifier_version
```

### 12.1 Topic Distribution

For a target, count topic membership across currently active followed accounts.

Because accounts may have multiple topics, topic percentages are presented as "share of followed accounts tagged with this topic", not as a partition that must sum to 100%.

### 12.2 Account Type Distribution

Account type is single-primary-label, so its distribution is a normal partition among classified followed accounts.

### 12.3 Topic Concentration

Use normalized HHI over the topic tag count shares for rule-v1:

```text
HHI = sum(p_i^2)
```

Expose the raw HHI as `topic_concentration`.

### 12.4 Topic Diversity

Use normalized Shannon entropy where possible:

```text
H = -sum(p_i * ln(p_i))
normalized_diversity = H / ln(number_of_nonzero_topics)
```

Return `0.0` when fewer than two nonzero topics exist.

These metrics describe public topic-tag distribution only. They must not be described as ideological concentration or belief diversity.

### 12.5 Public Association Summary

Return top explicitly extracted public associations for the target's followed accounts:

```json
{
  "value": "ExampleAI",
  "association_type": "company",
  "account_count": 17
}
```

## 13. Error Handling

- Unknown `classifier_version` on run request: HTTP 400.
- Missing account detail: HTTP 404.
- Empty database: classification run returns zero counts, not an error.
- Invalid association type query: HTTP 400.
- Rule parsing errors are treated as programmer errors and covered by tests; no partial database commit.
- One classification run is committed transactionally so a failed run does not leave a mixed version state.

## 14. Testing Strategy

### Unit tests

- topic rule matching in Korean and English
- multiple topics from one bio
- deterministic account-type priority
- Unknown behavior for ambiguous/empty bios
- explicit association extraction
- no `declared_affiliation` from follow graph data
- normalized association deduplication
- confidence threshold behavior

### Persistence tests

- first classification run writes topics/types/associations/run row
- repeating `replace_version` is idempotent
- new classifier version preserves old version rows
- transaction rollback on classification failure

### API tests

- `POST /api/analysis/classify`
- topic aggregate
- association aggregate
- account classification detail
- validation errors

### Fingerprint v2 tests

- topic distribution for a target
- account type distribution
- HHI concentration
- normalized entropy diversity
- association aggregation
- unclassified ratio
- existing fingerprint fields remain unchanged

### Regression

Run the full existing pytest suite after each task.

GitHub Actions are not required for this subsystem; local pytest/compile verification remains the default.

## 15. Rollout Sequence

1. Merge Following Fingerprint into `main`.
2. Add classification persistence tables.
3. Add taxonomy and deterministic rule engine.
4. Add account-type classifier.
5. Add public association extractor.
6. Add re-analysis service and `classification_runs`.
7. Add REST endpoints.
8. Extend Following Fingerprint to v2.
9. Validate with stored Sorsa-style snapshot data.
10. Update README and project status.

## 16. Success Criteria

The subsystem is ready when:

- the same SQLite database can be reclassified deterministically with `rule-v1`;
- every persisted semantic result has evidence, confidence, and classifier version;
- unresolved accounts remain explicitly measurable as Unknown/unclassified;
- a target fingerprint can show network metrics and semantic topic/type/association summaries together;
- no sensitive-trait inference is produced from follow relationships;
- all new tests and the existing full suite pass locally.

## 17. Future Extension: Optional AI Resolver

AI is deliberately excluded from rule-v1. If added later, it will process only unresolved accounts and must emit the same normalized output schema with:

```text
source = ai_model
model_name
prompt_version
evidence
confidence
```

AI output must not override explicit rule evidence silently. The UI/API must remain able to distinguish rule-derived and model-derived results.
