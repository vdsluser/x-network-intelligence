# X Network Intelligence — Project Plan

## 1. 프로젝트 정의

**X Network Intelligence**는 X의 공개 계정 및 팔로잉 관계망을 기반으로, 단순 팔로워 수가 아니라 **관심사, 관계 구조, 중심노드, 신생계정 코호트, 군집 변화**를 분석하는 네트워크 인텔리전스 시스템이다.

핵심 질문은 다음과 같다.

1. 타깃 계정은 어떤 계정들을 주로 팔로우하는가?
2. 그 팔로잉 네트워크에는 어떤 주제와 계정 유형이 많은가?
3. 여러 계정이 공통으로 팔로우하는 중심노드는 누구인가?
4. 최근 새롭게 주목받기 시작한 계정은 누구인가?
5. 신생계정들이 적은 팔로잉 수 안에서 공통적으로 선택하는 계정군은 무엇인가?
6. 서로 다른 군집을 연결하는 Bridge Node는 무엇인가?
7. 시간 흐름에 따라 관심 주제와 네트워크 구조가 어떻게 변하는가?

이 프로젝트의 핵심 가치는 **정적인 프로필 조회가 아니라 시간에 따라 변화하는 관계망을 축적하고 비교하는 것**에 있다.

---

## 2. 프로젝트 목적

### 2.1 1차 목적

- 타깃 계정의 공개 팔로잉 네트워크를 구조화한다.
- 팔로잉 계정의 bio와 공개 메타데이터를 분류한다.
- 관계망의 중심노드와 공통 팔로잉 구조를 찾는다.
- 신생계정의 선택적 팔로잉 패턴을 분석한다.
- 스냅샷 간 차이를 통해 네트워크 변화 이력을 만든다.

### 2.2 장기 목적

- 다수 타깃 간 공통 관심 네트워크 비교
- Emerging Hub / Rising Node 탐지
- 관심 주제의 7일 / 30일 / 90일 변화 분석
- 관계 군집 자동 탐색
- Network Timeline 구축
- 사용자 정의 분석 리포트
- 데이터 공급자 교체가 가능한 확장형 구조

---

## 3. 핵심 분석 원칙

### 3.1 관찰 가능한 사실과 추론을 분리

시스템은 다음과 같이 구분한다.

**관찰 데이터**

- 계정 생성일
- 팔로워 수
- 팔로잉 수
- 게시물 수
- bio
- 공개적으로 명시된 직책 / 기관 / 조직 / 관심 키워드
- 타깃과의 팔로잉 관계
- 스냅샷 최초/최근 관측 시각

**분석 데이터**

- 계정 분야
- 주제 태그
- 공통 팔로잉 수
- 팔로잉 유사도
- 중심성
- 군집 집중도
- 신생계정 코호트 신호
- 시간별 증가/감소 추세

### 3.2 민감한 개인 속성 단정 금지

정치, 종교 등 민감할 수 있는 속성을 시스템이 임의로 개인에게 확정적으로 부여하지 않는다.

대신 다음처럼 표현한다.

- `declared_affiliation`: bio 등에 본인이 명시적으로 공개한 소속 또는 지지 표현
- `topic_distribution`: 팔로잉 네트워크에서 관찰된 주제 분포
- `public_association`: 공개 관계망에서 관찰된 계정/기관 연결
- `evidence`: 해당 분석의 근거
- `confidence`: 규칙 또는 모델의 신뢰도

예를 들어 “이 계정은 특정 정치성향이다”라고 단정하는 대신, “팔로잉 네트워크 중 특정 정치·사회 주제를 명시적으로 언급한 계정의 비율이 높다”처럼 관찰 가능한 결과를 제시한다.

### 3.3 관계성은 신호로 표현

다음과 같은 표현을 피한다.

- 조직 계정이다
- 같은 세력이다
- 조작 계정이다

대신 측정 가능한 신호를 제공한다.

- 높은 Following Similarity
- 비슷한 계정 생성 시기
- 낮은 팔로잉 수 대비 높은 공통 팔로잉 비율
- 동일 핵심노드 집중
- 유사한 관계 확장 순서

---

## 4. 주요 기능

## 4.1 Target Management

분석할 X 계정을 등록하고 관리한다.

주요 필드:

- username
- X user id
- display name
- profile image
- tracking status
- first tracked at
- last collected at

---

## 4.2 Following Snapshot

타깃의 팔로잉 목록을 시점별로 저장한다.

목적:

