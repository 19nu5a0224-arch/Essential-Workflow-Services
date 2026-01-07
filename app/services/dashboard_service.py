"""
Dashboard Service Layer

Handles dashboard operations with permission checks and proper error handling.
Follows the flow: API -> Service Layer -> Permission Layer -> Codebase -> Database
"""

import traceback
import uuid
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select

from app.codebase.dashboards import (
    CoreDashboard,
    DashboardDeletedError,
    DashboardNotFoundError,
    InvalidOperationError,
    VersionNotFoundError,
)
from app.core.database import db_manager
from app.core.logging import logger
from app.dbmodels.activity_log import ActionType, ActivityLog, EntityType
from app.dbmodels.dashboard_models import Dashboard, DashboardVersion
from app.schemas.dashboards_schema import (
    DashboardCreateSchema,
    DashboardUpdateContentSchema,
    DashboardUpdateDetailsSchema,
)
from app.services.permission_service import PermissionService
from app.services.widget_locking_service import WidgetLockingService
from app.utils.cache import cached_dashboard, get_cache


class DashboardService:
    """Service for handling dashboard operations with permission checks."""

    @staticmethod
    async def create_dashboard(
        user_info: Any,
        dashboard_data: DashboardCreateSchema,
    ) -> Any:
        """
        Create a new dashboard.

        Args:
            user_info: User information object
            dashboard_data: Dashboard creation data

        Returns:
            Result from CoreDashboard.create_dashboard()
        """
        # Check user permission first - outside try block to avoid catching HTTPException
        has_permission = await PermissionService.check_create_dashboard(
            user_info=user_info,
            project_id=str(dashboard_data.project_id)
            if dashboard_data.project_id
            else None,
            workspace_id=str(dashboard_data.workspace_id)
            if dashboard_data.workspace_id
            else None,
        )

        if not has_permission:
            # Create contextual error message based on what was provided
            if dashboard_data.project_id and dashboard_data.workspace_id:
                detail = "You don't have permission to create dashboard in this project or workspace"
            elif dashboard_data.project_id:
                detail = "You don't have permission to create dashboard in this project"
            elif dashboard_data.workspace_id:
                detail = (
                    "You don't have permission to create dashboard in this workspace"
                )
            else:
                detail = "You don't have permission to create dashboard"  # Should not happen due to schema validation

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )

        try:
            async with db_manager.session() as session:
                result = await CoreDashboard.create_dashboard(
                    session=session,
                    dashboard_data=dashboard_data,
                    user_id=user_info["id"],
                )
                activity_log = ActivityLog(
                    entity_type=EntityType.DASHBOARD,
                    entity_id=result.dashboard_id,
                    user_id=result.owner_id,
                    username=user_info["username"],
                    action_type=ActionType.DASHBOARD_CREATED,
                    description=f"Created dashboard {dashboard_data.name}",
                    activity_metadata={
                        "dashboard_id": str(result.dashboard_id),
                        "dashboard_name": dashboard_data.name,
                    },
                )
                session.add(activity_log)
                await session.commit()
                await session.refresh(result)

                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"collection:dashboard:user:{user_info['id']}",
                    f"resource:dashboard",
                )

                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in create_dashboard " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in create_dashboard " + "=" * 50)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @staticmethod
    @cached_dashboard(ttl=60)  # Cache dashboards for 60 seconds
    async def get_all_dashboards(
        user_info: Any, page: int = 1, page_size: int = 50
    ) -> Any:
        """
        Get all dashboards for current user (my dashboards, shared dashboards, shared with me).

        Args:
            user_info: User information object
            page: Page number for pagination (1-indexed)
            page_size: Number of dashboards per page

        Returns:
            Result from codebase/dashboards.py get_all_dashboards()
        """
        try:
            async with db_manager.session() as session:
                result = await CoreDashboard.get_all_dashboards(
                    session=session, user_info=user_info, page=page, page_size=page_size
                )
                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in get_all_dashboards " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in get_all_dashboards " + "=" * 50)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @staticmethod
    @cached_dashboard(ttl=60)  # Cache dashboard for 60 seconds
    async def get_dashboard_by_id(
        user_info: Any, dashboard_id: uuid.UUID, version_id: Optional[uuid.UUID] = None
    ) -> Any:
        """
        Get dashboard details by ID.

        Args:
            user_info: User information object
            dashboard_id: Dashboard ID
            version_id: Optional version ID to get specific version content

        Returns:
            Result from CoreDashboard.get_dashboard_by_id()
        """
        # Check if user has permission for this dashboard - outside try block to avoid catching HTTPException
        # If version_id is provided, require write permission, otherwise read permission
        required_permission = "write" if version_id else "read"
        has_permission = await PermissionService.check_user_permission(
            user_info=user_info,
            dashboard_id=dashboard_id,
            user_id=user_info["id"],
            required_permission=required_permission,
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have {required_permission} permission to access this dashboard",
            )

        try:
            async with db_manager.session() as session:
                result = await CoreDashboard.get_dashboard_by_id(
                    session=session, dashboard_id=dashboard_id, version_id=version_id
                )
                return result

        except (DashboardNotFoundError, DashboardDeletedError) as e:
            logger.warning(f"Dashboard access denied: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        except Exception as e:
            logger.error("=" * 50 + " Error in get_dashboard_by_id " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in get_dashboard_by_id " + "=" * 50)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @staticmethod
    async def publish_dashboard(user_info: Any, dashboard_id: uuid.UUID) -> Any:
        """
        Publish dashboard from draft to publish.

        Args:
            user_info: User information object
            dashboard_id: Dashboard ID

        Returns:
            Result from CoreDashboard.publish_dashboard()
        """
        # Check user permission first - outside try block to avoid catching HTTPException
        has_permission = await PermissionService.check_user_permission(
            user_info=user_info,
            dashboard_id=dashboard_id,
            user_id=user_info["id"],
            required_permission="admin",
        )

        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to publish this dashboard",
            )

        try:
            async with db_manager.session() as session:
                # Get dashboard first
                dashboard = await session.get(Dashboard, dashboard_id)
                if not dashboard:
                    raise DashboardNotFoundError(f"Dashboard {dashboard_id} not found")

                # Get current draft version
                draft_version = await session.get(
                    DashboardVersion, dashboard.current_draft_version_id
                )
                if not draft_version:
                    raise VersionNotFoundError(
                        f"Draft version for dashboard {dashboard_id} not found"
                    )

                result = await CoreDashboard.publish_dashboard(
                    session=session,
                    dashboard=dashboard,
                    draft_version=draft_version,
                    user_id=user_info["id"],
                )
                activity_log = ActivityLog(
                    entity_type=EntityType.DASHBOARD,
                    entity_id=dashboard_id,
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.DASHBOARD_PUBLISHED,
                    description=f"Published version {draft_version.version_number}",
                    activity_metadata={
                        "dashboard_id": str(dashboard.dashboard_id),
                        "version_id": str(draft_version.id),
                        "version_number": draft_version.version_number,
                    },
                )
                session.add(activity_log)
                await session.commit()
                await session.refresh(result)

                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"entity:dashboard:{result.dashboard_id}",
                    f"detail:dashboard:{result.dashboard_id}",
                    f"collection:dashboard:user:{user_info['id']}",
                    f"resource:dashboard",
                )

                return result

        except (
            DashboardNotFoundError,
            InvalidOperationError,
            VersionNotFoundError,
        ) as e:
            logger.warning(f"Dashboard publish failed: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=str(e),
            )
        except Exception as e:
            logger.error("=" * 50 + " Error in publish_dashboard " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in publish_dashboard " + "=" * 50)
            raise HTTPException(
                status_code=500,
                detail="Internal server error",
            )

    @staticmethod
    async def delete_dashboard(
        user_info: Any,
        dashboard_id: uuid.UUID,
        draft_version_id: Optional[uuid.UUID] = None,
    ) -> Any:
        """
        Delete a dashboard or specific draft version.

        Args:
            user_info: User information object
            dashboard_id: Dashboard ID
            draft_version_id: Optional draft version ID to delete specific version

        Returns:
            Result from CoreDashboard.delete_dashboard_or_draft()
        """
        # Determine required permission level
        required_permission = "admin" if not draft_version_id else "write"

        # Check user permission first - outside try block to avoid catching HTTPException
        has_permission = await PermissionService.check_user_permission(
            user_info=user_info,
            dashboard_id=dashboard_id,
            user_id=user_info["id"],
            required_permission=required_permission,
        )

        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail=f"You don't have permission to delete this {'dashboard' if not draft_version_id else 'draft version'}",
            )

        try:
            async with db_manager.session() as session:
                # Get dashboard first
                dashboard = await session.get(Dashboard, dashboard_id)
                if not dashboard:
                    raise DashboardNotFoundError(f"Dashboard {dashboard_id} not found")

                result = await CoreDashboard.delete_dashboard_or_draft(
                    session=session,
                    dashboard=dashboard,
                    draft_version_id=draft_version_id,
                )

                # Create activity log
                activity_log = ActivityLog(
                    entity_type=EntityType.DASHBOARD,
                    entity_id=dashboard_id,
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.DASHBOARD_DELETED,
                    description=f"Deleted {'draft version' if draft_version_id else 'dashboard'}",
                    activity_metadata={
                        "dashboard_id": str(dashboard_id),
                    },
                )
                session.add(activity_log)
                await session.commit()
                await session.refresh(result)

                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"entity:dashboard:{dashboard_id}",
                    f"detail:dashboard:{dashboard_id}",
                    f"collection:dashboard:user:{user_info['id']}",
                    f"resource:dashboard",
                )

                return result

        except (
            DashboardNotFoundError,
            InvalidOperationError,
            VersionNotFoundError,
        ) as e:
            logger.warning(f"Dashboard deletion failed: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=str(e),
            )
        except Exception as e:
            logger.error("=" * 50 + " Error in delete_dashboard " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in delete_dashboard " + "=" * 50)
            raise HTTPException(
                status_code=500,
                detail="Internal server error",
            )

    @staticmethod
    async def update_dashboard_details(
        user_info: Any,
        dashboard_id: uuid.UUID,
        update_data: DashboardUpdateDetailsSchema,
    ) -> Any:
        """
        Update dashboard details (name, description, metadata).

        Args:
            user_info: User information object
            dashboard_id: Dashboard ID
            update_data: Dashboard update data

        Returns:
            Result from CoreDashboard.update_dashboard_details()
        """
        # Check user permission first - outside try block to avoid catching HTTPException
        has_permission = await PermissionService.check_user_permission(
            user_info=user_info,
            dashboard_id=dashboard_id,
            user_id=user_info["id"],
            required_permission="write",
        )

        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to update this dashboard",
            )

        try:
            async with db_manager.session() as session:
                # Get dashboard first
                dashboard = await session.get(Dashboard, dashboard_id)
                if not dashboard:
                    raise DashboardNotFoundError(f"Dashboard {dashboard_id} not found")

                result = await CoreDashboard.update_dashboard_details(
                    session=session,
                    dashboard=dashboard,
                    update_data=update_data,
                    user_id=user_info["id"],
                )

                # Build detailed field descriptions
                field_descriptions = []
                if hasattr(update_data, "name") and update_data.name:
                    field_descriptions.append("name")
                if hasattr(update_data, "description") and update_data.description:
                    field_descriptions.append("description")
                if (
                    hasattr(update_data, "dashboard_metadata")
                    and update_data.dashboard_metadata
                ):
                    field_descriptions.append("dashboard_metadata")

                # If no specific fields detected, use generic description
                if not field_descriptions:
                    description_text = "Updated dashboard details"
                else:
                    description_text = (
                        f"Updated dashboard {', '.join(field_descriptions)}"
                    )

                # Create activity log
                activity_log = ActivityLog(
                    entity_type=EntityType.DASHBOARD,
                    entity_id=dashboard_id,
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.DASHBOARD_UPDATED,
                    description=description_text,
                    activity_metadata={
                        "dashboard_id": str(dashboard_id),
                        "updated_fields": list(update_data.dict().keys()),
                    },
                )
                session.add(activity_log)
                await session.commit()

                # Invalidate cache using tags
                cache_manager = await get_cache()
                if result and hasattr(result, "dashboard_id"):
                    await cache_manager.delete_multi_level_by_tags(
                        f"entity:dashboard:{result.dashboard_id}",
                        f"detail:dashboard:{result.dashboard_id}",
                        f"collection:dashboard:user:{user_info['id']}",
                        f"resource:dashboard",
                    )
                else:
                    await cache_manager.delete_multi_level_by_tags(
                        f"collection:dashboard:user:{user_info['id']}",
                        f"resource:dashboard",
                    )

                return result

        except (
            DashboardNotFoundError,
            InvalidOperationError,
            VersionNotFoundError,
        ) as e:
            logger.warning(f"Dashboard details update failed: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=str(e),
            )
        except Exception as e:
            logger.error("=" * 50 + " Error in update_dashboard_details " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_dashboard_details " + "=" * 50
            )
            raise HTTPException(
                status_code=500,
                detail="Internal server error",
            )

    @staticmethod
    async def update_dashboard_content(
        user_info: Any,
        dashboard_id: uuid.UUID,
        content_data: DashboardUpdateContentSchema,
    ) -> Any:
        """
        Update dashboard content (widgets and layout).

        Args:
            user_info: User information object
            dashboard_id: Dashboard ID
            content_data: Dashboard content update data

        Returns:
            Result from CoreDashboard.create_or_update_draft()
        """
        # Check user permission first - outside try block to avoid catching HTTPException
        has_permission = await PermissionService.check_user_permission(
            user_info=user_info,
            dashboard_id=dashboard_id,
            user_id=user_info["id"],
            required_permission="write",
        )

        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to update this dashboard",
            )

        try:
            async with db_manager.session() as session:
                # Get dashboard first
                dashboard = await session.get(Dashboard, dashboard_id)
                if not dashboard:
                    raise DashboardNotFoundError(f"Dashboard {dashboard_id} not found")

                # Determine if we're creating a new draft or updating existing
                create_new_draft = True
                if dashboard.current_draft_version_id:
                    # Check if draft exists and we should update instead of create
                    draft_version = await session.get(
                        DashboardVersion, dashboard.current_draft_version_id
                    )
                    if draft_version and draft_version.status == "draft":
                        create_new_draft = False

                result = await CoreDashboard.create_or_update_draft(
                    session=session,
                    content=content_data,
                    create_new_draft=create_new_draft,
                    dashboard=dashboard,
                    user_id=user_info["id"],
                )

                # Analyze widget changes for descriptive logging
                widget_changes_description = ""
                if create_new_draft:
                    widget_changes_description = " with new widgets"
                elif hasattr(content_data, "content") and isinstance(
                    content_data.content, list
                ):
                    # Compare widget IDs for changes
                    current_draft = await session.get(
                        DashboardVersion, dashboard.current_draft_version_id
                    )
                    if current_draft and hasattr(current_draft, "content"):
                        # Extract widget IDs from current and new content
                        current_widget_ids = set()
                        if hasattr(current_draft, "content") and isinstance(
                            current_draft.content, list
                        ):
                            current_widget_ids = {
                                widget.get("widget_id")
                                for widget in current_draft.content
                                if widget.get("widget_id")
                            }

                        new_widget_ids = set()
                        if hasattr(content_data, "content") and isinstance(
                            content_data.content, list
                        ):
                            new_widget_ids = {
                                widget.get("widget_id")
                                for widget in content_data.content
                                if widget.get("widget_id")
                            }

                        # Calculate widget changes
                        added_widgets = new_widget_ids - current_widget_ids
                        removed_widgets = current_widget_ids - new_widget_ids

                        # Build descriptive message
                        if added_widgets and removed_widgets:
                            widget_changes_description = f": added {len(added_widgets)}, removed {len(removed_widgets)} widgets"
                        elif added_widgets:
                            widget_changes_description = (
                                f": added {len(added_widgets)} widgets"
                            )
                        elif removed_widgets:
                            widget_changes_description = (
                                f": removed {len(removed_widgets)} widgets"
                            )
                        else:
                            widget_changes_description = " with layout changes"

                action = "created" if create_new_draft else "updated"
                activity_log = ActivityLog(
                    entity_type=EntityType.DASHBOARD,
                    entity_id=dashboard_id,
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.DASHBOARD_UPDATED,
                    description=f"{action.capitalize()} draft version{widget_changes_description}",
                    activity_metadata={
                        "dashboard_id": str(dashboard_id),
                        "action": action,
                        "widget_changes": widget_changes_description.strip(": "),
                    },
                )
                session.add(activity_log)
                await session.commit()

                # Invalidate cache using tags
                cache_manager = await get_cache()
                if result and hasattr(result, "dashboard_id"):
                    await cache_manager.delete_multi_level_by_tags(
                        f"entity:dashboard:{result.dashboard_id}",
                        f"detail:dashboard:{result.dashboard_id}",
                        f"collection:dashboard:user:{user_info['id']}",
                        f"resource:dashboard",
                    )
                else:
                    await cache_manager.delete_multi_level_by_tags(
                        f"collection:dashboard:user:{user_info['id']}",
                        f"resource:dashboard",
                    )

                return result

        except (
            DashboardNotFoundError,
            InvalidOperationError,
            VersionNotFoundError,
        ) as e:
            logger.warning(f"Dashboard content update failed: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=str(e),
            )
        except Exception as e:
            logger.error("=" * 50 + " Error in update_dashboard_content " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_dashboard_content " + "=" * 50
            )
            raise HTTPException(
                status_code=500,
                detail="Internal server error",
            )
