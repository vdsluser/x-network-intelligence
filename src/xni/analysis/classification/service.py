from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ...models import (
    Account,
    AccountAssociation,
    AccountClassification,
    AccountTopic,
    ClassificationRun,
    FollowingSnapshot,
    SnapshotMember,
)
from .associations import extract_associations
from .classifier import classify_account_type, classify_topics
from .taxonomy import CLASSIFIER_VERSIONS


class ClassificationRunRequest(BaseModel):
    classifier_version: str = "rule-v1"
    replace_version: bool = True


class ClassificationRunSummary(BaseModel):
    classifier_version: str
    accounts_processed: int
    accounts_with_topics: int
    accounts_unknown: int
    topics_created: int
    associations_created: int


class ClassificationEvidence(BaseModel):
    source: str
    evidence: str
    confidence: float
    classifier_version: str


class TopicDetail(ClassificationEvidence):
    topic: str


class AssociationDetail(ClassificationEvidence):
    association_type: str
    value: str
    normalized_value: str


class AccountClassificationDetail(BaseModel):
    account_id: int
    external_user_id: str
    username: str
    account_type: str
    account_type_source: str
    account_type_evidence: str
    account_type_confidence: float
    classifier_version: str
    topics: list[TopicDetail]
    associations: list[AssociationDetail]


class TopicAggregate(BaseModel):
    topic: str
    account_count: int
    coverage: float


class AssociationAggregate(BaseModel):
    association_type: str
    value: str
    normalized_value: str
    account_count: int
    evidence_count: int


def _latest_raw_by_account(session: Session) -> dict[int, dict[str, Any]]:
    rows = session.execute(
        select(SnapshotMember.account_id, SnapshotMember.raw_json)
        .join(FollowingSnapshot, FollowingSnapshot.id == SnapshotMember.snapshot_id)
        .order_by(FollowingSnapshot.collected_at.desc(), SnapshotMember.snapshot_id.desc())
    ).all()
    result: dict[int, dict[str, Any]] = {}
    for account_id, raw_json in rows:
        result.setdefault(account_id, raw_json or {})
    return result


def _validate_version(version: str) -> None:
    if version not in CLASSIFIER_VERSIONS:
        raise ValueError(f"unsupported classifier_version: {version}")


def run_classification(session: Session, request: ClassificationRunRequest) -> ClassificationRunSummary:
    _validate_version(request.classifier_version)
    version = request.classifier_version
    started_at = datetime.now(timezone.utc)
    accounts_with_topics = 0
    topics_created = 0
    associations_created = 0

    transaction = session.begin_nested() if session.in_transaction() else session.begin()
    with transaction:
        accounts = session.scalars(select(Account).order_by(Account.id)).all()
        latest_raw = _latest_raw_by_account(session)

        if request.replace_version:
            session.execute(delete(AccountTopic).where(AccountTopic.classifier_version == version))
            session.execute(delete(AccountClassification).where(AccountClassification.classifier_version == version))
            session.execute(delete(AccountAssociation).where(AccountAssociation.classifier_version == version))

        existing_topics = set(
            session.execute(
                select(AccountTopic.account_id, AccountTopic.topic).where(AccountTopic.classifier_version == version)
            ).all()
        )
        existing_types = set(
            session.scalars(
                select(AccountClassification.account_id).where(AccountClassification.classifier_version == version)
            ).all()
        )
        existing_associations = set(
            session.execute(
                select(
                    AccountAssociation.account_id,
                    AccountAssociation.association_type,
                    AccountAssociation.normalized_value,
                ).where(AccountAssociation.classifier_version == version)
            ).all()
        )

        analyzed_at = datetime.now(timezone.utc)
        for account in accounts:
            text = account.description or ""
            topic_matches = classify_topics(text)
            type_match = classify_account_type(text)
            association_matches = extract_associations(text, raw_json=latest_raw.get(account.id))

            if topic_matches:
                accounts_with_topics += 1

            if account.id not in existing_types:
                session.add(AccountClassification(
                    account_id=account.id,
                    account_type=type_match.account_type,
                    source=type_match.source,
                    evidence=type_match.evidence,
                    confidence=type_match.confidence,
                    classifier_version=version,
                    analyzed_at=analyzed_at,
                ))
                existing_types.add(account.id)

            for match in topic_matches:
                key = (account.id, match.topic)
                if key in existing_topics:
                    continue
                session.add(AccountTopic(
                    account_id=account.id,
                    topic=match.topic,
                    source=match.source,
                    evidence=match.evidence,
                    confidence=match.confidence,
                    classifier_version=version,
                    analyzed_at=analyzed_at,
                ))
                existing_topics.add(key)
                topics_created += 1

            for match in association_matches:
                key = (account.id, match.association_type, match.normalized_value)
                if key in existing_associations:
                    continue
                session.add(AccountAssociation(
                    account_id=account.id,
                    association_type=match.association_type,
                    value=match.value,
                    normalized_value=match.normalized_value,
                    source=match.source,
                    evidence=match.evidence,
                    confidence=match.confidence,
                    classifier_version=version,
                    analyzed_at=analyzed_at,
                ))
                existing_associations.add(key)
                associations_created += 1

        completed_at = datetime.now(timezone.utc)
        session.add(ClassificationRun(
            classifier_version=version,
            parameters_json=request.model_dump(),
            accounts_processed=len(accounts),
            accounts_with_topics=accounts_with_topics,
            accounts_unknown=len(accounts) - accounts_with_topics,
            topics_created=topics_created,
            associations_created=associations_created,
            started_at=started_at,
            completed_at=completed_at,
        ))

    return ClassificationRunSummary(
        classifier_version=version,
        accounts_processed=len(accounts),
        accounts_with_topics=accounts_with_topics,
        accounts_unknown=len(accounts) - accounts_with_topics,
        topics_created=topics_created,
        associations_created=associations_created,
    )


