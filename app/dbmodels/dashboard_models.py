import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
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

# Import Share for the relationship
from app.dbmodels.features_models import Integration, Schedule, Share
from app.dbmodels.n8n_models import N8NWorkflow


class VersionStatus(str, Enum):
    """Status of a dashboard version"""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"  # Previous published versions (for history)


class Dashboard(Base):
    """
    Dashboard with versioning support.
    Flow: Create (draft) → Publish → Edit (new draft) → Publish (old becomes archived)

    At any time:
    - ONE draft version (being edited)
    - ONE published version (live)
    - MULTIPLE archived versions (history)
    """

    __tablename__ = "dashboards"

    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ownership and organization
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Active version tracking
    current_published_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "dashboard_versions.id",
            use_alter=True,
            name="fk_dashboard_published_version",
        ),
        nullable=True,
    )
    current_draft_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "dashboard_versions.id", use_alter=True, name="fk_dashboard_draft_version"
        ),
        nullable=True,
    )

    # Track the next version number to use
    next_version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    dashboard_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional information about Dashboard",
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
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Relationships - CASCADE delete removes all versions when dashboard is deleted
    versions: Mapped[list["DashboardVersion"]] = relationship(
        "DashboardVersion",
        back_populates="dashboard",
        foreign_keys="DashboardVersion.dashboard_id",
        order_by="DashboardVersion.version_number.desc()",
        cascade="all, delete-orphan",
    )

    published_version: Mapped[Optional["DashboardVersion"]] = relationship(
        "DashboardVersion",
        foreign_keys=[current_published_version_id],
        uselist=False,
        post_update=True,
        viewonly=True,  # Don't modify through this relationship
    )

    # Sharing relationships
    shares: Mapped[list["Share"]] = relationship(
        "Share",
        back_populates="dashboard",
        foreign_keys="Share.dashboard_id",
        cascade="all, delete-orphan",
    )

    # Dashboard schedules
    schedules: Mapped[list["Schedule"]] = relationship(
        "Schedule",
        back_populates="dashboard",
        foreign_keys="Schedule.dashboard_id",
        cascade="all, delete-orphan",
    )

    # Dashboard integrations
    integrations: Mapped[list["Integration"]] = relationship(
        "Integration",
        back_populates="dashboard",
        foreign_keys="Integration.dashboard_id",
        cascade="all, delete-orphan",
    )

    # Dashboard n8n workflows
    n8n_workflows: Mapped[list["N8NWorkflow"]] = relationship(
        "N8NWorkflow",
        back_populates="dashboard",
        foreign_keys="N8NWorkflow.dashboard_id",
        cascade="all, delete-orphan",
    )

    draft_version: Mapped[Optional["DashboardVersion"]] = relationship(
        "DashboardVersion",
        foreign_keys=[current_draft_version_id],
        uselist=False,
        post_update=True,
        viewonly=True,  # Don't modify through this relationship
    )

    __table_args__ = (
        Index("idx_dashboards_owner_workspace", "owner_id", "workspace_id"),
        Index("idx_dashboards_project", "project_id"),
        Index("idx_dashboards_deleted_at", "deleted_at"),
        # Add missing indexes for performance optimization
        Index("idx_dashboards_owner_deleted", "owner_id", "deleted_at"),
        Index("idx_dashboards_deleted_owner", "deleted_at", "owner_id"),
    )

    @property
    def current_status(self) -> str:
        """Get current dashboard status based on published state"""
        if self.current_published_version_id:
            return "published"
        elif self.current_draft_version_id:
            return "draft"
        return "empty"

    @property
    def has_draft(self) -> bool:
        """Check if dashboard has a draft version"""
        return self.current_draft_version_id is not None

    @property
    def has_published(self) -> bool:
        """Check if dashboard has a published version"""
        return self.current_published_version_id is not None

    @property
    def is_deleted(self) -> bool:
        """Check if dashboard is soft-deleted"""
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return (
            f"<Dashboard(id={self.dashboard_id}, name='{self.name}', "
            f"status={self.current_status})>"
        )


