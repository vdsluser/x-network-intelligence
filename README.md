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

상태 확인:

```text
http://127.0.0.1:8000/api/health
```

## 수동 Following Snapshot 가져오기

현재 MVP는 Sorsa Playground 등에서 확인한 **응답 JSON 객체 자체**를 수동으로 가져올 수 있습니다. `users`, `targetLabel`, `mode: "following"`을 포함한 JSON을 그대로 `POST /api/import/manual`에 전달합니다.

예시:

```json
{
  "users": [
    {
      "id": "123",
      "username": "alice",
      "display_name": "Alice",
      "description": "AI researcher",
      "followers_count": 100,
      "followings_count": 20,
      "created_at": "Sun Nov 05 08:05:40 +0000 2023",
      "tweets_count": 200,
      "verified": false,
      "protected": false,
      "profile_image_url": "https://example.com/alice.jpg"
    }
  ],
  "targetLabel": "target_user",
  "mode": "following"
}
```

응답 예:

```json
{
  "target": "target_user",
  "snapshot_id": 1,
  "total": 1,
  "added": 1,
  "removed": 0,
  "unchanged": 0
}
```

두 번째 Snapshot부터 직전 활성 관계와 비교해 다음 값을 계산합니다.

- `added`: 새롭게 관측된 팔로잉
- `removed`: 이전 Snapshot에는 있었으나 현재 Snapshot에서 보이지 않는 관계
- `unchanged`: 두 Snapshot에 모두 존재하는 관계

`removed`는 관측 결과이며, 계정이 왜 관계에서 사라졌는지까지 단정하지 않습니다.

## SQLite에 보존하는 데이터

- `targets` — 추적 대상
- `accounts` — 발견된 X 계정과 최신 공개 메타데이터
- `following_snapshots` — 수집 시점과 전체 원본 JSON
- `snapshot_members` — 각 Snapshot에 포함된 계정과 해당 원본 user JSON
- `target_relationships` — 현재 활성/비활성 팔로잉 관계와 최초/최근 관측 시점
- `relationship_events` — added / removed 변화 이벤트

원본 JSON을 함께 보관하므로 향후 분석 알고리즘을 개선한 뒤 과거 Snapshot을 다시 분석할 수 있습니다.

## 핵심 기능 로드맵

1. ✅ Target / Account / Snapshot 저장
2. ✅ Relationship Diff
3. Following Similarity
4. Following Fingerprint
5. New Account Cohort Analysis
6. Central Node / Bridge Node / Rising Node
7. Topic & Public Association Classification
8. Local Relationship Graph
9. Network Trend Analysis

## 분석 원칙

- 개인의 정치·종교 등 민감한 속성을 임의로 단정하지 않습니다.
- bio 등에 명시적으로 공개된 소속·관심 표현은 근거와 함께 기록할 수 있습니다.
- 조직성·세력 여부를 확정하지 않고, 팔로잉 유사도·공통 팔로잉 비율·계정 생성 시기·중심노드 집중도 같은 측정 가능한 신호를 제공합니다.
- 원본 데이터를 보존해 분석 알고리즘 개선 후 재분석할 수 있게 설계합니다.

## 데이터 Provider

Provider는 교체 가능한 인터페이스로 분리합니다.

- `ManualImportProvider` — JSON 수동 가져오기
- `SorsaProvider` — 정식 API Adapter(향후)
- 향후 추가 Provider

비공식 Playground endpoint 자동 호출을 기본 Provider로 구현하지 않습니다.

## 문서

- [Project Plan](docs/PROJECT_PLAN.md)
- [Python Local MVP Implementation Plan](docs/superpowers/plans/2026-08-25-python-local-mvp.md)
- [Manual Import + Snapshot Diff Plan](docs/superpowers/plans/2026-08-25-manual-import-snapshot.md)

## 현재 상태

**STEP 2 — Manual Import + Snapshot Diff**

현재 구현:

- `python -m xni` 로컬 실행
- FastAPI `/api/health`
- FastAPI `POST /api/import/manual`
- SQLite 자동 초기화
- Sorsa 형태 JSON → 내부 `NetworkAccount` 정규화
- 계정 메타데이터 및 원본 JSON 저장
- Snapshot별 관계 저장
- added / removed / unchanged Diff
- 관계 변화 이벤트 이력
- pytest 테스트
