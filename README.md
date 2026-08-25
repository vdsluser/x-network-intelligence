# X Network Intelligence

X 계정의 공개 팔로잉 관계망을 로컬에 축적하고 **관심 주제, 관계 군집, 중심노드, 신생계정 코호트, 관계 변화**를 분석하는 로컬 네트워크 인텔리전스 프로젝트입니다.

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

## 수동 Following Snapshot 가져오기

Sorsa 형태의 `users`, `targetLabel`, `mode: "following"` JSON을 `POST /api/import/manual`에 전달합니다. 원본 payload와 각 user JSON을 SQLite에 함께 보존하고, 두 번째 Snapshot부터 `added / removed / unchanged`를 계산합니다.

## 분석 API

### 신생·저팔로잉 후보

```text
GET /api/analysis/new-accounts?new_account_days=90&low_following_max=100
```

계정 생성일과 현재 팔로잉 수만 사용합니다. `90일`, `100`은 판정 사실이 아니라 사용자가 바꿀 수 있는 분석 기준값입니다.

### Following 유사도

```text
GET /api/analysis/similarity?min_jaccard=0.2&min_shared=2
```

두 추적 대상의 활성 Following 집합을 비교해 다음 근거를 반환합니다.

- `shared_count`
- `union_count`
- `jaccard`
- `overlap_a`
- `overlap_b`

### 신생계정 Cohort 후보

```text
GET /api/analysis/cohorts?new_account_days=90&low_following_max=100&min_jaccard=0.2&min_shared=2
```

신생·저팔로잉 후보 중 **둘 다 실제 추적 대상으로 Following Snapshot이 축적된 경우**에만 관계 유사도를 비교합니다. 높은 점수는 관계망 유사성 신호이며 조직성이나 동일 세력을 의미한다고 단정하지 않습니다.

### 중심노드

```text
GET /api/analysis/central-nodes?limit=20
```

활성 `Target → Account` 관계를 NetworkX bipartite graph로 구성해 다음 값을 반환합니다.

- `followed_by_targets`: 몇 개의 추적 대상이 해당 계정을 팔로우하는지
- `target_coverage`: 전체 추적 대상 중 연결 비율
- `betweenness`: 관계망에서 매개 경로에 위치하는 정도

추적 대상이 1개뿐이면 모든 연결 계정의 `target_coverage`가 1.0이므로 중심노드 비교의 의미가 제한됩니다. 여러 타깃의 Snapshot이 쌓일수록 가치가 커집니다.

## SQLite에 보존하는 데이터

- `targets` — 추적 대상
- `accounts` — 발견된 X 계정과 최신 공개 메타데이터
- `following_snapshots` — 수집 시점과 전체 원본 JSON
- `snapshot_members` — 각 Snapshot에 포함된 계정과 해당 원본 user JSON
- `target_relationships` — 현재 활성/비활성 팔로잉 관계와 최초/최근 관측 시점
- `relationship_events` — added / removed 변화 이벤트

## 핵심 기능 로드맵

1. ✅ Target / Account / Snapshot 저장
2. ✅ Relationship Diff
3. ✅ New Account Candidate Analysis
4. ✅ Following Similarity
5. ✅ New Account Cohort Pair Detection
6. ✅ Central Node / Bridge Signal
7. Following Fingerprint
8. Topic & Public Association Classification
9. Local Relationship Graph UI
10. Network Trend / Rising Node Analysis

## 분석 원칙

- 개인의 정치·종교 등 민감한 속성을 임의로 단정하지 않습니다.
- bio 등에 명시적으로 공개된 소속·관심 표현은 근거와 함께 기록할 수 있습니다.
- 조직성·세력 여부를 확정하지 않고, 팔로잉 유사도·공통 팔로잉 비율·계정 생성 시기·중심노드 집중도 같은 측정 가능한 신호를 제공합니다.
- 분석 기준값은 휴리스틱이며 사용자가 변경할 수 있게 유지합니다.
- 원본 데이터를 보존해 분석 알고리즘 개선 후 재분석할 수 있게 설계합니다.

## 데이터 Provider

- `ManualImportProvider` — JSON 수동 가져오기
- `SorsaProvider` — 정식 API Adapter(향후)
- 향후 추가 Provider

비공식 Playground endpoint 자동 호출을 기본 Provider로 구현하지 않습니다.

## 문서

- [Project Plan](docs/PROJECT_PLAN.md)
- [Python Local MVP Implementation Plan](docs/superpowers/plans/2026-08-25-python-local-mvp.md)
- [Manual Import + Snapshot Diff Plan](docs/superpowers/plans/2026-08-25-manual-import-snapshot.md)
- [Network Analysis Core Plan](docs/superpowers/plans/2026-08-25-network-analysis-core.md)

## 현재 상태

**STEP 3 — Network Analysis Core**

현재 구현:

- `python -m xni` 로컬 실행
- FastAPI `/api/health`
- FastAPI `POST /api/import/manual`
- Snapshot + Relationship Diff
- 신생·저팔로잉 후보 분석
- Following Jaccard 유사도
- 신생계정 Cohort 후보 pair
- NetworkX 중심노드 / betweenness 신호
- pytest 회귀 테스트
