"""
Feature models for Dashboard: Share, Schedule, and Integration
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import (
    EntityType,
    Frequency,
    IntegrationType,
    Permission,
    ScheduleType,
    TimePeriod,
)
from app.dbmodels.n8n_models import N8NWorkflow


class Share(Base):
    """
    Dashboard sharing with users, teams, projects, or workspaces.
    Supports different permission levels (read, write, admin).
    """

    __tablename__ = "shares"

    share_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dashboards.dashboard_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Who shared this dashboard
    shared_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="User who created this share",
    )

    # What entity is this shared with
    entity_type: Mapped[EntityType] = mapped_column(
        SQLEnum(EntityType, native_enum=True, name="entity_type_enum"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="ID of user/team/project/workspace",
    )
    entity_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Name of the entity being shared with",
    )

    # Permission level
    permission: Mapped[Permission] = mapped_column(
        SQLEnum(Permission, native_enum=True, name="permission_enum"),
        nullable=False,
        default=Permission.READ,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    dashboard = relationship(
        "Dashboard", back_populates="shares", foreign_keys=[dashboard_id]
    )

    __table_args__ = (
        # Prevent duplicate shares for same entity
        UniqueConstraint(
            "dashboard_id", "entity_type", "entity_id", name="uq_share_dashboard_entity"
        ),
        Index("idx_shares_entity", "entity_type", "entity_id"),
        Index("idx_shares_dashboard_permission", "dashboard_id", "permission"),
        # Add missing index for get_all_dashboards optimization
        Index(
            "idx_shares_dashboard_entity", "dashboard_id", "entity_type", "entity_id"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Share(id={self.share_id}, dashboard={self.dashboard_id}, "
            f"entity={self.entity_type.value}:{self.entity_id}, permission={self.permission.value})>"
        )


class Schedule(Base):
    """
    Dashboard execution schedules with cron-like functionality.
    Supports one-time and recurring schedules (daily, weekly, monthly).
    """

    __tablename__ = "schedules"

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dashboards.dashboard_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Username of the user who created the schedule",
    )

    # Who created this schedule
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Schedule configuration
    schedule_type: Mapped[ScheduleType] = mapped_column(
        SQLEnum(ScheduleType, native_enum=True, name="schedule_type_enum"),
        nullable=False,
        default=ScheduleType.SCHEDULED,
    )
    frequency: Mapped[Optional[Frequency]] = mapped_column(
        SQLEnum(Frequency, native_enum=True, name="frequency_enum"),
        nullable=True,
        comment="Required for scheduled type",
    )

    # Time configuration
    hour: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Hour in 12-hour format (1-12)"
    )
    minute: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Minute (0-59)"
    )
    period: Mapped[TimePeriod] = mapped_column(
        SQLEnum(TimePeriod, native_enum=True, name="time_period_enum"),
        nullable=False,
        comment="AM or PM",
    )

    # Date range
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Optional end date for recurring schedules",
    )

    # Weekly schedule - stored as JSONB array
    days_of_week: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Array of days ['Mon', 'Tue', ...] for weekly schedules",
    )

    # Monthly schedule
    day_of_month: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Day of month (1-31) for monthly schedules"
    )

    # Timezone
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UTC",
        comment="Timezone for schedule execution",
    )

    # Status tracking
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        index=True,
        comment="Whether schedule is currently active",
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time this schedule executed",
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Next scheduled execution time",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    dashboard = relationship(
        "Dashboard", back_populates="schedules", foreign_keys=[dashboard_id]
    )
    n8n_workflows: Mapped[list["N8NWorkflow"]] = relationship(
        "N8NWorkflow",
        back_populates="schedule",
        foreign_keys="N8NWorkflow.schedule_id",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Validate hour range
        CheckConstraint("hour >= 1 AND hour <= 12", name="ck_schedule_hour_range"),
        # Validate minute range
        CheckConstraint(
            "minute >= 0 AND minute <= 59", name="ck_schedule_minute_range"
        ),
        # Validate day_of_month range
        CheckConstraint(
            "day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31)",
            name="ck_schedule_day_of_month_range",
        ),
        # Weekly schedules must have days_of_week
        CheckConstraint(
            "(frequency != 'WEEKLY' OR days_of_week IS NOT NULL)",
            name="ck_schedule_weekly_needs_days",
        ),
        # Monthly schedules must have day_of_month
        CheckConstraint(
            "(frequency != 'MONTHLY' OR day_of_month IS NOT NULL)",
            name="ck_schedule_monthly_needs_day",
        ),
        # Scheduled type must have frequency
        CheckConstraint(
            "(schedule_type != 'SCHEDULED' OR frequency IS NOT NULL)",
            name="ck_schedule_type_needs_frequency",
        ),
        Index("idx_schedules_next_run", "next_run_at", "is_active"),
        Index("idx_schedules_frequency", "frequency", "is_active"),
        Index("idx_schedules_dashboard_active", "dashboard_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<Schedule(id={self.schedule_id}, dashboard={self.dashboard_id}, "
            f"type={self.schedule_type.value}, frequency={self.frequency}, "
            f"next_run={self.next_run_at})>"
        )


class Integration(Base):
    """
    Dashboard integrations with external BI tools (PowerBI, Tableau, etc.).
    Stores connection details and sync status.
    """

    __tablename__ = "integrations"

    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dashboards.dashboard_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Username of the user who created the integration",
    )

    # Integration details
    name: Mapped[IntegrationType] = mapped_column(
        SQLEnum(IntegrationType, native_enum=True, name="integration_type_enum"),
        nullable=False,
        comment="Type of integration (powerbi, tableau, etc.)",
    )

    # Connection configuration (encrypted in production)
    config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Integration-specific configuration (API keys, URLs, etc.)",
    )

    # Who added this integration
    added_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Status tracking
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        index=True,
        comment="Whether integration is currently active",
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Last successful sync time"
    )
    last_sync_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Status of last sync (success, failed, etc.)"
    )
    last_sync_error: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Error message if last sync failed"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    dashboard = relationship(
        "Dashboard", back_populates="integrations", foreign_keys=[dashboard_id]
    )

    __table_args__ = (
        Index("idx_integrations_name", "name"),
        Index("idx_integrations_dashboard_active", "dashboard_id", "is_active"),
        Index("idx_integrations_dashboard_name", "dashboard_id", "name"),
        Index("idx_integrations_last_sync", "last_sync_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Integration(id={self.integration_id}, dashboard={self.dashboard_id}, "
            f"name={self.name.value}, active={self.is_active})>"
        )
