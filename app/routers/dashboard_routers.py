import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.schemas.dashboards_schema import (
    DashboardCreateSchema,
    DashboardUpdateContentSchema,
    DashboardUpdateDetailsSchema,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboards", tags=["dashboards"])

dashboard_service = DashboardService()


@router.post("/create_dashboard")
async def create_dashboard(
    dashboard_data: DashboardCreateSchema,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new dashboard
    """
    result = await dashboard_service.create_dashboard(
        user_info=current_user,
        dashboard_data=dashboard_data,
    )
    return result


@router.get("/get_all_dashboards")
async def get_all_dashboards(
    page: int = 1, page_size: int = 50, current_user: dict = Depends(get_current_user)
):
    """
    Get all dashboards for current user (my dashboards, shared dashboards, shared with me)

    Args:
        page: Page number for pagination (default: 1)
        page_size: Number of dashboards per page (default: 50)
    """
    print(f"Current User is {current_user}")
    result = await dashboard_service.get_all_dashboards(
        user_info=current_user, page=page, page_size=page_size
    )
    return result


@router.get("/getdashboardbyid/{dashboard_id}")
async def get_dashboard_by_id(
    dashboard_id: str,
    version_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Get specific dashboard by ID

    Args:
        version_id: Optional version ID to get specific version content
    """
    try:
        dashboard_uuid = uuid.UUID(dashboard_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

    version_uuid = None
    if version_id:
        try:
            version_uuid = uuid.UUID(version_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid version ID format")

    result = await dashboard_service.get_dashboard_by_id(
        user_info=current_user, dashboard_id=dashboard_uuid, version_id=version_uuid
    )
    return result


@router.delete("/{dashboard_id}")
async def delete_dashboard(
    dashboard_id: str,
    draft_version_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a dashboard
    """
    try:
        dashboard_uuid = uuid.UUID(dashboard_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

    draft_version_uuid = None
    if draft_version_id:
        try:
            draft_version_uuid = uuid.UUID(draft_version_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid draft version ID format"
            )

    result = await dashboard_service.delete_dashboard(
        user_info=current_user,
        dashboard_id=dashboard_uuid,
        draft_version_id=draft_version_uuid,
    )
    return result


@router.patch("/{dashboard_id}/update_details")
async def update_dashboard_details(
    dashboard_id: str,
    dashboard_data: DashboardUpdateDetailsSchema,
    current_user: dict = Depends(get_current_user),
):
    """
    Update dashboard details
    """
    try:
        dashboard_uuid = uuid.UUID(dashboard_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

    result = await dashboard_service.update_dashboard_details(
        user_info=current_user,
        dashboard_id=dashboard_uuid,
        update_data=dashboard_data,
    )
    return result


@router.patch("/{dashboard_id}/edit")
async def update_dashboard_content(
    dashboard_id: str,
    dashboard_data: DashboardUpdateContentSchema,
    current_user: dict = Depends(get_current_user),
):
    """
    Update dashboard content
    """
    try:
        dashboard_uuid = uuid.UUID(dashboard_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

    result = await dashboard_service.update_dashboard_content(
        user_info=current_user,
        dashboard_id=dashboard_uuid,
        content_data=dashboard_data,
    )
    return result


@router.post("/{dashboard_id}/publish")
async def publish_dashboard(
    dashboard_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Publish a dashboard
    """
    try:
        dashboard_uuid = uuid.UUID(dashboard_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

    result = await dashboard_service.publish_dashboard(
        user_info=current_user, dashboard_id=dashboard_uuid
    )
    return result
