"""
Feature-related Pydantic schemas for the Dashboard API.

Defines the request and response models for dashboard features including
sharing, scheduling, and integration functionality.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import (
    DayOfWeek,
    EntityType,
    FeatureRequestType,
    Frequency,
    IntegrationType,
    Permission,
    ScheduleType,
    TimePeriod,
)


class ShareBase(BaseModel):
    """Base schema for defining share permissions."""

    entity_type: EntityType = Field(
        ..., description="Type of entity being shared with (user, team, or group)"
    )
    entity_id: UUID = Field(
        ..., description="Unique identifier of the entity receiving access"
    )
    entity_name: Optional[str] = Field(
        None, description="Name of the entity being shared with"
    )
    permission: Permission = Field(
        ..., description="Permission level granted to the entity (read, write, admin)"
    )


class ShareCreate(BaseModel):
    """Schema for creating dashboard shares."""

    dashboard_id: UUID = Field(
        ..., description="Unique identifier of the dashboard being shared"
    )
    share_info: Union[List[ShareBase], ShareBase] = Field(
        ..., description="Single share definition or list of shares to create"
    )


class ScheduleBase(BaseModel):
    """Base schema for dashboard scheduling configuration."""

    schedule_type: ScheduleType = Field(
        ...,
        description="Type of schedule (one-time, recurring, etc.)",
        alias="scheduleType",
    )
    frequency: Frequency = Field(
        ...,
        description="How often the schedule should run (daily, weekly, biweekly, fortnightly, monthly, bimonthly, quarterly, semiannual, biannual, annual, yearly)",
    )
    start_date: datetime = Field(
        ..., description="When the schedule should start", alias="startDate"
    )
    end_date: datetime = Field(
        ..., description="When the schedule should end", alias="endDate"
    )
    hour: int = Field(
        ..., description="Hour of the day for schedule execution (0-23)", ge=0, le=23
    )
    minute: int = Field(
        ..., description="Minute of the hour for schedule execution (0-59)", ge=0, le=59
    )
    period: TimePeriod = Field(
        ..., description="Time period (AM/PM) for 12-hour format schedules"
    )

    days_of_week: Optional[List[DayOfWeek]] = Field(
        [], description="Days of the week for weekly schedules", alias="daysOfWeek"
    )
    time_zone: str = Field(
        ...,
        description="Timezone for schedule execution (e.g., 'UTC', 'America/New_York')",
        alias="timeZone",
    )


class ScheduleCreate(BaseModel):
    """Schema for creating dashboard schedules."""

    dashboard_id: UUID = Field(
        ..., description="Unique identifier of the dashboard being scheduled"
    )
    schedule_info: Union[List[ScheduleBase], ScheduleBase] = Field(
        ..., description="Single schedule definition or list of schedules to create"
    )


class IntegrationCreate(BaseModel):
    """Schema for creating dashboard integrations."""

    dashboard_id: UUID = Field(
        ..., description="Unique identifier of the dashboard being integrated"
    )
    integration_type: Union[List[IntegrationType], IntegrationType] = Field(
        ...,
        description="Type of integration to create (webhook, API, email, etc.)",
        alias="integrationType",
    )


class ScheduleUpdate(BaseModel):
    """Schema for updating dashboard schedules."""

    schedule_type: ScheduleType = Field(
        ...,
        description="Type of schedule (one-time, recurring, etc.)",
        alias="scheduleType",
    )
    frequency: Frequency = Field(
        ..., description="How often the schedule should run (daily, weekly, monthly)"
    )
    start_date: datetime = Field(
        ..., description="When the schedule should start", alias="startDate"
    )
    end_date: datetime = Field(
        ..., description="When the schedule should end", alias="endDate"
    )
    hour: int = Field(
        ..., description="Hour of the day for schedule execution (0-23)", ge=0, le=23
    )
    minute: int = Field(
        ..., description="Minute of the hour for schedule execution (0-59)", ge=0, le=59
    )
    period: TimePeriod = Field(
        ..., description="Time period (AM/PM) for 12-hour format schedules"
    )
    days_of_week: Optional[List[DayOfWeek]] = Field(
        [], description="Days of the week for weekly schedules", alias="daysOfWeek"
    )
    time_zone: str = Field(
        ...,
        description="Timezone for schedule execution (e.g., 'UTC', 'America/New_York')",
        alias="timeZone",
    )