class DashboardVersion(Base):
    """
    Immutable version snapshot of dashboard content.

    Lifecycle:
    1. DRAFT - Created when user starts editing, can be modified
    2. PUBLISHED - Draft is published, becomes live version (immutable)
    3. ARCHIVED - Previous published version, kept for history (immutable)

    Only ONE draft and ONE published per dashboard at a time.
    Multiple archived versions allowed for history.
    """

    __tablename__ = "dashboard_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dashboards.dashboard_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequential version number, stays same when draft is published",
    )
    status: Mapped[VersionStatus] = mapped_column(
        SQLEnum(
            VersionStatus,
            native_enum=True,
            name="version_status_enum",
            create_constraint=True,
        ),
        nullable=False,
        default=VersionStatus.DRAFT,
        index=True,
    )

    # Content stored as JSONB (can be large)
    content: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Dashboard configuration and widget data",
    )

    # Track lineage - which version this was based on
    based_on_version_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Version number this draft was created from (null for first version)",
    )

    # Audit fields
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="User who created this version",
    )
    last_edited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="User who last edited this version (for drafts)",
    )
    published_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="User who published this version"
    )
    archived_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User who triggered archival (by publishing new version)",
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
        comment="Last edit time (only changes for drafts)",
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this version was published",
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When this version was archived (for cleanup jobs)",
    )

    # Relationships
    dashboard: Mapped["Dashboard"] = relationship(
        "Dashboard", back_populates="versions", foreign_keys=[dashboard_id]
    )

    __table_args__ = (
        # Ensure unique version numbers per dashboard
        UniqueConstraint(
            "dashboard_id", "version_number", name="uq_dashboard_version_number"
        ),
        # Only ONE draft per dashboard at a time
        Index(
            "uq_dashboard_one_draft",
            "dashboard_id",
            "status",
            unique=True,
            postgresql_where=(Column("status") == "DRAFT"),
        ),
        # Only ONE published per dashboard at a time
        Index(
            "uq_dashboard_one_published",
            "dashboard_id",
            "status",
            unique=True,
            postgresql_where=(Column("status") == "PUBLISHED"),
        ),
        # Valid status values - handled by PostgreSQL ENUM type
        # Published versions must have published_at and published_by
        CheckConstraint(
            "(status = 'PUBLISHED' AND published_at IS NOT NULL AND published_by IS NOT NULL) OR "
            "(status != 'PUBLISHED')",
            name="ck_published_fields_required",
        ),
        # Archived versions must have archived_at
        CheckConstraint(
            "(status = 'ARCHIVED' AND archived_at IS NOT NULL) OR "
            "(status != 'ARCHIVED')",
            name="ck_archived_fields_required",
        ),
        # Indexes for common queries
        Index("idx_dashboard_versions_dashboard_status", "dashboard_id", "status"),
        Index("idx_dashboard_versions_created_at", "created_at"),
        Index("idx_dashboard_versions_archived_at", "archived_at"),  # For cleanup jobs
        Index("idx_dashboard_versions_content", "content", postgresql_using="gin"),
        # Add missing index for get_dashboard_by_id optimization
        Index("idx_dashboard_versions_dashboard", "dashboard_id"),
    )

    @property
    def is_draft(self) -> bool:
        """Check if this is a draft version"""
        return self.status == VersionStatus.DRAFT

    @property
    def is_published(self) -> bool:
        """Check if this is the published version"""
        return self.status == VersionStatus.PUBLISHED

    @property
    def is_archived(self) -> bool:
        """Check if this is an archived version"""
        return self.status == VersionStatus.ARCHIVED

    @property
    def is_editable(self) -> bool:
        """Only drafts can be edited"""
        return self.is_draft

    def can_be_published(self) -> bool:
        """Only drafts can be published"""
        return self.is_draft

    def can_be_deleted(self) -> bool:
        """Only archived versions can be manually deleted (for cleanup)"""
        return self.is_archived

    def __repr__(self) -> str:
        return (
            f"<DashboardVersion(id={self.id}, dashboard_id={self.dashboard_id}, "
            f"v{self.version_number}, status={self.status})>"
        )
