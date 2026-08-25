from datetime import datetime, timezone
from typing import Any
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Target(Base):
    __tablename__ = "targets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    external_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    first_tracked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    followers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    following_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tweets_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    protected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    profile_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class FollowingSnapshot(Base):
    __tablename__ = "following_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

class SnapshotMember(Base):
    __tablename__ = "snapshot_members"
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("following_snapshots.id"), primary_key=True, nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), primary_key=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

class TargetRelationship(Base):
    __tablename__ = "target_relationships"
    __table_args__ = (UniqueConstraint("target_id", "account_id", name="uq_target_account"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), index=True, nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class RelationshipEvent(Base):
    __tablename__ = "relationship_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), index=True, nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True, nullable=False)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("following_snapshots.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class ExpansionCandidate(Base):
    __tablename__ = "expansion_candidates"
    __table_args__ = (UniqueConstraint("account_id", name="uq_expansion_candidate_account"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), default="new_low_following", nullable=False)
    age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    following_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_account_days: Mapped[int] = mapped_column(Integer, nullable=False)
    low_following_max: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promoted_target_id: Mapped[int | None] = mapped_column(ForeignKey("targets.id"), nullable=True)


class AccountTopic(Base):
    __tablename__ = "account_topics"
    __table_args__ = (
        UniqueConstraint("account_id", "topic", "classifier_version", name="uq_account_topic_version"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    classifier_version: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class AccountClassification(Base):
    __tablename__ = "account_classifications"
    __table_args__ = (
        UniqueConstraint("account_id", "classifier_version", name="uq_account_classification_version"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True, nullable=False)
    account_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    classifier_version: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class AccountAssociation(Base):
    __tablename__ = "account_associations"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "association_type", "normalized_value", "classifier_version",
            name="uq_account_association_version",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True, nullable=False)
    association_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    classifier_version: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class ClassificationRun(Base):
    __tablename__ = "classification_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classifier_version: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    accounts_processed: Mapped[int] = mapped_column(Integer, nullable=False)
    accounts_with_topics: Mapped[int] = mapped_column(Integer, nullable=False)
    accounts_unknown: Mapped[int] = mapped_column(Integer, nullable=False)
    topics_created: Mapped[int] = mapped_column(Integer, nullable=False)
    associations_created: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
