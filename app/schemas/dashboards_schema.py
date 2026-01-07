"""
Pydantic schemas for Dashboard API requests.
"""

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DashboardCreateSchema(BaseModel):
    """Schema for creating a new dashboard."""

    name: str = Field(
        ..., min_length=1, max_length=255, description="Name of the dashboard"
    )
    description: Optional[str] = Field(
        None, max_length=5000, description="Description of the dashboard"
    )
    project_id: Optional[uuid.UUID] = Field(
        None, description="Project ID to associate dashboard with"
    )
    workspace_id: Optional[uuid.UUID] = Field(
        None, description="Workspace ID to associate dashboard with"
    )
    content: List[Dict[str, Any]] = Field(
        default_factory=list, description="Dashboard widgets and layout configuration"
    )
    dashboard_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the dashboard"
    )

    @model_validator(mode="after")
    def validate_project_or_workspace(self):
        """Ensure at least one of project_id or workspace_id is provided."""
        if self.project_id is None and self.workspace_id is None:
            raise ValueError(
                "At least one of project_id or workspace_id must be provided"
            )
        return self

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate dashboard name."""
        v = v.strip()
        if not v:
            raise ValueError("Dashboard name cannot be empty or whitespace")
        return v

    @field_validator("content", mode="before")
    @classmethod
    def ensure_widget_ids(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure all widgets have widget_id, generating UUIDs if missing."""
        if not isinstance(v, list):
            raise ValueError("Content must be a list of widgets")

        for widget in v:
            if not isinstance(widget, dict):
                raise ValueError("All widgets must be dictionaries")
            if "widget_id" not in widget or not widget["widget_id"]:
                widget["widget_id"] = str(uuid.uuid4())

        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate content structure after widget_id generation."""
        if not isinstance(v, list):
            raise ValueError("Content must be a list of widgets")

        for idx, widget in enumerate(v):
            if not isinstance(widget, dict):
                raise ValueError(f"Widget at index {idx} must be a dictionary")
            # Ensure widget_id is present and valid
            if not widget.get("widget_id"):
                raise ValueError(f"Widget at index {idx} must have a valid widget_id")

        return v


class DashboardUpdateDetailsSchema(BaseModel):
    """Schema for updating dashboard metadata (name, description)."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="Name of the dashboard"
    )
    description: Optional[str] = Field(
        None, max_length=5000, description="Description of the dashboard"
    )
    dashboard_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata for the dashboard"
    )

    @model_validator(mode="after")
    def validate_at_least_one_field(self):
        """Ensure at least one field is being updated."""
        if (
            self.name is None
            and self.description is None
            and self.dashboard_metadata is None
        ):
            raise ValueError(
                "At least one field (name, description, or dashboard_metadata) must be provided"
            )
        return self

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate dashboard name if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Dashboard name cannot be empty or whitespace")
        return v


class DashboardUpdateContentSchema(BaseModel):
    """Schema for updating dashboard content (widgets)."""

    content: List[Dict[str, Any]] = Field(
        ..., description="Dashboard widgets and layout configuration"
    )

    @field_validator("content", mode="before")
    @classmethod
    def ensure_widget_ids(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure all widgets have widget_id, generating UUIDs if missing."""
        if not isinstance(v, list):
            raise ValueError("Content must be a list of widgets")

        for widget in v:
            if not isinstance(widget, dict):
                raise ValueError("All widgets must be dictionaries")
            if "widget_id" not in widget or not widget["widget_id"]:
                widget["widget_id"] = str(uuid.uuid4())

        return v
