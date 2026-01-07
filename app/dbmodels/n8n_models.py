"""
N8N workflow and execution tracking models.

This module contains models for tracking n8n workflows and their execution history.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class N8NWorkflowStatus(str, Enum):
    """Status of n8n workflows"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class N8NExecutionStatus(str, Enum):
    """Status of n8n workflow executions"""

    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"
    CANCELLED = "cancelled"


class N8NWorkflow(Base):
    """
    Track n8n workflow details including dashboard and schedule associations.
    Links workflows to specific dashboards and schedules for management.
    """

    __tablename__ = "n8n_workflows"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # References to dashboard and schedule
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dashboards.dashboard_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schedules.schedule_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # N8N system identifiers
    n8n_workflow_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="ID of the workflow in n8n system",
    )
    n8n_tag_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Unique tag name used to identify this workflow in n8n",
    )

    # Workflow metadata
    workflow_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Display name of the workflow"
    )
    workflow_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="Complete n8n workflow JSON configuration"
    )

    # Status tracking
    status: Mapped[N8NWorkflowStatus] = mapped_column(
        nullable=False,
        default=N8NWorkflowStatus.INACTIVE,
        index=True,
        comment="Current status of the workflow",
    )
    last_activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time the workflow was activated",
    )
    last_deactivated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time the workflow was deactivated",
    )

    # Error tracking
    last_error: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Last error message if workflow failed"
    )
    error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Number of consecutive errors"
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
    dashboard: Mapped["Dashboard"] = relationship(
        "Dashboard", back_populates="n8n_workflows"
    )
    schedule: Mapped["Schedule"] = relationship(
        "Schedule", back_populates="n8n_workflows"
    )
    executions: Mapped[list["N8NWorkflowExecution"]] = relationship(
        "N8NWorkflowExecution", back_populates="workflow", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Ensure unique workflow per schedule
        UniqueConstraint(
            "dashboard_id", "schedule_id", name="uq_n8n_workflow_dashboard_schedule"
        ),
        # Index for status queries
        Index("idx_n8n_workflows_status", "status"),
        Index("idx_n8n_workflows_n8n_id", "n8n_workflow_id"),
        Index("idx_n8n_workflows_tag", "n8n_tag_name"),
        Index("idx_n8n_workflows_dashboard", "dashboard_id"),
        Index("idx_n8n_workflows_schedule", "schedule_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<N8NWorkflow(id={self.workflow_id}, dashboard={self.dashboard_id}, "
            f"schedule={self.schedule_id}, status={self.status.value})>"
        )


class N8NWorkflowExecution(Base):
    """
    Track execution history of n8n workflows for monitoring and debugging.
    Stores success/failure information and execution logs.
    """

    __tablename__ = "n8n_workflow_executions"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Reference to the workflow
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("n8n_workflows.workflow_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Execution details
    execution_status: Mapped[N8NExecutionStatus] = mapped_column(
        nullable=False, index=True, comment="Status of this execution run"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Execution duration in milliseconds"
    )

    # Execution results
    success_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Number of successful operations"
    )
    error_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Number of failed operations"
    )

    # Logs and error information
    execution_logs: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Complete execution logs from n8n"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Error message if execution failed"
    )
    stack_trace: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Full stack trace for debugging"
    )

    # N8N system identifiers
    n8n_execution_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="ID of the execution in n8n system",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    workflow: Mapped["N8NWorkflow"] = relationship(
        "N8NWorkflow", back_populates="executions"
    )

    __table_args__ = (
        # Index for querying by date ranges
        Index("idx_executions_started_at", "started_at"),
        Index("idx_executions_status", "execution_status"),
        Index("idx_executions_workflow_status", "workflow_id", "execution_status"),
        Index("idx_executions_n8n_id", "n8n_execution_id"),
        # Ensure duration makes sense
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_execution_duration_positive",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<N8NWorkflowExecution(id={self.execution_id}, "
            f"workflow={self.workflow_id}, status={self.execution_status.value})>"
        )
