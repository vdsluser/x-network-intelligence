from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from xni.analysis.classification.service import ClassificationRunRequest, get_account_classification_detail, run_classification
from xni.db import create_engine_for_path, init_database
from xni.models import Account, AccountAssociation, AccountClassification, AccountTopic, ClassificationRun, FollowingSnapshot, SnapshotMember, Target


def _seed(session: Session):
    now = datetime.now(timezone.utc)
    target = Target(username="target", first_tracked_at=now)
    session.add(target); session.flush()
    accounts = [
        Account(external_user_id="1", username="ai_dev", description="AI researcher | LLM | Python", first_seen_at=now, last_seen_at=now),
        Account(external_user_id="2", username="news", description="경제 전문 기자 | 뉴스룸", first_seen_at=now, last_seen_at=now),
        Account(external_user_id="3", username="blank", description="hello world", first_seen_at=now, last_seen_at=now),
    ]
    session.add_all(accounts); session.flush()
    snapshot = FollowingSnapshot(target_id=target.id, provider="manual", collected_at=now, raw_json={"users": []})
    session.add(snapshot); session.flush()
    session.add_all([
        SnapshotMember(snapshot_id=snapshot.id, account_id=accounts[0].id, position=0, raw_json={"id": "1", "bio_urls": [{"expanded_url": "https://example.ai/about"}]}),
        SnapshotMember(snapshot_id=snapshot.id, account_id=accounts[1].id, position=1, raw_json={"id": "2"}),
        SnapshotMember(snapshot_id=snapshot.id, account_id=accounts[2].id, position=2, raw_json={"id": "3"}),
    ])
    session.commit()
    return accounts


def test_classification_run_persists_versioned_results_and_audit_row(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db"); init_database(engine)
    with Session(engine) as session:
        accounts = _seed(session)
        summary = run_classification(session, ClassificationRunRequest())
        assert summary.classifier_version == "rule-v1"
        assert summary.accounts_processed == 3
        assert summary.accounts_with_topics == 2
        assert summary.accounts_unknown == 1
        assert summary.topics_created >= 4
        assert summary.associations_created >= 2
        assert session.scalar(select(func.count()).select_from(AccountClassification)) == 3
        assert session.scalar(select(func.count()).select_from(ClassificationRun)) == 1
        detail = get_account_classification_detail(session, accounts[0].id)
        assert detail.account_type == "Individual"
        assert {row.topic for row in detail.topics} >= {"AI", "Technology", "ScienceResearch"}
        assert any(row.association_type == "domain" and row.value == "example.ai" for row in detail.associations)
    engine.dispose()


def test_replace_version_is_idempotent_for_derived_rows(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db"); init_database(engine)
    with Session(engine) as session:
        _seed(session)
        first = run_classification(session, ClassificationRunRequest())
        counts1 = (
            session.scalar(select(func.count()).select_from(AccountTopic)),
            session.scalar(select(func.count()).select_from(AccountClassification)),
            session.scalar(select(func.count()).select_from(AccountAssociation)),
        )
        second = run_classification(session, ClassificationRunRequest(replace_version=True))
        counts2 = (
            session.scalar(select(func.count()).select_from(AccountTopic)),
            session.scalar(select(func.count()).select_from(AccountClassification)),
            session.scalar(select(func.count()).select_from(AccountAssociation)),
        )
        assert counts2 == counts1
        assert second.topics_created == first.topics_created
        assert session.scalar(select(func.count()).select_from(ClassificationRun)) == 2
    engine.dispose()


def test_unknown_classifier_version_is_rejected(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db"); init_database(engine)
    with Session(engine) as session:
        _seed(session)
        with pytest.raises(ValueError, match="classifier_version"):
            run_classification(session, ClassificationRunRequest(classifier_version="rule-v2"))
    engine.dispose()


def test_missing_account_detail_raises_value_error(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db"); init_database(engine)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="account not found"):
            get_account_classification_detail(session, 999)
    engine.dispose()


def test_failed_replace_version_rolls_back_previous_derived_rows(tmp_path, monkeypatch):
    import xni.analysis.classification.service as service
    engine = create_engine_for_path(tmp_path / "xni.db"); init_database(engine)
    with Session(engine) as session:
        _seed(session)
        run_classification(session, ClassificationRunRequest())
        before = (
            session.scalar(select(func.count()).select_from(AccountTopic)),
            session.scalar(select(func.count()).select_from(AccountClassification)),
            session.scalar(select(func.count()).select_from(AccountAssociation)),
        )
        session.commit()
        def boom(_text):
            raise RuntimeError("classifier failure")
        monkeypatch.setattr(service, "classify_topics", boom)
        with pytest.raises(RuntimeError, match="classifier failure"):
            run_classification(session, ClassificationRunRequest(replace_version=True))
        after = (
            session.scalar(select(func.count()).select_from(AccountTopic)),
            session.scalar(select(func.count()).select_from(AccountClassification)),
            session.scalar(select(func.count()).select_from(AccountAssociation)),
        )
        assert after == before
    engine.dispose()