- 현재 팔로잉 네트워크 구성 확인
- 신규 팔로우 탐지
- 관계 제거 후보 탐지
- 관계 변화 이력 구축

원본 응답은 가능하면 그대로 보존한다.

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

---

## 4.3 Account Profile Normalization

서로 다른 데이터 공급자가 반환하는 계정 정보를 하나의 내부 모델로 통일한다.

```ts
interface NetworkAccount {
  id: string
  username: string
  displayName?: string
  description?: string
  followersCount?: number
  followingCount?: number
  tweetsCount?: number
  createdAt?: string
  verified?: boolean
  protected?: boolean
  profileImageUrl?: string
}
```

Provider가 바뀌어도 나머지 분석 모듈은 영향을 받지 않도록 한다.

---

## 4.4 Topic / Account Category Classification

bio와 공개 메타데이터를 기반으로 계정의 주요 분야를 태깅한다.

예시 카테고리:

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

예:

```text
국회의원 → Public Figure + Politics
기자 / reporter → Media
CEO → Business
AI / LLM → AI
주식 / 투자 → Investment
```

규칙으로 판단하기 어려운 경우에만 선택적으로 AI 분류를 사용한다.

---

## 4.5 Public Association Analysis

bio 등에 명시된 공개 관계 정보를 별도로 추출한다.

예:

- 조직명
- 정당명
- 회사명
- 언론사
- 프로젝트
- 주요 인물명
- 브랜드
- 기술 키워드

결과에는 항상 근거를 연결한다.

```json
{
  "type": "organization_mention",
  "value": "Example Organization",
  "source": "bio",
  "evidence": "...",
  "confidence": 1.0
}
```

---

## 4.6 Following Fingerprint

각 계정의 팔로잉 구조를 하나의 네트워크 지문처럼 표현한다.

예시 지표:

- 전체 팔로잉 수
- 관심 분야 비중
- 공통 핵심 계정 수
- 특정 군집 집중도
- 신생계정 여부
- 평균 유사도
- 주요 연결 노드

예:

```text
Account A
────────────────
Account Age          12 days
Following            18
Political/Social     13
Media                 2
Tech                   1
Other                  2

Core-node overlap    11
Network concentration 72%
Cluster               #7
```

---

## 4.7 Following Similarity

두 계정의 팔로잉 관계 유사도를 계산한다.

초기 MVP는 Jaccard Similarity를 사용한다.

```text
similarity(A, B)
=
|A ∩ B| / |A ∪ B|
```

함께 제공할 보조 지표:

- shared following count
- shared following ratio A 기준
- shared following ratio B 기준
- weighted similarity

팔로잉 수가 매우 작은 계정은 동일 수의 공통 연결이 더 큰 의미를 갖기 때문에 단순 공통 개수와 비율을 함께 사용한다.

---

## 4.8 New Account Cohort Analysis

신생계정의 팔로잉 구조를 별도로 분석한다.

신생계정 기준은 사용자 설정이 가능하도록 한다.

초기 기본값 예:

- 계정 생성 30일 이내
- 계정 생성 90일 이내

주요 분석 지표:

- account age days
- following count
- common following count
- common following ratio
- following similarity
- creation cohort similarity
- target concentration
- core-node overlap

### 핵심 가설

팔로잉 수가 매우 적은 신생계정이 동일한 핵심계정을 높은 비율로 공유한다면, 일반적인 대량 팔로잉 계정보다 관계망 유사성이 더 강한 신호일 수 있다.

시스템은 이를 조직성으로 단정하지 않고 **Network Cohort Signal**로 표시한다.

---

## 4.9 Network Cohort Signal

신생계정 군집의 관계 유사도를 복합 점수로 표시한다.

초기 구성 예:

```text
Account Age Similarity      20
Following Similarity        30
Common Core Accounts        20
Low Following Weight        15
Temporal Similarity         15
──────────────────────────────
Total                      100
```

표시는 다음 정도로 단순화한다.

- LOW
- MEDIUM
- HIGH

중요한 원칙은 점수뿐 아니라 근거를 함께 제공하는 것이다.

예:

```text
HIGH

- 9 accounts created within 14 days
- average following count: 21
- average shared following: 15
- mean Jaccard similarity: 0.71
- common core nodes: 11
```

---

## 4.10 Centrality Engine

이 프로젝트의 핵심 차별화 기능이다.

### Global Hub

전체 분석 네트워크에서 가장 많은 연결을 받는 계정.

### Cohort Hub

특정 군집에서 집중적으로 선택되는 계정.

### Emerging Hub

최근 새롭게 연결이 증가하기 시작한 계정.

