# X Network Intelligence — Project Plan

## 1. 프로젝트 정의

**X Network Intelligence**는 X의 공개 계정과 팔로잉 관계망을 로컬에 축적하고, **관심 주제, 관계 군집, 중심노드, 신생계정 코호트, 관계 변화**를 분석하는 로컬 네트워크 인텔리전스 시스템이다.

핵심 질문은 다음과 같다.

1. 타깃 계정은 어떤 계정들을 주로 팔로우하는가?
2. 그 팔로잉 네트워크에는 어떤 주제와 계정 유형이 많은가?
3. 여러 계정이 공통으로 팔로우하는 중심노드는 누구인가?
4. 최근 새롭게 주목받기 시작한 계정은 누구인가?
5. 신생계정들이 적은 팔로잉 수 안에서 공통적으로 선택하는 계정군은 무엇인가?
6. 서로 다른 군집을 연결하는 Bridge Node는 무엇인가?
7. 시간 흐름에 따라 관심 주제와 네트워크 구조가 어떻게 변하는가?

핵심 가치는 **정적인 프로필 조회가 아니라 시간에 따라 변화하는 관계망을 SQLite에 누적하고 다시 분석할 수 있게 만드는 것**이다.

---

## 2. 개발 원칙

- **Local First**: 별도 클라우드 서버 없이 개인 PC에서 실행한다.
- **SQLite as Asset**: 수집·분석 이력을 하나의 SQLite DB에 축적한다.
- **Provider Independent**: Sorsa 등 데이터 공급자는 Adapter로 분리한다.
- **Evidence First**: 분석 결과에는 가능한 한 근거 데이터와 수치를 연결한다.
- **Rule First, AI Optional**: 규칙 기반 분류를 먼저 사용하고 AI 호출은 선택적으로 사용한다.
- **Re-analysis Ready**: 원본 JSON을 보관해 분석 알고리즘이 개선되면 과거 데이터를 다시 분석한다.

### 민감한 속성 처리

정치·종교 등 민감할 수 있는 개인 속성을 시스템이 임의로 단정하지 않는다.

대신 다음처럼 관찰 가능한 값으로 표현한다.

- `declared_affiliation`: bio 등에 명시적으로 공개된 소속·지지 표현
- `topic_distribution`: 팔로잉 네트워크의 주제 분포
- `public_association`: 공개 관계망에서 관찰된 계정·기관 연결
- `evidence`: 분석 근거
- `confidence`: 규칙 또는 모델의 신뢰도

관계성 또한 “조직 계정”, “같은 세력”으로 확정하지 않고 **Following Similarity, 공통 팔로잉 비율, 생성 시기, 중심노드 집중도** 같은 측정 가능한 신호로 표시한다.

---

## 3. 기술 스택

### Runtime

- Python 3.12+
- FastAPI
- Uvicorn

### Database

- SQLite
- SQLAlchemy 2.x

기본 DB 경로:

```text
data/x_network.db
```

### Data / Network Analysis

- pandas
- NetworkX
- scikit-learn

### HTTP / Validation

- httpx
- Pydantic v2

### Local Web UI

MVP는 FastAPI가 정적 HTML/JS를 제공하는 단순 구조로 시작한다.

- HTML / CSS / JavaScript
- Cytoscape.js: Relationship Graph

React/Vite는 UI 복잡도가 실제로 커질 때 별도 프론트엔드로 분리한다.

### Scheduling

초기에는 수동 수집을 기본으로 한다. 자동 수집이 필요한 시점에 APScheduler를 선택적으로 추가한다.

---

## 4. 실행 구조

```text
python -m xni
     │
     ├── FastAPI Local Server
     │      └── http://127.0.0.1:8000
     │
     ├── Provider Layer
     │      ├── SorsaProvider
     │      ├── ManualImportProvider
     │      └── FutureProvider
     │
     ├── SQLite
     │      └── data/x_network.db
     │
     └── Analysis Engine
            ├── Snapshot Diff
            ├── Similarity
            ├── Centrality
            ├── Cohort
            ├── Classification
            └── Trend
```

---

## 5. 모듈 구조

```text
src/xni/
├── __init__.py
├── __main__.py
├── app.py
├── config.py
├── db.py
├── models.py
├── schemas.py
├── providers/
│   ├── base.py
│   ├── manual.py
│   └── sorsa.py
├── services/
│   ├── snapshots.py
│   └── targets.py
├── analysis/
│   ├── similarity.py
│   ├── centrality.py
│   ├── cohorts.py
│   ├── classification.py
│   └── trends.py
└── web/
    ├── index.html
    └── app.js
```

