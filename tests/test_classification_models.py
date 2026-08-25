from datetime import datetime, timezone
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xni.db import create_engine_for_path, init_database
from xni.models import Account, AccountTopic


def test_classification_tables_are_created(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    names = set(inspect(engine).get_table_names())
    assert {"account_topics", "account_classifications", "account_associations", "classification_runs"} <= names


def test_account_topic_is_unique_per_account_topic_version(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        account = Account(external_user_id="1", username="a", first_seen_at=now, last_seen_at=now)
        session.add(account)
        session.flush()
        row = dict(account_id=account.id, topic="AI", source="bio_rule", evidence="AI", confidence=0.95, classifier_version="rule-v1", analyzed_at=now)
        session.add(AccountTopic(**row))
        session.commit()
        session.add(AccountTopic(**row))
        with pytest.raises(IntegrityError):
            session.commit()
