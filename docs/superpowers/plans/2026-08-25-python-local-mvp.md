# Python Local MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** X Network Intelligence를 Python + FastAPI + SQLite 기반으로 로컬에서 실행 가능한 최소 MVP 골격으로 전환한다.

**Architecture:** `src/xni` 패키지가 FastAPI 서버와 SQLite 연결을 소유하고, Provider와 분석엔진은 독립 모듈로 분리한다. STEP 0에서는 데이터 수집이나 고급 분석을 구현하지 않고, 이후 단계가 안전하게 붙을 수 있도록 실행·설정·DB·health endpoint·테스트 기반을 먼저 만든다.

**Tech Stack:** Python 3.12+, FastAPI, Uvicorn, SQLAlchemy 2.x, Pydantic v2, httpx, NetworkX, pandas, scikit-learn, pytest

**Spec:** `docs/PROJECT_PLAN.md`

## Global Constraints

- 로컬 실행을 기본으로 한다.
- 기본 DB 경로는 `data/x_network.db`이다.
- `python -m xni`로 실행 가능해야 한다.
- 데이터 공급자는 Provider Adapter로 분리한다.
- 비공식 Playground endpoint 자동 호출을 기본 Provider로 구현하지 않는다.
- 민감한 개인 속성을 임의로 단정하지 않는다.
- GitHub Actions는 이 단계에서 사용하지 않는다.

---

## File Structure

- `pyproject.toml`: Python 패키지 메타데이터, 런타임/개발 의존성, pytest 설정
- `.gitignore`: 가상환경, 캐시, 로컬 DB, 환경변수 파일 제외
- `src/xni/__init__.py`: 패키지 버전
- `src/xni/config.py`: 로컬 경로와 앱 설정
- `src/xni/db.py`: SQLAlchemy engine/session 및 DB 초기화
- `src/xni/models.py`: STEP 0에서 필요한 최소 `Target` 모델
- `src/xni/app.py`: FastAPI 앱 생성, lifespan에서 DB 초기화, health endpoint
- `src/xni/__main__.py`: `python -m xni` 실행 진입점
- `src/xni/providers/base.py`: 미래 Provider 구현이 따라야 할 Protocol
- `tests/test_config.py`: 데이터 경로 생성 규칙 검증
- `tests/test_db.py`: SQLite 초기화 검증
- `tests/test_app.py`: health endpoint 검증
- `README.md`: Python 로컬 실행법과 현재 MVP 상태 반영

---

### Task 1: Package Bootstrap and Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/xni/__init__.py`
- Create: `src/xni/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings(database_path: Path, host: str, port: int)`
- Produces: `get_settings() -> Settings`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from xni.config import Settings


def test_settings_creates_parent_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "x_network.db"
    settings = Settings(database_path=db_path)
    settings.ensure_directories()
    assert db_path.parent.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL because `xni.config` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    database_path: Path = Path("data/x_network.db")
    host: str = "127.0.0.1"
    port: int = 8000

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
```

`pyproject.toml`은 `src` layout을 사용하고 FastAPI, Uvicorn, SQLAlchemy, Pydantic, httpx, NetworkX, pandas, scikit-learn과 pytest/httpx 개발 의존성을 선언한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore src/xni/__init__.py src/xni/config.py tests/test_config.py
git commit -m "chore: bootstrap local Python package"
```

---

### Task 2: SQLite Initialization

