"""
N8N workflow Pydantic schemas for the Dashboard API.

Defines the request and response models for N8N workflow functionality.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.dbmodels.n8n_models import N8NExecutionStatus, N8NWorkflowStatus


class N8NWorkflowBase(BaseModel):
    """Base schema for N8N workflow details."""

    dashboard_id: UUID = Field(
        ..., description="Dashboard ID associated with the workflow"
    )
    schedule_id: UUID = Field(
        ..., description="Schedule ID associated with the workflow"
    )
    n8n_workflow_id: str = Field(..., description="ID of the workflow in n8n system")
    n8n_tag_name: str = Field(
        ..., description="Unique tag name used to identify this workflow in n8n"
    )
    workflow_name: str = Field(..., description="Display name of the workflow")
    workflow_data: Dict[str, Any] = Field(
        ..., description="Complete n8n workflow JSON configuration"
    )
    status: N8NWorkflowStatus = Field(..., description="Current status of the workflow")


class N8NWorkflowResponse(N8NWorkflowBase):
    """Schema for N8N workflow response with additional fields."""

    workflow_id: UUID = Field(..., description="Internal workflow ID")
    last_activated_at: Optional[datetime] = Field(
        None, description="Last time the workflow was activated"
    )
    last_deactivated_at: Optional[datetime] = Field(
        None, description="Last time the workflow was deactivated"
    )
    last_error: Optional[str] = Field(
        None, description="Last error message if workflow failed"
    )
    error_count: int = Field(..., description="Number of consecutive errors")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class N8NWorkflowExecutionResponse(BaseModel):
    """Schema for N8N workflow execution response."""

    execution_id: UUID = Field(..., description="Internal execution ID")
    workflow_id: UUID = Field(
        ..., description="Workflow ID associated with the execution"
    )
    execution_status: N8NExecutionStatus = Field(
        ..., description="Status of this execution run"
    )
    started_at: datetime = Field(..., description="Execution start time")
    completed_at: Optional[datetime] = Field(
        None, description="Execution completion time"
    )
    duration_ms: Optional[int] = Field(
        None, description="Execution duration in milliseconds"
    )
    success_count: Optional[int] = Field(
        None, description="Number of successful operations"
    )
    error_count: Optional[int] = Field(None, description="Number of failed operations")
    error_message: Optional[str] = Field(
        None, description="Error message if execution failed"
    )
    n8n_execution_id: Optional[str] = Field(
        None, description="ID of the execution in n8n system"
    )
    created_at: datetime = Field(..., description="Creation timestamp")


class N8NWorkflowWithExecutionsResponse(N8NWorkflowResponse):
    """Schema for N8N workflow response including executions."""

    executions: List[N8NWorkflowExecutionResponse] = Field(
        default=[], description="List of workflow executions"
    )


class N8NWorkflowsResponse(BaseModel):
    """Schema for paginated N8N workflows response."""

    workflows: List[N8NWorkflowResponse] = Field(
        ..., description="List of N8N workflows"
    )
    total_count: int = Field(..., description="Total number of workflows")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of workflows per page")


class N8NWorkflowsWithExecutionsResponse(BaseModel):
    """Schema for paginated N8N workflows response with executions."""

    workflows: List[N8NWorkflowWithExecutionsResponse] = Field(
        ..., description="List of N8N workflows with executions"
    )
    total_count: int = Field(..., description="Total number of workflows")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of workflows per page")
