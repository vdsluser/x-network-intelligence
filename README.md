# X Network Intelligence

X 계정의 공개 팔로잉 관계망을 로컬 SQLite에 축적하고 **관계 변화, 신생계정 코호트, Following 유사도, 중심노드, 공개 주제·계정 유형·명시적 공개 관계**를 근거와 함께 분석하는 로컬 네트워크 인텔리전스 프로젝트입니다.

## 현재 기술 구조

- Python 3.12+
- FastAPI + Uvicorn
- SQLite + SQLAlchemy 2.x
- Pydantic v2
- NetworkX
- pandas / scikit-learn
- Provider Adapter 구조

기본 DB 파일은 `data/x_network.db`에 생성됩니다.

## 실행

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m xni
```

macOS / Linux:

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m xni
```

상태 확인: `http://127.0.0.1:8000/api/health`

## 수동 Following Snapshot

Sorsa 형태의 `users`, `targetLabel`, `mode: "following"` JSON을 `POST /api/import/manual`에 전달합니다. 원본 payload와 각 user JSON을 SQLite에 보존하고, 두 번째 Snapshot부터 `added / removed / unchanged`를 계산합니다.

여러 Target JSON은 `POST /api/import/manual/batch`로 한 번에 넣을 수 있습니다. Batch Import 후 Expansion Queue와 Similarity/Cohort/Central Node 요약을 다시 계산합니다.

## Network Expansion Queue

신생·저팔로잉 후보를 로컬 추적 대상으로 확장합니다.

```text
관측 Account
  → 신생·저팔로잉 후보 판별
  → Expansion Queue(pending)
  → Target 승격
  → 해당 Target의 Following JSON 추가 Import
  → Similarity / Cohort / Central Node 재분석
```

주요 API:

- `POST /api/expansion/queue/refresh`
- `GET /api/expansion/queue?status=pending`
- `POST /api/expansion/queue/{candidate_id}/promote`
- `POST /api/import/manual/batch`

`promote`는 X에서 실제 Follow를 수행하지 않습니다. SQLite의 로컬 추적 Target만 생성합니다.

## Semantic Classification — rule-v1

STEP 6부터 공개 bio와 이미 저장된 snapshot metadata를 규칙 기반으로 분석합니다. **외부 웹 요청이나 AI 호출 없이 로컬 데이터만 사용**합니다.

Topic과 Account Type은 별개 차원입니다. 예를 들어 한 계정은 `account_type=Media`이면서 `topics=[MediaJournalism, EconomyFinance]`일 수 있습니다.

초기 Topic에는 AI, Technology, EconomyFinance, Investment, Business, MediaJournalism, PoliticsSociety, PublicAffairs, Crypto, Sports, Entertainment, Creator, Organization, ScienceResearch, Education, CultureArts 등이 포함됩니다. Account Type은 `Individual / Media / Company / Organization / PublicFigure / Creator / FanAccount / Unknown` 중 하나입니다.

모든 저장 결과에는 다음 근거가 붙습니다.

- `source`
- `evidence`
- `confidence`
- `classifier_version`
- `analyzed_at`

애매한 계정은 억지로 분류하지 않고 `Unknown` 또는 미분류로 남깁니다.

### 분류 실행

```text
POST /api/analysis/classify
```

기본 요청:

```json
{
  "classifier_version": "rule-v1",
  "replace_version": true
}
```

같은 `rule-v1`을 다시 실행하면 해당 버전의 파생 결과를 재생성하므로 중복 누적되지 않습니다. 원본 Account와 Snapshot JSON은 수정하지 않습니다.

### 분류 조회 API

- `GET /api/analysis/topics?classifier_version=rule-v1`
- `GET /api/analysis/associations?type=organization&limit=50&classifier_version=rule-v1`
- `GET /api/accounts/{account_id}/classification?classifier_version=rule-v1`

Public Association은 bio 또는 저장된 URL metadata에 **명시된 공개 정보**만 추출합니다. `declared_affiliation`은 `member of ...`, `소속: ...`처럼 명시적인 문구가 있을 때만 생성하며 Following 관계, Cohort, 중심노드로부터 개인의 정치·종교 등 민감한 속성을 추론하지 않습니다.

## Network Analysis API

- `GET /api/analysis/new-accounts?new_account_days=90&low_following_max=100`
- `GET /api/analysis/similarity?min_jaccard=0.2&min_shared=2`
- `GET /api/analysis/cohorts?new_account_days=90&low_following_max=100&min_jaccard=0.2&min_shared=2`
- `GET /api/analysis/central-nodes?limit=20`

