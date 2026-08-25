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

## Network Expansion Queue

신생·저팔로잉 후보를 로컬 추적 대상으로 확장하는 워크플로를 제공합니다.

```text
관측 Account
  → New Account 후보 판별
  → Expansion Queue(pending)
  → 사용자가 Target으로 승격
  → 해당 Target의 Following JSON 수집
  → Batch Import
  → Similarity / Cohort / Central Node 재분석
```

주요 API:

- `POST /api/expansion/queue/refresh` — 현재 계정 데이터에서 후보 큐 갱신
- `GET /api/expansion/queue?status=pending` — 대기 후보 조회
- `POST /api/expansion/queue/{candidate_id}/promote` — 후보를 로컬 Target으로 승격
- `POST /api/import/manual/batch` — 여러 Target JSON을 순차 저장하고 큐/분석 요약 반환

`promote`는 X에서 실제 Follow를 수행하거나 외부 서비스에 요청하지 않습니다. SQLite의 로컬 `targets` 테이블에 추적 대상을 등록하는 동작만 수행합니다.

배치 요청은 `payloads`, `new_account_days`, `low_following_max`, `min_jaccard`, `min_shared`, `central_limit`을 받을 수 있습니다. 응답에는 각 Import 결과, Queue 갱신 결과, Target 수, 활성 관계 수, Similarity/Cohort 쌍 수와 상위 Central Node가 포함됩니다.

## 분석 API

### 신생·저팔로잉 후보

`GET /api/analysis/new-accounts?new_account_days=90&low_following_max=100`

계정 생성일과 현재 팔로잉 수만 사용합니다. `90일`, `100`은 판정 사실이 아니라 사용자가 바꿀 수 있는 분석 기준값입니다.

### Following 유사도

`GET /api/analysis/similarity?min_jaccard=0.2&min_shared=2`

두 추적 대상의 활성 Following 집합을 비교해 `shared_count`, `union_count`, `jaccard`, `overlap_a`, `overlap_b`를 반환합니다.

### 신생계정 Cohort 후보

`GET /api/analysis/cohorts?new_account_days=90&low_following_max=100&min_jaccard=0.2&min_shared=2`

신생·저팔로잉 후보 중 둘 다 실제 추적 대상으로 Following Snapshot이 축적된 경우에만 관계 유사도를 비교합니다. 높은 점수는 관계망 유사성 신호이며 조직성이나 동일 세력을 의미한다고 단정하지 않습니다.

### 중심노드

`GET /api/analysis/central-nodes?limit=20`

활성 `Target → Account` 관계를 NetworkX graph로 구성해 `followed_by_targets`, `target_coverage`, `betweenness`를 반환합니다. 여러 타깃의 Snapshot이 쌓일수록 의미가 커집니다.

### Following Fingerprint

각 활성 Target의 현재 관계망을 하나의 비교 가능한 프로필로 계산합니다. 별도 캐시 테이블을 만들지 않고 현재 SQLite 관계 데이터를 기준으로 즉시 계산합니다.

- `GET /api/analysis/fingerprints` — 모든 활성 Target의 Fingerprint 조회
- `GET /api/analysis/fingerprints/{target_username}` — 한 Target의 Fingerprint 조회

주요 필드:

- `following_count` — 현재 관측된 활성 Following 수
- `new_account_count`, `new_account_ratio` — 설정한 기간 기준 신생계정 수와 비율
- `new_low_following_count`, `new_low_following_ratio` — 신생계정 중 팔로잉 수도 설정 기준 이하인 계정 수와 비율
- `shared_following_count` — 다른 활성 Target도 함께 팔로우하는 계정 수
- `shared_network_concentration` — 전체 Following 중 공통 관계망 계정이 차지하는 비율
- `most_similar_target` — Following Jaccard가 가장 높은 다른 Target
- `similarity_jaccard`, `similarity_shared_count` — 최고 유사 Target과의 유사도 근거
- `cohort_peers`, `cohort_peer_count` — 설정 기준을 만족하는 신생계정 Cohort 연결
- `top_central_nodes` — 해당 Target이 팔로우하는 계정 중 전체 관계망에서 중심성이 높은 노드

예: `GET /api/analysis/fingerprints/alpha?new_account_days=90&low_following_max=100&top_node_limit=5`

`shared_network_concentration`은 주제나 정치 성향의 집중도를 뜻하지 않습니다. 현재 단계에서는 **여러 추적 Target 사이에서 실제 Following 관계가 얼마나 겹치는지**만 나타내는 관찰 가능한 네트워크 지표입니다. 주제 기반 관심사 집중도는 Topic Classification 기능이 추가된 뒤 별도 지표로 확장합니다.

## SQLite에 보존하는 데이터

- `targets` — 추적 대상
- `accounts` — 발견된 X 계정과 최신 공개 메타데이터
- `following_snapshots` — 수집 시점과 전체 원본 JSON
- `snapshot_members` — 각 Snapshot 계정과 원본 user JSON
- `target_relationships` — 활성/비활성 팔로잉 관계
- `relationship_events` — added / removed 변화 이벤트
- `expansion_candidates` — 신생·저팔로잉 확장 후보와 pending/promoted 상태

## 핵심 기능 로드맵

1. ✅ Target / Account / Snapshot 저장
2. ✅ Relationship Diff
3. ✅ New Account Candidate Analysis
4. ✅ Following Similarity
5. ✅ New Account Cohort Pair Detection
6. ✅ Central Node / Bridge Signal
7. ✅ Network Expansion Queue / Target Promotion / Batch Import
8. ✅ Following Fingerprint
9. Topic & Public Association Classification
10. Local Relationship Graph UI
11. Network Trend / Rising Node Analysis

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
- [Network Expansion Queue Plan](docs/superpowers/plans/2026-08-25-network-expansion-queue.md)

## 현재 상태

**STEP 5 — Following Fingerprint**

현재 구현:

- `python -m xni` 로컬 실행
- FastAPI Snapshot Import / Batch Import
- SQLite Snapshot + Relationship Diff
- 신생·저팔로잉 후보 분석
- Following Jaccard 유사도 / Cohort 후보
- NetworkX 중심노드 / betweenness 신호
- Expansion Queue pending/promoted 관리
- 후보 → 로컬 Target 승격
- Batch Import 후 자동 Queue 갱신 및 네트워크 분석 요약
- Target별 Following Fingerprint 및 전체 Fingerprint 조회
- pytest 회귀 테스트