### Rising Node

7일 / 30일 기준 연결 증가율이 큰 계정.

### Bridge Node

서로 다른 군집을 연결하는 계정.

초기 알고리즘:

- Degree Centrality
- Weighted Degree
- Betweenness Centrality
- Shared Following Count
- Growth Rate

추후:

- PageRank
- Eigenvector Centrality
- Community Detection

---

## 4.11 Relationship Graph

관계망을 시각적으로 탐색할 수 있는 그래프 UI를 제공한다.

노드:

- Target
- Followed Account
- Hub
- Cohort

Edge:

- follows
- shared-following relation
- cohort membership

그래프 기능:

- 노드 검색
- 카테고리 필터
- 계정 생성일 필터
- Following 수 필터
- 특정 군집 강조
- Hub 강조
- Bridge Node 강조
- 시간 범위 선택

---

## 4.12 Network Trend

스냅샷을 시간순으로 비교한다.

분석 예:

```text
Recent Network Change

AI / Technology      +18%
Finance               +4%
Media                  0%
Politics / Society    -8%
```

추적 대상:

- 신규 팔로우
- 제거된 관계 후보
- 새로 등장한 중심노드
- 중심노드 순위 변화
- 카테고리 구성 변화
- 신생계정 군집 변화

---

## 5. 기술 스택

초기 MVP는 운영비와 유지관리 복잡도를 낮추기 위해 Cloudflare 중심 서버리스 구조를 사용한다.

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- Cytoscape.js

### Backend

- Cloudflare Workers
- Hono
- TypeScript

### Database

- Cloudflare D1

초기에는 D1 하나로 시작한다.

추후 필요 시:

- KV: 캐시 / 간단한 설정
- R2: 대량 Raw Snapshot 보관
- Queues: 비동기 분석
- Cron Triggers: 정기 수집

단, MVP에서는 필요하지 않은 Cloudflare 서비스를 미리 추가하지 않는다.

### Graph Analysis

- Graphology
- graphology metrics / algorithms

후보 알고리즘:

- degree
- betweenness
- PageRank
- connected components
- community detection

### AI / NLP

초기에는 비용 절감을 위해 다음 순서를 사용한다.

```text
1. keyword / regex rules
2. dictionary matching
3. deterministic scoring
4. optional AI classification
```

AI 호출은 규칙 기반 분류가 실패한 계정에만 제한적으로 적용한다.

---

## 6. 데이터 Provider 구조

특정 외부 서비스에 강하게 종속되지 않도록 Provider Adapter를 사용한다.

```ts
interface NetworkProvider {
  getFollowing(username: string): Promise<NetworkAccount[]>
  getFollowers?(username: string): Promise<NetworkAccount[]>
  getProfile?(username: string): Promise<NetworkAccount>
  getPosts?(username: string): Promise<NetworkPost[]>
}
```

초기 후보:

```text
SorsaProvider
ManualImportProvider
FutureOfficialProvider
```

Playground 등 비공식 웹 내부 호출은 서비스 약관과 접근 정책을 우회하는 방식으로 설계하지 않는다. MVP에서도 Provider는 쉽게 교체할 수 있도록 만든다.

---

## 7. 시스템 아키텍처

```text
Browser
  │
  ▼
React Dashboard
  │
  ▼
Cloudflare Worker API
  │
  ├── Target Service
  ├── Collection Service
  ├── Normalizer
  ├── Diff Engine
  ├── Classification Engine
  ├── Centrality Engine
  ├── Cohort Engine
  └── Trend Engine
  │
  ├───────────────┐
  ▼               ▼
Cloudflare D1   Provider Adapter
                  │
                  ▼
             External Data Source
```

---

## 8. 데이터 모델

## 8.1 targets

```text
id
username
x_user_id
label
tracking_enabled
created_at
last_collected_at
```

## 8.2 accounts

```text
id
x_user_id
username
display_name
description
followers_count
following_count
tweets_count
account_created_at
verified
protected
profile_image_url
first_seen_at
last_seen_at
raw_json
```

## 8.3 snapshots

```text
id
target_id
provider
collected_at
account_count
raw_json
```

## 8.4 relationships

```text
id
source_account_id
target_account_id
relationship_type
first_seen_at
last_seen_at
active
```

초기 relationship_type:

- following

추후:

- shared_following
- cohort_member

## 8.5 account_analysis

```text
account_id
categories_json
topics_json
public_associations_json
activity_score
network_score
analysis_version
analyzed_at
```

## 8.6 network_metrics