Similarity는 Jaccard와 공통 Following 수/비율을 근거로 제공합니다. Cohort와 중심노드 결과는 관계망 신호이며 조직성·동일 세력을 의미한다고 단정하지 않습니다.

## Following Fingerprint v2

각 활성 Target의 네트워크 지표와 semantic 지표를 하나의 프로필로 조회합니다.

- `GET /api/analysis/fingerprints?classifier_version=rule-v1`
- `GET /api/analysis/fingerprints/{target_username}?classifier_version=rule-v1`

기존 Network Fingerprint 필드:

- `following_count`
- `new_account_count`, `new_account_ratio`
- `new_low_following_count`, `new_low_following_ratio`
- `shared_following_count`, `shared_network_concentration`
- `most_similar_target`, `similarity_jaccard`, `similarity_shared_count`
- `cohort_peers`
- `top_central_nodes`

v2 Semantic 필드:

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

`topic_distribution`은 한 계정이 여러 Topic을 가질 수 있어 표시 비율 합계가 100%를 넘을 수 있습니다. `topic_concentration`은 Topic assignment를 정규화한 뒤 계산한 HHI이고, `topic_diversity`는 정규화 Shannon entropy입니다. 이 값들은 **공개 bio에서 분류된 주제의 분포**만 설명하며 정치적 성향·사상·신념의 집중도나 다양성을 뜻하지 않습니다.

## SQLite 주요 테이블

기본/관계망:

- `targets`
- `accounts`
- `following_snapshots`
- `snapshot_members`
- `target_relationships`
- `relationship_events`
- `expansion_candidates`

Semantic derived data:

- `account_topics`
- `account_classifications`
- `account_associations`
- `classification_runs`

분류 결과는 파생 데이터입니다. 원본 Snapshot JSON을 유지하므로 규칙 버전이 개선되면 다시 분석할 수 있습니다.

## 분석 원칙

- **Evidence First**: 가능한 모든 결과에 근거 문구와 수치를 연결합니다.
- **Rule First, AI Optional**: rule-v1은 결정론적 규칙 기반이며 AI를 사용하지 않습니다.
- **Unknown Is Valid**: 근거가 부족하면 미분류 상태를 유지합니다.
- **Sensitive Attribute Guard**: Following 관계만으로 개인의 정치·종교 등 민감한 속성을 임의로 추정하지 않습니다.
- **Relationship Signals, Not Claims**: 유사도·Cohort·중심노드는 측정값이며 조직성·조작 여부의 확정 판정이 아닙니다.
- **Re-analysis Ready**: classifier version과 원본 JSON을 보존해 재분석할 수 있게 합니다.

## 핵심 기능 로드맵

1. ✅ Target / Account / Snapshot 저장
2. ✅ Relationship Diff
3. ✅ New Account Candidate Analysis
4. ✅ Following Similarity
5. ✅ New Account Cohort Pair Detection
6. ✅ Central Node / Bridge Signal
7. ✅ Network Expansion Queue / Target Promotion / Batch Import
8. ✅ Following Fingerprint v1
9. ✅ Topic / Account Type / Public Association Classification rule-v1
10. ✅ Following Fingerprint v2 Semantic Metrics
11. ⏭ Local Cytoscape Relationship Graph UI
12. Network Trend / Rising Node / Emerging Hub

## 문서

- [Project Plan](docs/PROJECT_PLAN.md)
- [Topic & Public Association Classification Design](docs/superpowers/specs/2026-08-25-topic-association-classification-design.md)
- [Topic & Public Association Classification Implementation Plan](docs/superpowers/plans/2026-08-25-topic-association-classification.md)

## 현재 상태

**STEP 6 — Semantic Network Intelligence**

구현 범위:

- Snapshot / Relationship Diff
- Expansion Queue / Batch Import
- Following Similarity / Cohort / Centrality
- Following Fingerprint v1
- bilingual deterministic `rule-v1` Topic Classification
- deterministic primary Account Type Classification
- explicit Public Association Extraction
- versioned classification re-analysis and audit run
- Topic / Association / Account detail API
- Following Fingerprint v2 semantic distribution, HHI, diversity, associations

다음 단계는 **STEP 7 — Cytoscape 기반 Local Relationship Graph UI**입니다.
