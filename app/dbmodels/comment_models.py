import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base

if TYPE_CHECKING:
    from models.dashboard_models import Dashboard
    # Future imports for workflow and report models


class Comment(Base):
    __tablename__ = "comments"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Entity reference (dashboard, workflow, report)
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    entity_type = Column(
        String(20),
        nullable=False,
    )

    # Comment content
    content = Column(Text, nullable=False)

    # User who created the comment
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Reply functionality - parent comment reference
    parent_comment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Comment metrics
    like_count = Column(Integer, nullable=False, default=0)
    reply_count = Column(Integer, nullable=False, default=0, index=True)

    # Moderation and status
    is_edited = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    is_pinned = Column(Boolean, nullable=False, default=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )
    edited_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    parent_comment = relationship(
        "Comment", remote_side=[id], backref="replies", foreign_keys=[parent_comment_id]
    )

    # Entity relationships (for future expansion)
    # These will be lazy-loaded and optional
    dashboard = relationship(
        "Dashboard",
        primaryjoin="and_(Comment.entity_type == 'dashboard', foreign(Comment.entity_id) == Dashboard.dashboard_id)",
        viewonly=True,
    )

    __table_args__ = (
        # Entity type validation
        CheckConstraint(
            "entity_type IN ('dashboard', 'workflow', 'report')",
            name="ck_comment_entity_type",
        ),
        # Composite indexes for optimal querying
        Index("ix_comments_entity_type_id", "entity_type", "entity_id"),
        Index("ix_comments_entity_created", "entity_type", "entity_id", "created_at"),
        Index(
            "ix_comments_entity_pinned",
            "entity_type",
            "entity_id",
            "is_pinned",
            "created_at",
        ),
        Index("ix_comments_user_created", "user_id", "created_at"),
        Index("ix_comments_parent_created", "parent_comment_id", "created_at"),
        Index("ix_comments_like_count", "entity_type", "entity_id", "like_count"),
    )

    def __repr__(self):
        return f"<Comment {self.id} on {self.entity_type} {self.entity_id}>"

    @property
    def is_root_comment(self) -> bool:
        """Check if this is a root comment (not a reply)."""
        return self.parent_comment_id is None

    @property
    def is_reply(self) -> bool:
        """Check if this is a reply to another comment."""
        return self.parent_comment_id is not None

    def to_dict(self) -> dict:
        """Convert comment to dictionary for API response."""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "content": self.content,
            "user_id": self.user_id,
            "parent_comment_id": self.parent_comment_id,
            "like_count": self.like_count,
            "reply_count": self.reply_count,
            "is_edited": self.is_edited,
            "is_deleted": self.is_deleted,
            "is_pinned": self.is_pinned,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
        }

    def can_edit(self, user_id: uuid.UUID) -> bool:
        """Check if user can edit this comment."""
        return self.user_id == user_id and not self.is_deleted

    def can_delete(self, user_id: uuid.UUID) -> bool:
        """Check if user can delete this comment."""
        return self.user_id == user_id and not self.is_deleted

    def mark_as_edited(self) -> None:
        """Mark comment as edited and update timestamp."""
        self.is_edited = True
        self.edited_at = datetime.now()


class CommentLike(Base):
    __tablename__ = "comment_likes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    comment = relationship("Comment", backref="likes")

    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_comment_like_user"),
        Index("ix_comment_likes_comment_user", "comment_id", "user_id"),
    )

    def __repr__(self):
        return f"<CommentLike {self.user_id} -> {self.comment_id}>"
