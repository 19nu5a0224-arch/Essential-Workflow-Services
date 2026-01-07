import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.core.database import db_manager
from app.dbmodels.n8n_models import N8NWorkflow
from app.schemas.features_schema import (
    IntegrationCreate,
    ScheduleCreate,
    ScheduleUpdate,
    ShareCreate,
)
from app.services.features_service import FeaturesService
from app.services.n8n_service import N8NService
from app.services.permission_service import PermissionService
from app.utils.cache import cached_n8n_workflows

router = APIRouter(prefix="/features", tags=["features"])

features_service = FeaturesService()
n8n_service = N8NService()


@router.get("/shares/{dashboard_id}")
async def get_shares_by_dashboard(
    dashboard_id: str, current_user: dict = Depends(get_current_user)
):
    """Get all shares for a specific dashboard."""
    try:
        dashboard_uuid = uuid.UUID(dashboard_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

    result = await features_service.get_shares_by_dashboard(
        user_info=current_user, dashboard_id=dashboard_uuid
    )
    return result


@router.post("/shares")
async def create_shares(
    share_data: ShareCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create shares for a dashboard."""
    result = await features_service.create_shares(
        user_info=current_user, share_data=share_data
    )
    return result


@router.patch("/shares/{share_id}")
async def update_share_permission(
    share_id: str,
    permission: str = Query(..., regex="^(read|write|admin)$"),
    current_user: dict = Depends(get_current_user),
):
    """Update share permission."""
    try:
        share_uuid = uuid.UUID(share_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid share ID format")

    result = await features_service.update_share_permission(
        user_info=current_user, share_id=share_uuid, new_permission=permission
    )
    return result


@router.delete("/shares/{share_id}")
async def delete_share(share_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a share."""
    try:
        share_uuid = uuid.UUID(share_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid share ID format")

    result = await features_service.delete_share(
        user_info=current_user, share_id=share_uuid
    )
    return result


@router.get("/schedules/{dashboard_id}")
async def get_schedules_by_dashboard(
    dashboard_id: str, current_user: dict = Depends(get_current_user)
):
    """Get all schedules for a specific dashboard."""
    try:
        dashboard_uuid = uuid.UUID(dashboard_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

    result = await features_service.get_schedules_by_dashboard(
        user_info=current_user, dashboard_id=dashboard_uuid
    )
    return result


@router.post("/schedules")
async def create_schedules(
    schedule_data: ScheduleCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create schedules for a dashboard."""
    result = await features_service.create_schedules(
        user_info=current_user, schedule_data=schedule_data
    )
    return result


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    schedule_data: ScheduleUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update schedule configuration and update associated N8N workflow.

    Updates the schedule in the database and sends a PUT request to N8N
    to update the workflow with the new schedule configuration.

    Args:
        schedule_id: UUID of the schedule to update
        schedule_data: Updated schedule configuration
        current_user: Authenticated user information

    Returns:
        Updated schedule information
    """
    try:
        schedule_uuid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid schedule ID format")

    result = await features_service.update_schedule_with_n8n(
        user_info=current_user, schedule_id=schedule_uuid, schedule_data=schedule_data
    )
    return result


@router.patch("/schedules/{schedule_id}/status")
async def update_schedule_status(
    schedule_id: str,
    is_active: bool = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """Update schedule status."""
    try:
        schedule_uuid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid schedule ID format")

    result = await features_service.update_schedule_status(
        user_info=current_user, schedule_id=schedule_uuid, is_active=is_active
    )
    return result


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str, current_user: dict = Depends(get_current_user)
):
    """Delete a schedule."""
    try:
        schedule_uuid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid schedule ID format")

    result = await features_service.delete_schedule(
        user_info=current_user, schedule_id=schedule_uuid
    )
    return result


@router.get("/integrations/{dashboard_id}")
async def get_integrations_by_dashboard(
    dashboard_id: str, current_user: dict = Depends(get_current_user)
):
    """Get all integrations for a specific dashboard."""
    try:
        dashboard_uuid = uuid.UUID(dashboard_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

    result = await features_service.get_integrations_by_dashboard(
        user_info=current_user, dashboard_id=dashboard_uuid
    )
    return result


@router.post("/integrations")
async def create_integrations(
    integration_data: IntegrationCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create integrations for a dashboard."""
    result = await features_service.create_integrations(
        user_info=current_user, integration_data=integration_data
    )
    return result


@router.patch("/integrations/{integration_id}")
async def update_integration_config(
    integration_id: str,
    config: dict,
    current_user: dict = Depends(get_current_user),
):
    """Update integration configuration."""
    try:
        integration_uuid = uuid.UUID(integration_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid integration ID format")

    result = await features_service.update_integration_config(
        user_info=current_user, integration_id=integration_uuid, config=config
    )
    return result


@router.delete("/integrations/{integration_id}")
async def delete_integration(
    integration_id: str, current_user: dict = Depends(get_current_user)
):
    """Delete an integration."""
    try:
        integration_uuid = uuid.UUID(integration_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid integration ID format")

    result = await features_service.delete_integration(
        user_info=current_user, integration_id=integration_uuid
    )
    return result


@router.get("/activity-logs/{dashboard_id}")
async def get_activity_logs_by_dashboard(
    dashboard_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    current_user: dict = Depends(get_current_user),
):
    """Get all activity logs for a specific dashboard with pagination."""
    try:
        dashboard_uuid = uuid.UUID(dashboard_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

    # Calculate offset
    offset = (page - 1) * page_size

    result = await features_service.get_activity_logs_by_dashboard(
        user_info=current_user,
        dashboard_id=dashboard_uuid,
        page=page,
        page_size=page_size,
    )
    return result


from fastapi import Request


@router.post("/features/schedules-debug")
async def debug_schedule(request: Request):
    body = await request.body()
    return {"raw_body": body.decode("utf-8", errors="replace")}