def get_account_classification_detail(
    session: Session,
    account_id: int,
    *,
    classifier_version: str = "rule-v1",
) -> AccountClassificationDetail:
    _validate_version(classifier_version)
    account = session.get(Account, account_id)
    if account is None:
        raise ValueError("account not found")

    primary = session.scalar(
        select(AccountClassification).where(
            AccountClassification.account_id == account_id,
            AccountClassification.classifier_version == classifier_version,
        )
    )
    topics = session.scalars(
        select(AccountTopic)
        .where(AccountTopic.account_id == account_id, AccountTopic.classifier_version == classifier_version)
        .order_by(AccountTopic.topic)
    ).all()
    associations = session.scalars(
        select(AccountAssociation)
        .where(AccountAssociation.account_id == account_id, AccountAssociation.classifier_version == classifier_version)
        .order_by(AccountAssociation.association_type, AccountAssociation.normalized_value)
    ).all()

    return AccountClassificationDetail(
        account_id=account.id,
        external_user_id=account.external_user_id,
        username=account.username,
        account_type=primary.account_type if primary else "Unknown",
        account_type_source=primary.source if primary else "unclassified",
        account_type_evidence=primary.evidence if primary else "",
        account_type_confidence=primary.confidence if primary else 0.0,
        classifier_version=classifier_version,
        topics=[
            TopicDetail(
                topic=row.topic,
                source=row.source,
                evidence=row.evidence,
                confidence=row.confidence,
                classifier_version=row.classifier_version,
            ) for row in topics
        ],
        associations=[
            AssociationDetail(
                association_type=row.association_type,
                value=row.value,
                normalized_value=row.normalized_value,
                source=row.source,
                evidence=row.evidence,
                confidence=row.confidence,
                classifier_version=row.classifier_version,
            ) for row in associations
        ],
    )


def list_topic_aggregates(session: Session, *, classifier_version: str = "rule-v1") -> list[TopicAggregate]:
    _validate_version(classifier_version)
    total_accounts = session.scalar(select(func.count()).select_from(Account)) or 0
    rows = session.execute(
        select(AccountTopic.topic, func.count(func.distinct(AccountTopic.account_id)))
        .where(AccountTopic.classifier_version == classifier_version)
        .group_by(AccountTopic.topic)
        .order_by(func.count(func.distinct(AccountTopic.account_id)).desc(), AccountTopic.topic)
    ).all()
    return [
        TopicAggregate(topic=topic, account_count=count, coverage=(count / total_accounts if total_accounts else 0.0))
        for topic, count in rows
    ]


def list_association_aggregates(
    session: Session,
    *,
    association_type: str | None = None,
    limit: int = 50,
    classifier_version: str = "rule-v1",
) -> list[AssociationAggregate]:
    from .taxonomy import ASSOCIATION_TYPES

    _validate_version(classifier_version)
    if association_type is not None and association_type not in ASSOCIATION_TYPES:
        raise ValueError(f"invalid association type: {association_type}")
    if limit < 1:
        raise ValueError("limit must be at least 1")

    stmt = select(
        AccountAssociation.association_type,
        AccountAssociation.normalized_value,
        func.min(AccountAssociation.value),
        func.count(func.distinct(AccountAssociation.account_id)),
        func.count(AccountAssociation.id),
    ).where(AccountAssociation.classifier_version == classifier_version)
    if association_type is not None:
        stmt = stmt.where(AccountAssociation.association_type == association_type)
    stmt = (
        stmt.group_by(AccountAssociation.association_type, AccountAssociation.normalized_value)
        .order_by(
            func.count(func.distinct(AccountAssociation.account_id)).desc(),
            AccountAssociation.association_type,
            AccountAssociation.normalized_value,
        )
        .limit(limit)
    )
    return [
        AssociationAggregate(
            association_type=row_type,
            value=value,
            normalized_value=normalized,
            account_count=account_count,
            evidence_count=evidence_count,
        )
        for row_type, normalized, value, account_count, evidence_count in session.execute(stmt).all()
    ]
