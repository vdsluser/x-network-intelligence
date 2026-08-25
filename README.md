# X Network Intelligence

X 계정의 공개 팔로잉 관계망을 기반으로 **관심 주제, 관계 군집, 중심노드, 신생계정 코호트, 관계 변화**를 분석하는 네트워크 인텔리전스 프로젝트입니다.

단순한 팔로워 수 집계가 아니라 다음 질문에 답하는 것을 목표로 합니다.

- 어떤 계정들이 공통으로 주목받고 있는가?
- 특정 타깃의 팔로잉 네트워크는 어떤 주제에 집중되어 있는가?
- 최근 새롭게 부상하는 중심노드는 누구인가?
- 신생계정들은 어떤 계정군을 선택적으로 팔로우하는가?
- 서로 다른 군집을 연결하는 Bridge Node는 무엇인가?
- 시간에 따라 네트워크의 관심사와 관계 구조는 어떻게 변하는가?

## 핵심 기능

- Target Following Snapshot
- Account Profile Normalization
- Topic / Account Category Classification
- Public Association Analysis
- Following Fingerprint
- Following Similarity
- New Account Cohort Analysis
- Central Node Detection
- Bridge / Emerging / Rising Node Detection
- Relationship Graph
- Network Trend & Change Detection

## 분석 원칙

이 프로젝트는 공개적으로 관찰 가능한 데이터와 관계 구조를 분석합니다.

- 개인의 정치적 성향이나 민감한 속성을 임의로 단정하지 않습니다.
- bio 등에 명시적으로 공개된 소속·관심 주제는 근거와 함께 기록할 수 있습니다.
- “조직 계정”, “세력”처럼 확정적인 결론 대신 관계망 유사도, 생성 시기, 공통 팔로잉 비율 등 측정 가능한 신호를 제공합니다.
- 모든 분석 결과는 가능한 한 근거 데이터와 점수를 함께 표시합니다.

## 기술 방향

초기 MVP는 운영비와 복잡도를 낮추기 위해 Cloudflare 중심의 서버리스 구조를 사용합니다.

- Frontend: React + TypeScript + Vite + Tailwind CSS
- API: Cloudflare Workers + Hono
- Database: Cloudflare D1
- Graph Analysis: Graphology
- Graph Visualization: Cytoscape.js
- Deployment: Cloudflare Pages / Workers
- Data Provider: 교체 가능한 Provider Adapter 구조

자세한 설계, 데이터 모델, 개발 단계와 MVP 범위는 아래 문서를 참고하세요.

- [Project Plan](docs/PROJECT_PLAN.md)

## Status

**Phase: Project Definition / MVP Design**

현재는 데이터 수집 → 스냅샷 → 관계망 분석 → 중심노드/코호트 분석 순서로 MVP를 구축하는 단계입니다.