```text
account_id
target_id
degree_score
betweenness_score
pagerank_score
hub_type
calculated_at
```

## 8.7 cohorts

```text
id
target_id
name
cohort_type
score
metadata_json
created_at
```

## 8.8 cohort_members

```text
cohort_id
account_id
similarity_score
joined_at
```

---

## 9. 핵심 계산 지표

### Account Age

```text
current_time - account_created_at
```

### Tweets per Day

```text
tweets_count / account_age_days
```

### Follower / Following Ratio

```text
followers_count / max(following_count, 1)
```

### Target Concentration

```text
cluster_related_following / total_following
```

### Jaccard Similarity

```text
shared_following / unique_following_union
```

### Hub Growth

```text
(current_connections - previous_connections)
/ max(previous_connections, 1)
```

### New Account Weight

팔로잉 수가 적을수록 공통 연결 하나의 의미가 커지도록 가중치를 적용한다.

정확한 수식은 실제 수집 데이터를 확인한 뒤 튜닝한다.

---

## 10. 화면 구성

## Dashboard

표시 항목:

- tracked targets
- total discovered accounts
- active relationships
- new relationships
- new accounts
- top hubs
- emerging hubs
- recent cohort signals

## Target Detail

탭 구성:

```text
Overview
Following
Topics
Network
Cohorts
Central Nodes
Timeline
```

## Network Graph

- 그래프 확대/축소
- 선택 노드 상세 정보
- 중심노드 강조
- 신생계정만 표시
- 특정 카테고리만 표시
- 군집별 필터

## Central Nodes

```text
Global Hub
Emerging Hub
Cohort Hub
Bridge Node
Rising Node
```

## Cohorts

```text
Cohort #12
Accounts              23
Average Account Age   16 days
Average Following     24
Common Core Nodes     14
Mean Similarity       0.76
Signal                HIGH
```

---

## 11. MVP 범위

MVP는 너무 많은 기능을 한 번에 구현하지 않는다.

### MVP 필수

1. Target 등록
2. Following 데이터 수집
3. Raw JSON 저장
4. Account 정규화
5. Snapshot 저장
6. Snapshot Diff
7. bio 기반 카테고리 분류
8. Following Similarity
9. 신생계정 필터
10. Central Node 계산
11. 기본 Network Graph
12. Target Dashboard

### MVP 이후

- AI 고급 분류
- 게시물 내용 분석
- Bridge Node 고급 알고리즘
- 자동 Community Detection
- Network Trend 예측
- 알림
- 다중 사용자 계정
- 유료 서비스 기능

---

## 12. 개발 단계

## STEP 0 — Repository Bootstrap

목표:

- 기본 프로젝트 구조 생성
- Frontend / Worker 분리
- 개발환경 구축
- D1 설정

권장 구조:

```text
/
├─ apps/
│  ├─ web/
│  └─ worker/
├─ packages/
│  ├─ core/
│  ├─ providers/
│  └─ graph/
├─ migrations/
├─ docs/
└─ README.md
```

완료 기준:

- local dev 실행
- Worker health endpoint 확인
- D1 연결 확인

---

## STEP 1 — Data Collection

목표:

- Target 등록
- Provider Adapter 구현
- Following 데이터 수집
- 원본 응답 저장

완료 기준:

- 한 개의 타깃을 입력하여 계정 목록을 수집할 수 있음
- accounts / snapshots 저장 성공

---

## STEP 2 — Relationship Engine

목표:

- target → following 관계 생성
- first_seen / last_seen 저장
- snapshot diff 구현

완료 기준:

- 신규 관계 탐지
- 이전 관계와 현재 관계 비교 가능

---

## STEP 3 — Account Intelligence

목표:

- account age
- tweets/day
- follower/following ratio
- bio keyword classification
- public association extraction

완료 기준:

- 계정별 기본 분석 카드 표시

---

## STEP 4 — Centrality Engine

목표:

- Global Hub
- Cohort Hub
- Degree Centrality
- 기본 Ranking

완료 기준:

- 타깃 네트워크에서 중심 계정 TOP N 표시

---

## STEP 5 — New Account Cohort

목표:

- 신생계정 필터
- low-following 계정 가중치
- Jaccard Similarity
- 공통 핵심 노드 계산

완료 기준:

- 유사한 신생계정 그룹을 찾고 근거 지표를 보여줌

---

## STEP 6 — Network Graph UI

목표:

- 노드/엣지 시각화
- 중심노드 강조
- 신생계정 강조
- 필터 기능

완료 기준:

