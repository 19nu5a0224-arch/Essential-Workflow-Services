"""
Pydantic schemas for widget locking and session tracking APIs.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, validator


class WidgetLockAcquireSchema(BaseModel):
    """Schema for acquiring a widget lock."""

    widget_id: uuid.UUID = Field(..., description="Widget ID to lock")
    lock_duration: int = Field(
        default=60, ge=30, le=300, description="Lock duration in seconds (30-300)"
    )


class WidgetLockReleaseSchema(BaseModel):
    """Schema for releasing a widget lock."""

    widget_id: uuid.UUID = Field(..., description="Widget ID to release")


class WidgetLockHeartbeatSchema(BaseModel):
    """Schema for refreshing widget lock heartbeat."""

    widget_id: uuid.UUID = Field(..., description="Widget ID to refresh heartbeat")


class DashboardEditingSessionSchema(BaseModel):
    """Schema for dashboard editing session response."""

    session_id: uuid.UUID = Field(..., description="Session ID")
    dashboard_id: uuid.UUID = Field(..., description="Dashboard ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    user_name: str = Field(..., description="User display name")
    connected_at: datetime = Field(..., description="Session start time")
    message: str = Field(..., description="Status message")


class UserSessionSchema(BaseModel):
    """Schema for user session data."""

    session_id: uuid.UUID = Field(..., description="Session ID")
    dashboard_id: uuid.UUID = Field(..., description="Dashboard ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    user_name: str = Field(..., description="User display name")
    user_email: Optional[str] = Field(None, description="User email")
    client_info: Optional[Dict] = Field(None, description="Client metadata")
    connected_at: datetime = Field(..., description="Session start time")
    last_activity: datetime = Field(..., description="Last activity time")
    locked_widgets: List[uuid.UUID] = Field(
        default_factory=list, description="Widgets locked by this session"
    )


class WidgetLockSchema(BaseModel):
    """Schema for widget lock data."""

    widget_id: uuid.UUID = Field(..., description="Widget ID")
    dashboard_id: uuid.UUID = Field(..., description="Dashboard ID")
    session_id: uuid.UUID = Field(..., description="Session ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    user_name: str = Field(..., description="User display name")
    locked_at: datetime = Field(..., description="Lock acquisition time")
    expires_at: datetime = Field(..., description="Lock expiration time")
    last_heartbeat: datetime = Field(..., description="Last heartbeat time")
    time_remaining: float = Field(
        ..., description="Seconds remaining until lock expires"
    )


class ActiveSessionsResponse(BaseModel):
    """Response schema for active sessions API."""

    dashboard_id: uuid.UUID = Field(..., description="Dashboard ID")
    active_sessions: List[UserSessionSchema] = Field(
        default_factory=list, description="Active user sessions"
    )
    total_sessions: int = Field(..., description="Total active sessions")
    widget_locks: List[WidgetLockSchema] = Field(
        default_factory=list, description="Active widget locks"
    )


class WidgetLockStatusResponse(BaseModel):
    """Response schema for widget lock status."""

    widget_id: uuid.UUID = Field(..., description="Widget ID")
    is_locked: bool = Field(..., description="Whether widget is locked")
    locked_by: Optional[str] = Field(None, description="User who locked the widget")
    locked_by_user_id: Optional[uuid.UUID] = Field(
        None, description="User ID who locked the widget"
    )
    locked_at: Optional[datetime] = Field(
        None, description="When the widget was locked"
    )
    expires_at: Optional[datetime] = Field(None, description="When the lock expires")
    time_remaining: Optional[float] = Field(None, description="Seconds remaining")
    can_acquire: bool = Field(..., description="Whether current user can acquire lock")


class CollaborationEventSchema(BaseModel):
    """Schema for collaboration events."""

    event_id: uuid.UUID = Field(..., description="Event ID")
    dashboard_id: uuid.UUID = Field(..., description="Dashboard ID")
    widget_id: Optional[uuid.UUID] = Field(None, description="Widget ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    user_name: str = Field(..., description="User display name")
    event_type: str = Field(..., description="Event type")
    event_data: Optional[Dict] = Field(None, description="Event metadata")
    created_at: datetime = Field(..., description="Event timestamp")


class LockAcquisitionResponse(BaseModel):
    """Response schema for lock acquisition."""

    success: bool = Field(..., description="Whether lock was acquired")
    widget_id: uuid.UUID = Field(..., description="Widget ID")
    session_id: uuid.UUID = Field(..., description="Session ID")
    expires_at: datetime = Field(..., description="Lock expiration time")
    message: str = Field(..., description="Status message")


class HeartbeatResponse(BaseModel):
    """Response schema for heartbeat."""

    success: bool = Field(..., description="Whether heartbeat was successful")
    widget_id: uuid.UUID = Field(..., description="Widget ID")
    expires_at: datetime = Field(..., description="New expiration time")
    message: str = Field(..., description="Status message")


class CleanupResponse(BaseModel):
    """Response schema for cleanup operations."""

    cleaned_sessions: int = Field(..., description="Number of sessions cleaned up")
    cleaned_locks: int = Field(..., description="Number of locks cleaned up")
    message: str = Field(..., description="Cleanup result message")


@validator("lock_duration")
def validate_lock_duration(cls, v):
    """Validate lock duration is reasonable."""
    if v < 30:
        raise ValueError("Lock duration must be at least 30 seconds")
    if v > 300:
        raise ValueError("Lock duration cannot exceed 300 seconds")
    return v