각 모듈은 한 가지 책임만 가진다. 데이터 공급자가 바뀌어도 분석엔진과 DB 모델은 영향을 받지 않아야 한다.

---

## 6. 주요 기능

### 6.1 Target Management

분석할 X 계정을 등록하고 관리한다.

주요 필드:

- username
- external user id
- display name
- tracking status
- first tracked at
- last collected at

### 6.2 Following Snapshot

타깃의 팔로잉 목록을 시점별로 저장한다.

```text
Target
  ↓
Provider
  ↓
Raw Snapshot
  ↓
Normalize
  ↓
Accounts + Relationships
  ↓
Diff Engine
```

각 스냅샷마다 원본 응답과 정규화된 관계를 함께 보관한다.

### 6.3 Relationship Diff

연속 스냅샷을 비교해 다음 이벤트를 만든다.

- NEW_FOLLOWING
- REMOVED_FOLLOWING_CANDIDATE
- PROFILE_CHANGED

### 6.4 Account Profile Normalization

내부 공통 모델:

```python
class NetworkAccount(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    description: str | None = None
    followers_count: int | None = None
    following_count: int | None = None
    tweets_count: int | None = None
    created_at: datetime | None = None
    verified: bool = False
    protected: bool = False
    profile_image_url: str | None = None
```

### 6.5 Topic / Account Category Classification

bio와 공개 메타데이터를 기반으로 계정 분야를 태깅한다.

초기 카테고리:

- Politics / Society
- Media / Journalist
- Economy / Finance
- Investment
- Business / CEO
- Technology
- AI
- Crypto
- Sports
- Entertainment
- Creator
- Public Figure
- Organization
- Fan Account
- General Individual
- Unknown

초기에는 규칙 기반 분류를 우선한다.

### 6.6 Public Association Analysis

bio 등에 명시된 공개 관계 정보를 별도로 추출한다.

- 조직명
- 정당명
- 회사명
- 언론사
- 프로젝트
- 주요 인물명
- 브랜드
- 기술 키워드

### 6.7 Following Similarity

MVP는 Jaccard Similarity를 기본으로 사용한다.

```text
similarity(A, B) = |A ∩ B| / |A ∪ B|
```

함께 제공:

- shared following count
- shared ratio A
- shared ratio B
- low-following weighted score

팔로잉 수가 적은 신생계정은 동일한 공통 팔로잉 수가 더 큰 의미를 가질 수 있으므로 비율을 반드시 함께 본다.

### 6.8 Following Fingerprint

계정마다 관계망 특성을 지문 형태로 저장한다.

- account age days
- following count
- topic distribution
- common core accounts
- network concentration
- average similarity
- cluster id
- major nodes

### 6.9 New Account Cohort Analysis

신생계정 기준은 설정 가능하게 한다.

초기 preset:

- 30일 이내
- 90일 이내

주요 신호:

- account age similarity
- following count
- common following count
- common following ratio
- Jaccard similarity
- creation cohort similarity
- target concentration
- core-node overlap

결과는 조직성을 단정하지 않고 **Network Cohort Signal**로 제공한다.

### 6.10 Centrality Engine

핵심 차별화 기능이다.

- **Global Hub**: 전체 관계망에서 많이 선택되는 계정
- **Cohort Hub**: 특정 군집에서 집중적으로 선택되는 계정
- **Emerging Hub**: 최근 연결이 증가하기 시작한 계정
- **Rising Node**: 기간별 연결 증가율이 큰 계정
- **Bridge Node**: 서로 다른 군집을 연결하는 계정

MVP 알고리즘:

- Degree Centrality
- Weighted Degree
- Betweenness Centrality
- Shared Following Count
- Growth Rate

추후:

- PageRank
- Eigenvector Centrality
- Community Detection

### 6.11 Relationship Graph

Cytoscape.js로 로컬 브라우저에서 관계망을 탐색한다.

기능:

- 노드 검색
- 카테고리 필터
- 계정 생성일 필터
- Following 수 필터
- Hub 강조
- Bridge Node 강조
- Cohort 강조
- 시간 범위 선택

### 6.12 Network Trend

스냅샷을 시간순으로 비교한다.

- 신규 팔로우
- 제거 관계 후보
- 중심노드 순위 변화
- 새로 등장한 중심노드
- 카테고리 구성 변화
- 신생계정 군집 변화

---

## 7. SQLite 데이터 모델

### targets

- id
- username
- external_user_id
- display_name
- is_active
- first_tracked_at
- last_collected_at

### accounts

- id
- external_user_id
- username
- display_name
- description
- followers_count
- following_count
- tweets_count
- created_at
- verified
- protected
- profile_image_url
- first_seen_at
- last_seen_at

