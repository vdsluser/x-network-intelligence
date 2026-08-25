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

서버가 실행되면 다음 주소에서 상태를 확인할 수 있습니다.

```text
http://127.0.0.1:8000/api/health
```

정상 응답 예:

```json
{
  "status": "ok",
  "database": "data/x_network.db"
}
```

## 핵심 기능 로드맵

1. Target / Account / Snapshot 저장
2. Relationship Diff
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
- `SorsaProvider` — 정식 API Adapter
- 향후 추가 Provider

비공식 Playground endpoint 자동 호출을 기본 Provider로 구현하지 않습니다.

## 문서

- [Project Plan](docs/PROJECT_PLAN.md)
- [Python Local MVP Implementation Plan](docs/superpowers/plans/2026-08-25-python-local-mvp.md)

## 현재 상태

**STEP 0 — Local Bootstrap**

현재 골격은 다음을 제공합니다.

- `python -m xni` 로컬 실행 진입점
- FastAPI 앱
- `/api/health`
- SQLite 자동 초기화
- 최소 `Target` 모델
- `NetworkAccount` / `NetworkProvider` 계약
- pytest 기본 테스트
