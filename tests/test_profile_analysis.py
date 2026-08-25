from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from xni.analysis.profiles import analyze_account_profile, find_new_account_candidates
from xni.db import create_engine_for_path, init_database
from xni.models import Account

AS_OF = datetime(2026, 8, 25, tzinfo=timezone.utc)


def _account(external_id: str, username: str, age_days: int, following: int) -> Account:
    return Account(
        external_user_id=external_id,
        username=username,
        created_at=AS_OF - timedelta(days=age_days),
        following_count=following,
        followers_count=10,
        tweets_count=20,
        first_seen_at=AS_OF,
        last_seen_at=AS_OF,
    )


def test_analyze_account_profile_uses_explicit_thresholds():
    account = _account("1", "new_small", 20, 12)
    signal = analyze_account_profile(account, as_of=AS_OF, new_account_days=90, low_following_max=100)
    assert signal.age_days == 20
    assert signal.is_new_account is True
    assert signal.is_low_following is True
    assert signal.new_account_days == 90
    assert signal.low_following_max == 100


def test_find_new_account_candidates_requires_both_signals(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    with Session(engine) as session:
        session.add_all([
            _account("1", "new_small", 20, 12),
            _account("2", "old_small", 200, 12),
            _account("3", "new_large", 20, 500),
        ])
        session.commit()
        candidates = find_new_account_candidates(
            session, as_of=AS_OF, new_account_days=90, low_following_max=100
        )
    assert [item.username for item in candidates] == ["new_small"]