### snapshots

- id
- target_id
- provider
- collected_at
- raw_json
- account_count

### snapshot_accounts

- snapshot_id
- account_id

### relationship_events

- id
- target_id
- account_id
- event_type
- observed_at
- snapshot_id

### account_topics

- id
- account_id
- topic
- source
- evidence
- confidence

### account_associations

- id
- account_id
- association_type
- value
- source
- evidence
- confidence

### analysis_runs

- id
- analysis_type
- target_id
- parameters_json
- result_json
- created_at

분석 캐시는 초기에는 `analysis_runs.result_json`으로 충분히 처리하고, 실제 필요가 생길 때 전용 테이블로 분리한다.

---

## 8. Provider Adapter

데이터 공급자는 다음 인터페이스를 구현한다.

```python
from typing import Protocol

class NetworkProvider(Protocol):
    async def get_following(self, username: str) -> list[NetworkAccount]: ...
```

초기 Provider:

1. `ManualImportProvider`: 저장된 JSON을 가져와 분석할 수 있도록 한다.
2. `SorsaProvider`: Sorsa 정식 API 사용을 위한 Adapter. 키는 환경변수 또는 `.env`에서 읽으며 DB에 평문 저장하지 않는다.

비공식 Playground endpoint 자동 호출을 프로젝트의 기본 Provider로 만들지 않는다.

---

## 9. MVP 범위

### 포함

- Python 프로젝트 실행
- SQLite 자동 초기화
- Target 등록/조회
- JSON 수동 import
- Snapshot 저장
- Relationship Diff
- Jaccard Similarity
- Degree / Betweenness Centrality
- 신생계정 필터 및 Cohort 기본 분석
- 규칙 기반 bio 분류
- 간단한 REST API
- 로컬 대시보드
- Cytoscape 관계 그래프

### MVP에서 제외

- 로그인/회원 시스템
- 클라우드 동기화
- 대규모 실시간 스트리밍
- 유료 결제
- 모바일 앱
- 자동 AI 분석 대량 호출
- 복잡한 커뮤니티 탐지 모델

---

## 10. 개발 단계

### STEP 0 — Local Bootstrap

- Python package 생성
- FastAPI health endpoint
- SQLite 초기화
- `python -m xni` 실행
- pytest 기본 테스트

### STEP 1 — Core Data Model

- SQLAlchemy 모델
- Target CRUD
- Account upsert
- Snapshot 저장

### STEP 2 — Provider Layer

- Provider Protocol
- Manual JSON Import
- Sorsa Adapter 뼈대

### STEP 3 — Relationship Diff

- 신규 관계 탐지
- 제거 후보 탐지
- 이벤트 이력 저장

### STEP 4 — Similarity Engine

- Jaccard
- shared count / ratio
- low-following weighting

### STEP 5 — Centrality Engine

- NetworkX 그래프 빌드
- Degree Centrality
- Betweenness Centrality
- Hub ranking

### STEP 6 — New Account Cohort

- 계정 나이 계산
- 30/90일 cohort
- 공통 핵심노드
- 평균 유사도
- Network Cohort Signal

### STEP 7 — Classification

- 규칙 기반 topic/category
- 공개 affiliation/association evidence 저장

### STEP 8 — Local Dashboard

- Target 선택
- Summary
- Hub ranking
- Cohort table
- Cytoscape graph

### STEP 9 — Trend Analysis

- 7일 / 30일 / 90일
- Hub 변화
- 관심주제 변화
- 관계 변화 timeline

---

## 11. 성공 기준

MVP 완료 기준:

1. `python -m xni`로 로컬 서버가 실행된다.
2. SQLite DB가 자동 생성된다.
3. JSON 파일을 import해 타깃의 팔로잉 스냅샷을 저장할 수 있다.
4. 두 스냅샷을 비교해 신규/제거 관계를 계산할 수 있다.
5. 두 계정의 Following Similarity를 계산할 수 있다.
6. 관계망의 중심노드 순위를 계산할 수 있다.
7. 신생계정 군집의 공통 핵심노드와 유사도를 표시할 수 있다.
8. 브라우저에서 기본 관계 그래프를 확인할 수 있다.
9. 모든 분석 결과는 근거 데이터로 다시 추적할 수 있다.

---

## 12. 현재 상태

**Status: Python Local Architecture Approved**

Cloudflare Workers / D1 중심 설계에서 **Python + FastAPI + SQLite + NetworkX 로컬 구조**로 전환했다.

다음 구현 단계는 **STEP 0 — Local Bootstrap**이다.
