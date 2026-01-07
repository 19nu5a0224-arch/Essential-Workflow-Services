"""
Activity Log model for tracking all entity actions in the system.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    DateTime,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EntityType(str, Enum):
    """Types of entities that can be logged."""

    DASHBOARD = "dashboard"
    DASHBOARD_VERSION = "dashboard_version"
    COMMENT = "comment"
    SHARE = "share"
    SCHEDULE = "schedule"
    INTEGRATION = "integration"


class ActionType(str, Enum):
    """Types of actions that can be performed."""

    # Dashboard actions
    DASHBOARD_CREATED = "dashboard_created"
    DASHBOARD_UPDATED = "dashboard_updated"
    DASHBOARD_DELETED = "dashboard_deleted"
    DASHBOARD_PUBLISHED = "dashboard_published"
    DASHBOARD_ARCHIVED = "dashboard_archived"

    # Comment actions
    COMMENT_CREATED = "comment_created"
    COMMENT_UPDATED = "comment_updated"
    COMMENT_DELETED = "comment_deleted"
    COMMENT_RESOLVED = "comment_resolved"

    # Share actions
    SHARE_CREATED = "share_created"
    SHARE_UPDATED = "share_updated"
    SHARE_REMOVED = "share_removed"

    # Schedule actions
    SCHEDULE_CREATED = "schedule_created"
    SCHEDULE_UPDATED = "schedule_updated"
    SCHEDULE_DELETED = "schedule_deleted"
    SCHEDULE_EXECUTED = "schedule_executed"

    # Integration actions
    INTEGRATION_ADDED = "integration_added"
    INTEGRATION_UPDATED = "integration_updated"
    INTEGRATION_REMOVED = "integration_removed"
    INTEGRATION_SYNCED = "integration_synced"


class ActivityLog(Base):
    """
    Activity log for tracking all entity actions.
    Provides audit trail and activity feed functionality.
    """

    __tablename__ = "activity_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Entity reference
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="ID of the entity this activity is about",
    )
    entity_type: Mapped[EntityType] = mapped_column(
        SQLEnum(EntityType, native_enum=True, name="activity_entity_type_enum"),
        nullable=False,
        index=True,
        comment="Type of entity (dashboard, comment, etc.)",
    )

    # User who performed the action
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="ID of user who performed the action",
    )
    username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Username at time of action (for historical record)",
    )

    # Action details
    action_type: Mapped[ActionType] = mapped_column(
        SQLEnum(ActionType, native_enum=True, name="activity_action_type_enum"),
        nullable=False,
        index=True,
        comment="Type of action performed",
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Human-readable description of the action"
    )

    # Flexible metadata storage
    activity_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Additional context data for the action",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index("idx_activity_entity", "entity_type", "entity_id"),
        Index("idx_activity_entity_created", "entity_type", "entity_id", "created_at"),
        Index("idx_activity_user", "user_id", "created_at"),
        Index("idx_activity_action", "action_type", "created_at"),
        Index("idx_activity_created", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ActivityLog({self.action_type.value} by {self.user_id} "
            f"on {self.entity_type.value}:{self.entity_id})>"
        )