- 네트워크를 시각적으로 탐색 가능

---

## STEP 7 — Trend Engine

목표:

- 기간별 관계 변화
- Hub 순위 변화
- 주제 구성 변화

완료 기준:

- 7D / 30D 네트워크 변화 리포트 제공

---

## STEP 8 — Production Hardening

목표:

- rate limit
- retry
- error logging
- secret 관리
- 데이터 보존 정책
- API 비용 제어

완료 기준:

- 장시간 운영 시에도 예측 가능한 비용과 안정성을 유지

---

## 13. 비용 절감 전략

### 원칙 1 — 수집 횟수를 최소화

MVP는 실시간보다 저빈도 스냅샷을 우선한다.

### 원칙 2 — 동일 계정 중복 분석 금지

한 번 분석한 계정은 profile 변경이 감지되기 전까지 분석 결과를 재사용한다.

### 원칙 3 — AI는 마지막 단계

규칙 기반으로 처리할 수 있는 데이터는 AI로 보내지 않는다.

### 원칙 4 — 전체 Raw Snapshot 중복 저장을 관리

초기에는 D1에 저장하되 데이터량이 커지면 R2로 이동한다.

### 원칙 5 — GitHub Actions 최소화

빌드/테스트 자동화가 필요해질 때 Actions 사용량과 비용을 먼저 확인하고 적용한다.

---

## 14. 보안

- API Key를 프론트엔드에 노출하지 않는다.
- Provider Secret은 Worker Secret으로 관리한다.
- 사용자 입력 username 검증
- API rate limit 적용
- SQL parameter binding 사용
- Raw 데이터와 분석 데이터 분리
- 외부 API 응답을 신뢰하지 않고 validation 수행

---

## 15. 데이터 품질

각 분석 결과에는 가능하면 다음 메타데이터를 둔다.

```text
source
collected_at
analysis_version
confidence
evidence
```

이를 통해 분석 알고리즘이 변경되어도 과거 결과를 재현하고 비교할 수 있다.

---

## 16. 분석 버전 관리

분류 및 점수 계산 알고리즘은 버전 번호를 가진다.

예:

```text
classification-v1
centrality-v1
cohort-v1
```

알고리즘 개선 후 과거 데이터를 다시 계산할 수 있도록 한다.

---

## 17. MVP 성공 기준

MVP가 성공했다고 판단하는 기준:

1. 타깃 하나를 입력하면 팔로잉 네트워크를 수집할 수 있다.
2. 동일 타깃을 다시 수집하면 이전 스냅샷과 차이를 계산할 수 있다.
3. 팔로잉 계정의 주요 주제와 계정 분야를 자동 분류할 수 있다.
4. 팔로잉 수가 적은 신생계정을 별도로 식별할 수 있다.
5. 신생계정 간 Following Similarity를 계산할 수 있다.
6. 공통 핵심노드를 찾을 수 있다.
7. Global Hub / Cohort Hub를 화면에 표시할 수 있다.
8. 그래프에서 계정 관계를 탐색할 수 있다.
9. 모든 분석 결과에 근거가 표시된다.
10. 데이터 공급자를 나중에 교체할 수 있다.

---

## 18. 우선 개발 순서

가장 먼저 만들 기능은 다음 다섯 가지다.

```text
1. Provider Adapter
2. Snapshot Storage
3. Relationship Diff
4. Following Similarity
5. Centrality Engine
```

그 다음:

```text
6. New Account Cohort
7. Account Classification
8. Network Graph
9. Trend Analysis
```

이 순서를 추천하는 이유는 AI나 복잡한 UI보다 먼저 **관계망 데이터 자체가 정확히 쌓이는 구조**를 확보해야 하기 때문이다.

---

## 19. 최종 방향

X Network Intelligence의 핵심은 다음 흐름이다.

```text
FOLLOWING
   ↓
SNAPSHOT
   ↓
RELATIONSHIP
   ↓
SIMILARITY
   ↓
COHORT
   ↓
CENTRAL NODE
   ↓
TREND
   ↓
NETWORK INTELLIGENCE
```

즉, 단순한 “누가 누구를 팔로우한다”는 정보를 넘어 **어떤 관계망이 만들어지고 있고, 어떤 계정이 그 관계망의 중심이 되며, 어떤 관심사가 새롭게 부상하는지**를 시간축으로 분석하는 프로젝트를 목표로 한다.

---

## 20. 현재 상태

**Status: Project Definition Complete**

다음 구현 단계는 **STEP 0 — Repository Bootstrap**이다.
