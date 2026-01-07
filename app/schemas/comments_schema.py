import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class CommentType(str, Enum):
    """Enum for comment type."""

    CREATE = "create"  # Root comment
    REPLY = "reply"  # Reply to existing comment


class CommentAction(str, Enum):
    """Enum for comment operations."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LIKE = "like"
    UNLIKE = "unlike"


class CommentCreateRequest(BaseModel):
    """Schema for creating a comment."""

    content: str = Field(
        ..., min_length=1, max_length=5000, description="Comment content"
    )
    parent_comment_id: Optional[uuid.UUID] = Field(
        None, description="Parent comment ID for replies"
    )


class CommentUpdateRequest(BaseModel):
    """Schema for updating a comment."""

    content: str = Field(
        ..., min_length=1, max_length=5000, description="Updated comment content"
    )


class CommentResponse(BaseModel):
    """Schema for comment response."""

    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    content: str
    user_id: uuid.UUID
    parent_comment_id: Optional[uuid.UUID]
    like_count: int
    reply_count: int
    is_edited: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    is_pinned: bool = Field(default=False)
    created_at: datetime
    updated_at: datetime
    edited_at: Optional[datetime] = Field(default=None)

    # User display name
    username: str = Field(default="User")

    # Current user's interaction status
    has_liked: bool = Field(default=False)

    # Nested replies
    replies: List["CommentResponse"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CommentTreeResponse(BaseModel):
    """Schema for hierarchical comment tree response."""

    entity_type: str = Field(..., description="Entity type")
    entity_id: uuid.UUID = Field(..., description="Entity ID")
    comments: List[CommentResponse] = Field(
        ..., description="Root level comments with nested replies"
    )
    total_comments: int = Field(..., description="Total comments including replies")
    total_likes: int = Field(..., description="Total likes across all comments")
    has_more: bool = Field(..., description="Whether more comments are available")
    next_offset: Optional[int] = Field(
        default=None, description="Next pagination offset"
    )

    model_config = {"from_attributes": True}


class CommentOperationResponse(BaseModel):
    """Schema for comment operation responses."""

    success: bool
    action: CommentAction
    comment_id: uuid.UUID
    message: str
    data: Optional[CommentResponse] = Field(
        default=None, description="Updated comment data"
    )

    model_config = {"from_attributes": True}


# Update forward reference
CommentResponse.model_rebuild()
