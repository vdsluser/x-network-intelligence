from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from xni.analysis.graph import build_graph, build_graph_options
from xni.db import create_engine_for_path, init_database
from xni.models import Account, AccountClassification, AccountTopic, Target, TargetRelationship

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def account(external_id: str, username: str, *, age_days: int = 500) -> Account:
    return Account(
        external_user_id=external_id,
        username=username,
        display_name=username.title(),
        followers_count=100,
        following_count=50,
        created_at=NOW - timedelta(days=age_days),
        first_seen_at=NOW,
        last_seen_at=NOW,
    )


def rel(target: Target, acct: Account) -> TargetRelationship:
    return TargetRelationship(
        target_id=target.id,
        account_id=acct.id,
        first_seen_at=NOW,
        last_seen_at=NOW,
        is_active=True,
    )


def seed(session: Session):
    shared = account("1", "shared")
    alpha_only = account("2", "alpha_only", age_days=10)
    beta_only = account("3", "beta_only")
    session.add_all([shared, alpha_only, beta_only])
    session.flush()

    alpha = Target(username="alpha", display_name="Alpha", first_tracked_at=NOW)
    beta = Target(username="beta", display_name="Beta", first_tracked_at=NOW)
    session.add_all([alpha, beta])
    session.flush()

    session.add_all([
        rel(alpha, shared),
        rel(alpha, alpha_only),
        rel(beta, shared),
        rel(beta, beta_only),
    ])
    session.add_all([
        AccountTopic(account_id=shared.id, topic="AI", source="bio_rule", evidence="AI", confidence=0.9, classifier_version="rule-v1", analyzed_at=NOW),
        AccountTopic(account_id=alpha_only.id, topic="Technology", source="bio_rule", evidence="tech", confidence=0.9, classifier_version="rule-v1", analyzed_at=NOW),
        AccountClassification(account_id=shared.id, account_type="Company", source="bio_rule", evidence="company", confidence=0.9, classifier_version="rule-v1", analyzed_at=NOW),
        AccountClassification(account_id=alpha_only.id, account_type="Individual", source="fallback", evidence="", confidence=0.7, classifier_version="rule-v1", analyzed_at=NOW),
        AccountClassification(account_id=beta_only.id, account_type="Media", source="bio_rule", evidence="media", confidence=0.9, classifier_version="rule-v1", analyzed_at=NOW),
    ])
    session.commit()
    return alpha, beta, shared, alpha_only, beta_only


def test_build_graph_returns_active_bipartite_network(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    with Session(engine) as session:
        alpha, beta, shared, *_ = seed(session)
        graph = build_graph(session, as_of=NOW)

    assert graph.meta.target_count == 2
    assert graph.meta.account_count == 3
    assert graph.meta.edge_count == 4
    nodes = {node.data["id"]: node.data for node in graph.nodes}
    assert f"target:{alpha.id}" in nodes
    assert f"target:{beta.id}" in nodes
    shared_data = nodes[f"account:{shared.id}"]
    assert shared_data["followed_by_targets"] == 2
    assert shared_data["target_coverage"] == 1.0
    assert shared_data["is_central"] is True
    assert len(graph.edges) == 4
    engine.dispose()


def test_target_filter_preserves_overlap_context_targets(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    with Session(engine) as session:
        alpha, beta, shared, alpha_only, _ = seed(session)
        graph = build_graph(session, target="alpha", as_of=NOW)

    ids = {node.data["id"] for node in graph.nodes}
    assert f"target:{alpha.id}" in ids
    assert f"target:{beta.id}" in ids
    assert f"account:{shared.id}" in ids
    assert f"account:{alpha_only.id}" in ids
    assert graph.meta.account_count == 2
    engine.dispose()


def test_semantic_new_and_coverage_filters(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    with Session(engine) as session:
        _, _, shared, alpha_only, _ = seed(session)
        topic_graph = build_graph(session, topic="AI", as_of=NOW)
        type_graph = build_graph(session, account_type="Individual", as_of=NOW)
        new_graph = build_graph(session, new_only=True, new_account_days=90, as_of=NOW)
        coverage_graph = build_graph(session, min_target_coverage=1.0, as_of=NOW)

    assert {n.data["id"] for n in topic_graph.nodes if n.data["kind"] == "account"} == {f"account:{shared.id}"}
    assert {n.data["id"] for n in type_graph.nodes if n.data["kind"] == "account"} == {f"account:{alpha_only.id}"}
    assert {n.data["id"] for n in new_graph.nodes if n.data["kind"] == "account"} == {f"account:{alpha_only.id}"}
    assert {n.data["id"] for n in coverage_graph.nodes if n.data["kind"] == "account"} == {f"account:{shared.id}"}
    engine.dispose()


def test_cap_is_deterministic_and_sets_truncated(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    with Session(engine) as session:
        _, _, shared, *_ = seed(session)
        graph = build_graph(session, max_accounts=1, as_of=NOW)

    accounts = [n.data for n in graph.nodes if n.data["kind"] == "account"]
    assert [item["username"] for item in accounts] == ["shared"]
    assert graph.meta.candidate_account_count == 3
    assert graph.meta.truncated is True
    engine.dispose()


def test_empty_graph_and_options(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    with Session(engine) as session:
        empty = build_graph(session, as_of=NOW)
        options = build_graph_options(session)
    assert empty.nodes == []
    assert empty.edges == []
    assert empty.meta.account_count == 0
    assert options.targets == []
    assert options.topics == []
    assert options.account_types == []
    engine.dispose()


def test_graph_validation_errors(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    with Session(engine) as session:
        seed(session)
        with pytest.raises(ValueError, match="target not found"):
            build_graph(session, target="missing", as_of=NOW)
        with pytest.raises(ValueError, match="topic not found"):
            build_graph(session, topic="MissingTopic", as_of=NOW)
        with pytest.raises(ValueError, match="account type not found"):
            build_graph(session, account_type="MissingType", as_of=NOW)
        with pytest.raises(ValueError, match="unsupported classifier_version"):
            build_graph(session, classifier_version="rule-v999", as_of=NOW)
        with pytest.raises(ValueError, match="max_accounts"):
            build_graph(session, max_accounts=0, as_of=NOW)
    engine.dispose()
