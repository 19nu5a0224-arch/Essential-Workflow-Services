"""
Database models for widget locking and session tracking.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import VersionStatus


class UserSession(Base):
    """
    Tracks active user sessions for dashboard editing collaboration.
    """

    __tablename__ = "user_sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Session metadata
    client_info: Mapped[Optional[dict]] = mapped_column(  # browser, IP, etc.
        JSONB, nullable=True
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Track all widgets this user has locked
    locked_widgets: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=[]
    )

    __table_args__ = (
        Index("idx_user_sessions_dashboard_active", "dashboard_id", "is_active"),
        Index("idx_user_sessions_last_activity", "last_activity"),
        Index("idx_user_sessions_user_dashboard", "user_id", "dashboard_id"),
    )

    @property
    def duration(self) -> float:
        """Get session duration in seconds"""
        return (datetime.now() - self.connected_at).total_seconds()

    def __repr__(self) -> str:
        return f"<UserSession(session_id={self.session_id}, user={self.user_name}, dashboard={self.dashboard_id})>"


class WidgetLock(Base):
    """
    Manages widget-level locking for concurrent editing.
    """

    __tablename__ = "widget_locks"

    widget_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_sessions.session_id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Lock timing and expiration
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_widget_locks_dashboard_active", "dashboard_id", "is_active"),
        Index("idx_widget_locks_expires_at", "expires_at"),
        Index("idx_widget_locks_session", "session_id"),
        Index("idx_widget_locks_user", "user_id"),
        Index("idx_widget_locks_heartbeat", "last_heartbeat"),
    )

    @property
    def is_expired(self) -> bool:
        """Check if lock has expired"""
        # FIX: Added timezone.utc
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def time_remaining(self) -> float:
        """Get time remaining until lock expires in seconds"""
        # FIX: Added timezone.utc and max(0, ...) to prevent negative values
        diff = (self.expires_at - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, diff)

    def __repr__(self) -> str:
        # repr calls time_remaining; fixing time_remaining fixes repr
        return f"<WidgetLock(widget_id={self.widget_id}, user={self.user_name}, expires_in={self.time_remaining:.1f}s)>"

class CollaborationEvent(Base):
    """
    Audit trail for collaboration events (lock acquired, released, etc.)
    """

    __tablename__ = "collaboration_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    widget_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Event details
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # lock_acquired, lock_released, etc.
    event_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index("idx_collab_events_dashboard", "dashboard_id"),
        Index("idx_collab_events_user", "user_id"),
        Index("idx_collab_events_timestamp", "created_at"),
        Index("idx_collab_events_type", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<CollaborationEvent(event_type={self.event_type}, user={self.user_name}, widget={self.widget_id})>"
