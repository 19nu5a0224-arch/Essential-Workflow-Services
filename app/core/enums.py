"""
Centralized enum definitions for the Dashboard API.

This file contains all enums used throughout the application to avoid circular dependencies
and ensure consistent enum definitions across different modules.
"""

from enum import Enum


class EntityType(str, Enum):
    """Entity types that can be shared with."""

    USER = "user"
    TEAM = "team"
    PROJECT = "project"
    WORKSPACE = "workspace"


class Permission(str, Enum):
    """Permission levels for shared resources."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class ScheduleType(str, Enum):
    """Schedule execution types."""

    ONE_TIME = "one_time"
    SCHEDULED = "scheduled"


class Frequency(str, Enum):
    """Schedule frequency options."""

    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"
    BIMONTHLY = "bimonthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    BIANNUAL = "biannual"
    ANNUAL = "annual"
    YEARLY = "yearly"


class DayOfWeek(str, Enum):
    """Days of the week for scheduling."""

    MON = "Mon"
    TUE = "Tue"
    WED = "Wed"
    THU = "Thu"
    FRI = "Fri"
    SAT = "Sat"
    SUN = "Sun"


class TimePeriod(str, Enum):
    """Time period (AM/PM)."""

    AM = "AM"
    PM = "PM"


class IntegrationType(str, Enum):
    """Supported integration types."""

    POWERBI = "powerbi"
    TABLEAU = "tableau"


class FeatureRequestType(str, Enum):
    """Type of feature request for dashboard operations."""

    SHARE = "share"
    SCHEDULE = "schedule"
    INTEGRATION = "integration"


class VersionStatus(str, Enum):
    """Status of dashboard versions."""

    DRAFT = "draft"
    PUBLISHED = "published"
