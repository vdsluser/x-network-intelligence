from datetime import datetime, timedelta, timezone
import math

from sqlalchemy.orm import Session

from xni.analysis.fingerprint import build_following_fingerprint
from xni.db import create_engine_for_path, init_database
from xni.models import Account, AccountAssociation, AccountClassification, AccountTopic, Target, TargetRelationship

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def _rel(target, account):
    return TargetRelationship(target_id=target.id, account_id=account.id, first_seen_at=NOW, last_seen_at=NOW, is_active=True)


def test_fingerprint_v2_adds_semantic_distribution_metrics(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db"); init_database(engine)
    with Session(engine) as session:
        a1 = Account(external_user_id="1", username="a1", created_at=NOW-timedelta(days=1000), following_count=500, first_seen_at=NOW, last_seen_at=NOW)
        a2 = Account(external_user_id="2", username="a2", created_at=NOW-timedelta(days=1000), following_count=500, first_seen_at=NOW, last_seen_at=NOW)
        a3 = Account(external_user_id="3", username="a3", created_at=NOW-timedelta(days=1000), following_count=500, first_seen_at=NOW, last_seen_at=NOW)
        session.add_all([a1,a2,a3]); session.flush()
        target = Target(username="alpha", first_tracked_at=NOW); session.add(target); session.flush()
        session.add_all([_rel(target,a1),_rel(target,a2),_rel(target,a3)])
        for row in [
            AccountTopic(account_id=a1.id, topic="AI", source="bio_rule", evidence="AI", confidence=.95, classifier_version="rule-v1", analyzed_at=NOW),
            AccountTopic(account_id=a1.id, topic="Technology", source="bio_rule", evidence="Python", confidence=.85, classifier_version="rule-v1", analyzed_at=NOW),
            AccountTopic(account_id=a2.id, topic="AI", source="bio_rule", evidence="LLM", confidence=.95, classifier_version="rule-v1", analyzed_at=NOW),
        ]: session.add(row)
        session.add_all([
            AccountClassification(account_id=a1.id, account_type="Individual", source="bio_rule", evidence="researcher", confidence=.85, classifier_version="rule-v1", analyzed_at=NOW),
            AccountClassification(account_id=a2.id, account_type="Company", source="bio_rule", evidence="company", confidence=.95, classifier_version="rule-v1", analyzed_at=NOW),
            AccountClassification(account_id=a3.id, account_type="Unknown", source="default", evidence="", confidence=1.0, classifier_version="rule-v1", analyzed_at=NOW),
            AccountAssociation(account_id=a1.id, association_type="company", value="ExampleAI", normalized_value="exampleai", source="bio_mention", evidence="@ExampleAI", confidence=.9, classifier_version="rule-v1", analyzed_at=NOW),
            AccountAssociation(account_id=a2.id, association_type="company", value="ExampleAI", normalized_value="exampleai", source="bio_mention", evidence="@ExampleAI", confidence=.9, classifier_version="rule-v1", analyzed_at=NOW),
        ])
        session.commit()
        fp = build_following_fingerprint(session, "alpha", as_of=NOW, classifier_version="rule-v1")

    topics = {row.topic: row for row in fp.topic_distribution}
    assert topics["AI"].account_count == 2
    assert topics["AI"].share == 2/3
    assert topics["Technology"].share == 1/3
    assert fp.top_topics[0].topic == "AI"
    assert math.isclose(fp.topic_concentration, 5/9, rel_tol=1e-9)
    assert math.isclose(fp.topic_diversity, 0.9182958340544894, rel_tol=1e-9)
    types = {row.account_type: row for row in fp.account_type_distribution}
    assert types["Individual"].share == 1/3
    assert types["Company"].share == 1/3
    assert types["Unknown"].share == 1/3
    assert fp.classified_account_count == 2
    assert fp.unclassified_account_count == 1
    assert fp.unclassified_ratio == 1/3
    assert fp.public_associations[0].normalized_value == "exampleai"
    assert fp.public_associations[0].account_count == 2
    assert fp.classifier_version == "rule-v1"
    engine.dispose()


def test_fingerprint_without_classification_is_still_valid(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db"); init_database(engine)
    with Session(engine) as session:
        a = Account(external_user_id="1", username="a", first_seen_at=NOW, last_seen_at=NOW)
        session.add(a); session.flush(); target=Target(username="alpha", first_tracked_at=NOW); session.add(target);session.flush();session.add(_rel(target,a));session.commit()
        fp = build_following_fingerprint(session, "alpha", as_of=NOW)
    assert fp.topic_distribution == []
    assert fp.account_type_distribution == []
    assert fp.classified_account_count == 0
    assert fp.unclassified_account_count == 1
    assert fp.unclassified_ratio == 1.0
    assert fp.topic_concentration == 0.0
    assert fp.topic_diversity == 0.0
    engine.dispose()