**Files:**
- Create: `src/xni/models.py`
- Create: `src/xni/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `Settings.database_path`
- Produces: `Base`
- Produces: `Target`
- Produces: `create_engine_for_path(database_path: Path) -> Engine`
- Produces: `init_database(engine: Engine) -> None`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from sqlalchemy import inspect

from xni.db import create_engine_for_path, init_database


def test_init_database_creates_targets_table(tmp_path: Path) -> None:
    db_path = tmp_path / "x_network.db"
    engine = create_engine_for_path(db_path)
    init_database(engine)
    assert "targets" in inspect(engine).get_table_names()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL because DB module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

`Target` 모델은 `id`, `username`, `external_user_id`, `display_name`, `is_active`, `first_tracked_at`, `last_collected_at` 필드를 가진다. `create_engine_for_path`는 SQLite URL을 생성하고 parent directory를 만든다. `init_database`는 `Base.metadata.create_all(engine)`을 호출한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/xni/models.py src/xni/db.py tests/test_db.py
git commit -m "feat: initialize local SQLite database"
```

---

### Task 3: FastAPI App and Health Endpoint

**Files:**
- Create: `src/xni/app.py`
- Create: `src/xni/__main__.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `get_settings()`, `create_engine_for_path()`, `init_database()`
- Produces: `create_app(settings: Settings | None = None) -> FastAPI`
- Produces: `GET /api/health -> {"status":"ok","database":"..."}`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from fastapi.testclient import TestClient

from xni.app import create_app
from xni.config import Settings


def test_health_endpoint(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "x_network.db")
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app.py -v`
Expected: FAIL because app module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

`create_app`는 FastAPI lifespan에서 DB를 초기화하고 `/api/health`를 제공한다. `__main__.py`는 `uvicorn.run("xni.app:app", host=settings.host, port=settings.port)`로 로컬 서버를 실행한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_app.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/xni/app.py src/xni/__main__.py tests/test_app.py
git commit -m "feat: add local FastAPI entrypoint"
```

---

### Task 4: Provider Boundary

**Files:**
- Create: `src/xni/providers/__init__.py`
- Create: `src/xni/providers/base.py`
- Test: `tests/test_provider_contract.py`

**Interfaces:**
- Produces: `NetworkAccount` Pydantic model
- Produces: `NetworkProvider` Protocol with `async get_following(username: str) -> list[NetworkAccount]`

- [ ] **Step 1: Write the failing test**

```python
from xni.providers.base import NetworkAccount


def test_network_account_requires_id_and_username() -> None:
    account = NetworkAccount(id="1", username="example")
    assert account.id == "1"
    assert account.username == "example"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_provider_contract.py -v`
Expected: FAIL because provider contract does not exist yet.

- [ ] **Step 3: Write minimal implementation**

`NetworkAccount`에는 spec의 정규화 필드를 선언하고, `NetworkProvider`는 Python `Protocol`로 정의한다. 실제 Sorsa 호출은 이 Task에서 구현하지 않는다.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_provider_contract.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/xni/providers tests/test_provider_contract.py
git commit -m "feat: define network provider contract"
```

---

### Task 5: Documentation and Full Verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents: local installation, `python -m xni`, DB path, health endpoint, current scope

- [ ] **Step 1: Update README**

README에는 다음 실행 절차를 명시한다.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m xni
```

그리고 `http://127.0.0.1:8000/api/health` 및 `data/x_network.db` 경로를 설명한다.

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest -v`
Expected: all tests PASS.

- [ ] **Step 3: Verify import and CLI entrypoint**

Run: `python -c "from xni.app import create_app; print(create_app().title)"`
Expected: `X Network Intelligence`

Run: `python -m xni`
Expected: Uvicorn starts on `127.0.0.1:8000` and SQLite DB is created.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document local Python MVP"
```

---

## Self-Review

- Spec coverage: STEP 0 Local Bootstrap, SQLite, local server, Provider boundary를 모두 포함한다.
- Scope: Snapshot/Diff/Centrality/Cohort 실제 구현은 다음 계획으로 분리해 STEP 0을 작고 검증 가능하게 유지한다.
- Placeholder scan: 구현에 필요한 함수/타입 이름과 검증 명령을 명시했다.
- Type consistency: `Settings`, `NetworkAccount`, `NetworkProvider`, `create_app`, DB 초기화 함수 이름을 일관되게 사용한다.
