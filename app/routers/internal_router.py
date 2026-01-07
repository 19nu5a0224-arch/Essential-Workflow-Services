"""
Internal router APIs - hidden from Swagger documentation. This API's are used for n8n purpose only. Don't touch them...
These APIs don't require authorization and are for internal use only.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import db_manager
from app.dbmodels.activity_log import ActionType, ActivityLog, EntityType
from app.dbmodels.dashboard_models import Dashboard, DashboardVersion

logger = logging.getLogger(__name__)

# Create router with include_in_schema=False to hide from Swagger
router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)


@router.get("/dashboards/{dashboard_id}", status_code=200)
async def get_dashboard_by_id(
    dashboard_id: str,
    user_id: str = Query(..., description="User ID"),  # type: ignore
) -> Dict[str, Any]:
    """Get dashboard by ID with published version content.

    Internal API - no authorization required.
    """
    try:
        # Convert string IDs to UUID
        try:
            dashboard_uuid: UUID = UUID(dashboard_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid UUID format for dashboard_id or user_id",
            ) from exc

        async with db_manager.session() as session:
            print(f"Dashboard id came in session is {dashboard_uuid}")
            # Get dashboard
            stmt = select(Dashboard).where(Dashboard.dashboard_id == dashboard_uuid)
            result = await session.execute(stmt)
            dashboard: Optional[Dashboard] = result.scalar_one_or_none()

            if not dashboard:
                raise HTTPException(
                    status_code=404,
                    detail="Dashboard not found",
                )

            # Get published version
            if dashboard.current_published_version_id is None:
                raise HTTPException(
                    status_code=404,
                    detail="No published version found for this dashboard",
                )

            version_stmt = select(DashboardVersion).where(
                DashboardVersion.id == dashboard.current_published_version_id
            )
            version_result = await session.execute(version_stmt)
            version: Optional[DashboardVersion] = version_result.scalar_one_or_none()

            if not version:
                raise HTTPException(
                    status_code=404,
                    detail="Published version not found",
                )

            return {
                "dashboard_id": str(dashboard.dashboard_id),
                "published_id": str(version.id),
                "content": version.content,
            }

    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        logger.error(f"Database error in get_dashboard_by_id: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in get_dashboard_by_id")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from exc


@router.patch("/dashboards/{dashboard_id}/content", status_code=200)
async def update_dashboard_content(
    dashboard_id: str,
    user_id: str = Query(..., description="User ID"),  # type: ignore
    new_content: List[Dict[str, Any]] = Body(..., description="New dashboard content"),  # type: ignore
) -> Dict[str, Any]:
    """Update dashboard content and log the update.

    Uses PATCH for partial content updates.
    Internal API - no authorization required.
    """
    try:
        # Convert string IDs to UUID
        try:
            dashboard_uuid: UUID = UUID(dashboard_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid UUID format for dashboard_id or user_id",
            ) from exc

        async with db_manager.session() as session:
            # Get dashboard
            stmt = select(Dashboard).where(Dashboard.dashboard_id == dashboard_uuid)
            result = await session.execute(stmt)
            dashboard: Optional[Dashboard] = result.scalar_one_or_none()

            if not dashboard:
                raise HTTPException(
                    status_code=404,
                    detail="Dashboard not found",
                )

            # Get published version
            if dashboard.current_published_version_id is None:
                raise HTTPException(
                    status_code=404,
                    detail="No published version found for this dashboard",
                )

            version_stmt = select(DashboardVersion).where(
                DashboardVersion.id == dashboard.current_published_version_id
            )
            version_result = await session.execute(version_stmt)
            version: Optional[DashboardVersion] = version_result.scalar_one_or_none()

            if not version:
                raise HTTPException(
                    status_code=404,
                    detail="Published version not found",
                )

            # Update content - rename 'id' to 'widget_id' in each dictionary
            updated_content = []
            for widget in new_content:
                if "id" in widget:
                    widget["widget_id"] = widget.pop("id")
                updated_content.append(widget)
            version.content = updated_content

            # Create activity log entry
            timestamp: datetime = datetime.now()
            activity_log: ActivityLog = ActivityLog(
                entity_id=str(dashboard_uuid),  # type: ignore
                entity_type=EntityType.DASHBOARD,
                user_id=str(UUID(user_id)),  # type: ignore
                username="N8N",
                action_type=ActionType.DASHBOARD_UPDATED,
                description="dashboard ran successfully",
                activity_metadata={
                    "dashboard_id": str(dashboard_uuid),
                    "version_id": str(version.id),
                },
                created_at=timestamp,
            )
            session.add(activity_log)

            await session.commit()

            return {
                "message": "Dashboard content updated successfully",
                "dashboard_id": str(dashboard.dashboard_id),
                "published_id": str(version.id),
                "timestamp": timestamp.isoformat(),
            }

    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        logger.error(f"Database error in update_dashboard_content: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in update_dashboard_content")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from exc
