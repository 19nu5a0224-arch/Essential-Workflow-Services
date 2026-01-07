"""
Features Service Layer

Handles dashboard features operations (Share, Schedule, Integration) with permission checks and proper error handling.
Follows the flow: API -> Service Layer -> Permission Layer -> Codebase -> Database
"""

import traceback
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.codebase.features import CoreFeatures
from app.core.config import settings
from app.core.database import db_manager
from app.core.enums import Permission
from app.core.logging import logger
from app.dbmodels.activity_log import ActionType, ActivityLog, EntityType
from app.dbmodels.features_models import Integration, Schedule, Share
from app.dbmodels.n8n_models import N8NWorkflowStatus
from app.schemas.features_schema import (
    IntegrationCreate,
    ScheduleCreate,
    ScheduleUpdate,
    ShareCreate,
)
from app.services.n8n_service import N8NService
from app.services.permission_service import PermissionService
from app.utils.cache import cached_features, cached_schedules, cached_shares, get_cache


class FeaturesService:
    """Service for handling dashboard features operations with permission checks."""

    @staticmethod
    async def create_shares(user_info: Any, share_data: ShareCreate) -> Any:
        """
        Create shares for a dashboard.

        Args:
            user_info: User information object
            share_data: Share creation data

        Returns:
            Result from codebase/features.py create_shares()
        """
        try:
            # Check if user has write permission for the dashboard
            has_permission = await PermissionService.check_user_permission(
                user_info=user_info,
                dashboard_id=share_data.dashboard_id,
                user_id=user_info["id"],
                required_permission="write",
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to create shares for this dashboard",
                )

            # Create shares using codebase
            async with db_manager.session() as session:
                result = await CoreFeatures.create_shares(
                    session=session,
                    share_data=share_data,
                    user_id=user_info["id"],
                )
                # Create activity log for share creation
                activity_log = ActivityLog(
                    entity_type=EntityType.SHARE,
                    entity_id=str(share_data.dashboard_id),
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.SHARE_CREATED,
                    description="Created share(s) for dashboard",
                    activity_metadata={
                        "dashboard_id": str(share_data.dashboard_id),
                        "share_count": len(result) if isinstance(result, list) else 1,
                    },
                )
                session.add(activity_log)
                await session.commit()

                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:features",
                    f"entity:dashboard:{share_data.dashboard_id}",
                    f"collection:features:dashboard:{share_data.dashboard_id}",
                    f"resource:dashboard",
                )
                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in create_shares " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in create_shares " + "=" * 50)
            raise

    @staticmethod
    @cached_shares(ttl=settings.CACHE_TTL_DEFAULT)  # Cache shares using consistent TTL
    async def get_shares_by_dashboard(user_info: Any, dashboard_id: UUID) -> Any:
        """
        Get all shares for a specific dashboard.

        Args:
            user_info: User information object
            dashboard_id: Dashboard ID

        Returns:
            Result from codebase/features.py get_shares_by_dashboard()
        """
        try:
            # Check if user has read permission for the dashboard
            has_permission = await PermissionService.check_user_permission(
                user_info=user_info,
                dashboard_id=dashboard_id,
                user_id=user_info["id"],
                required_permission="read",
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view shares for this dashboard",
                )

            # Get shares using codebase
            async with db_manager.session() as session:
                result = await CoreFeatures.get_shares_by_dashboard(
                    session=session, dashboard_id=dashboard_id
                )
                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in get_shares_by_dashboard " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in get_shares_by_dashboard " + "=" * 50
            )
            raise

    @staticmethod
    async def update_share_permission(
        user_info: Any, share_id: UUID, new_permission: str
    ) -> Any:
        """
        Update share permission.

        Args:
            user_info: User information object
            share_id: Share ID
            new_permission: New permission level (read/write/admin)

        Returns:
            Result from codebase/features.py update_share_permission()
        """
        try:
            # Get the share first to find dashboard_id for permission check
            async with db_manager.session() as session:
                stmt = select(Share.dashboard_id).where(Share.share_id == share_id)
                result = await session.execute(stmt)
                share = result.scalar_one_or_none()

                if not share:
                    raise ValueError(f"Share with id {share_id} not found")

                dashboard_id = share

                # Check if user has write permission for the dashboard
                has_permission = await PermissionService.check_user_permission(
                    user_info=user_info,
                    dashboard_id=dashboard_id,
                    user_id=user_info["id"],
                    required_permission="write",
                )

                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You don't have permission to update share permissions for this dashboard",
                    )

                # Convert string permission to Permission enum
                permission_enum = Permission(new_permission.lower())

                result = await CoreFeatures.update_share_permission(
                    session=session,
                    share_id=share_id,
                    new_permission=permission_enum,
                )
                # Create activity log for share permission update
                activity_log = ActivityLog(
                    entity_type=EntityType.SHARE,
                    entity_id=str(share_id),
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.SHARE_UPDATED,
                    description="Updated share permission",
                    activity_metadata={
                        "share_id": str(share_id),
                        "new_permission": new_permission,
                    },
                )
                session.add(activity_log)
                await session.commit()

                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:features",
                    f"entity:dashboard:{dashboard_id}",
                    f"collection:features:dashboard:{dashboard_id}",
                    f"resource:dashboard",
                )
                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in update_share_permission " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_share_permission " + "=" * 50
            )
            raise

    @staticmethod
    async def delete_share(user_info: Any, share_id: UUID) -> bool:
        """
        Delete a share.

        Args:
            user_info: User information object
            share_id: Share ID

        Returns:
            Success status
        """
        try:
            # Get the share first to find dashboard_id for permission check
            async with db_manager.session() as session:
                stmt = select(Share.dashboard_id).where(Share.share_id == share_id)
                result = await session.execute(stmt)
                share = result.scalar_one_or_none()

                if not share:
                    raise ValueError(f"Share with id {share_id} not found")

                dashboard_id = share

                # Check if user has write permission for the dashboard
                has_permission = await PermissionService.check_user_permission(
                    user_info=user_info,
                    dashboard_id=dashboard_id,
                    user_id=user_info["id"],
                    required_permission="write",
                )

                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You don't have permission to delete shares for this dashboard",
                    )

                result = await CoreFeatures.delete_share(
                    session=session, share_id=share_id
                )
                # Create activity log for share deletion
                activity_log = ActivityLog(
                    entity_type=EntityType.SHARE,
                    entity_id=str(share_id),
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.SHARE_REMOVED,
                    description="Deleted share for dashboard",
                    activity_metadata={"share_id": str(share_id)},
                )
                session.add(activity_log)
                await session.commit()

                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:features",
                    f"entity:dashboard:{dashboard_id}",
                    f"collection:features:dashboard:{dashboard_id}",
                    f"resource:dashboard",
                )
                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in delete_share " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in delete_share " + "=" * 50)
            raise

    @staticmethod
    async def create_schedules(user_info: Any, schedule_data: ScheduleCreate) -> Any:
        """
        Create schedules for a dashboard.

        Args:
            user_info: User information object
            schedule_data: Schedule creation data

        Returns:
            Result from codebase/features.py create_schedules()
        """
        try:
            # Check if user has write permission for the dashboard
            has_permission = await PermissionService.check_user_permission(
                user_info=user_info,
                dashboard_id=schedule_data.dashboard_id,
                user_id=user_info["id"],
                required_permission="write",
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to create schedules for this dashboard",
                )

            # Create schedules using codebase
            async with db_manager.session() as session:
                result = await CoreFeatures.create_schedules(
                    session=session,
                    schedule_data=schedule_data,
                    user_id=user_info["id"],
                    username=user_info["username"],
                )
                # Create activity log for schedule creation
                schedule_count = len(result) if isinstance(result, list) else 1
                activity_log = ActivityLog(
                    entity_type=EntityType.SCHEDULE,
                    entity_id=str(schedule_data.dashboard_id),
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.SCHEDULE_CREATED,
                    description=f"Created {schedule_count} schedule(s) for dashboard",
                    activity_metadata={
                        "dashboard_id": str(schedule_data.dashboard_id),
                        "schedule_count": schedule_count,
                    },
                )
                session.add(activity_log)

                # Create n8n workflows for the created schedules
                try:
                    n8n_service = N8NService()

                    # Get the actual schedule objects if result is list
                    schedules_to_process = (
                        result if isinstance(result, list) else [result]
                    )

                    for schedule in schedules_to_process:
                        # Create n8n workflow for this schedule
                        n8n_workflow = await n8n_service.create_or_update_workflow(
                            db_session=session,
                            schedule=schedule,
                            user_info=user_info,
                            workspace_id=str(user_info.get("workspace_id", "default")),
                            project_id=str(user_info.get("project_id", "default")),
                        )

                        if n8n_workflow:
                            logger.info(
                                f"Created n8n workflow for schedule {schedule.schedule_id}"
                            )
                        else:
                            logger.warning(
                                f"Failed to create n8n workflow for schedule {schedule.schedule_id}"
                            )

                except Exception as n8n_error:
                    # Log n8n error but don't fail the entire schedule creation
                    logger.error(f"N8N workflow creation failed: {str(n8n_error)}")

                await session.commit()
                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:features",
                    f"entity:dashboard:{schedule_data.dashboard_id}",
                    f"collection:features:dashboard:{schedule_data.dashboard_id}",
                    f"resource:schedules",
                )
                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in create_schedules " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in create_schedules " + "=" * 50)
            raise

    @staticmethod
    @cached_schedules(
        ttl=settings.CACHE_TTL_DEFAULT
    )  # Cache schedules using consistent TTL
    async def get_schedules_by_dashboard(user_info: Any, dashboard_id: UUID) -> Any:
        """
        Get all schedules for a specific dashboard.

        Args:
            user_info: User information object
            dashboard_id: Dashboard ID

        Returns:
            Result from codebase/features.py get_schedules_by_dashboard()
        """
        try:
            # Check if user has read permission for the dashboard
            has_permission = await PermissionService.check_user_permission(
                user_info=user_info,
                dashboard_id=dashboard_id,
                user_id=user_info["id"],
                required_permission="read",
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view schedules for this dashboard",
                )

            # Get schedules using codebase
            async with db_manager.session() as session:
                result = await CoreFeatures.get_schedules_by_dashboard(
                    session=session, dashboard_id=dashboard_id
                )
                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in get_schedules_by_dashboard " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in get_schedules_by_dashboard " + "=" * 50
            )
            raise

    @staticmethod
    async def update_schedule_status(
        user_info: Any, schedule_id: UUID, is_active: bool
    ) -> Any:
        """
        Update active status for a schedule.

        Args:
            user_info: User information object
            schedule_id: Schedule ID
            is_active: New active status

        Returns:
            Result from codebase/features.py update_schedule_status()
        """
        try:
            # Get the schedule first to find dashboard_id for permission check
            async with db_manager.session() as session:
                stmt = select(Schedule.dashboard_id).where(
                    Schedule.schedule_id == schedule_id
                )
                result = await session.execute(stmt)
                schedule = result.scalar_one_or_none()

                if not schedule:
                    raise ValueError(f"Schedule with id {schedule_id} not found")

                dashboard_id = schedule

                # Check if user has write permission for the dashboard
                has_permission = await PermissionService.check_user_permission(
                    user_info=user_info,
                    dashboard_id=dashboard_id,
                    user_id=user_info["id"],
                    required_permission="write",
                )

                if not has_permission:
                    raise PermissionError(
                        "User does not have permission to modify this schedule"
                    )

                result = await CoreFeatures.update_schedule_status(
                    session=session, schedule_id=schedule_id, is_active=is_active
                )
                # Create activity log for schedule status update
                activity_log = ActivityLog(
                    entity_type=EntityType.SCHEDULE,
                    entity_id=str(schedule_id),
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.SCHEDULE_UPDATED,
                    description=f"Updated schedule status to {'active' if is_active else 'inactive'}",
                    activity_metadata={
                        "schedule_id": str(schedule_id),
                        "is_active": is_active,
                    },
                )
                session.add(activity_log)

                # Update n8n workflow status
                try:
                    n8n_service = N8NService()

                    # Get associated n8n workflow
                    workflow = await n8n_service.get_workflow_by_schedule(
                        session, schedule_id
                    )
                    if workflow:
                        # Update workflow status in n8n
                        await n8n_service.activate_workflow(
                            workflow.n8n_workflow_id, is_active
                        )

                        # Update database status
                        new_status = (
                            N8NWorkflowStatus.ACTIVE
                            if is_active
                            else N8NWorkflowStatus.INACTIVE
                        )
                        await n8n_service.update_workflow_status(
                            session, workflow.workflow_id, new_status
                        )
                        logger.info(
                            f"Updated n8n workflow status for schedule {schedule_id}"
                        )

                except Exception as n8n_error:
                    # Log n8n error but don't fail the status update
                    logger.error(f"N8N workflow status update failed: {str(n8n_error)}")

                await session.commit()

                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:features",
                    f"entity:dashboard:{dashboard_id}",
                    f"collection:features:dashboard:{dashboard_id}",
                    f"resource:schedules",
                )

                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in update_schedule_status " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_schedule_status " + "=" * 50
            )
            raise

    @staticmethod
    async def update_schedule_with_n8n(
        user_info: Any, schedule_id: UUID, schedule_data: ScheduleUpdate
    ) -> Any:
        """
        Update schedule configuration and update associated N8N workflow.

        Args:
            user_info: User information object
            schedule_id: Schedule ID to update
            schedule_data: Updated schedule configuration

        Returns:
            Updated schedule information
        """
        try:
            # Validate schedule ID format
            if not schedule_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Schedule ID is required",
                )

            async with db_manager.session() as session:
                # Get existing schedule
                schedule_stmt = select(Schedule).where(
                    Schedule.schedule_id == schedule_id
                )
                schedule_result = await session.execute(schedule_stmt)
                schedule = schedule_result.scalar_one_or_none()

                if not schedule:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Schedule with id {schedule_id} not found",
                    )

                # Update schedule in database
                result = await CoreFeatures.update_schedule(
                    session=session, schedule_id=schedule_id, update_data=schedule_data
                )

                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update schedule",
                    )

                # Update N8N workflow with new schedule configuration
                try:
                    n8n_service = N8NService()

                    # Get associated workflow
                    workflow = await n8n_service.get_workflow_by_schedule(
                        session, schedule_id
                    )
                    if workflow:
                        # Build updated workflow data
                        workflow_data = n8n_service.build_workflow(
                            workflow_name=f"Dashboard {schedule.dashboard_id} - Schedule {schedule_id}",
                            user_id=user_info["id"],
                            dashboard_id=str(schedule.dashboard_id),
                            workspace_id="",  # Get from user_info or schedule if available
                            project_id="",  # Get from user_info or schedule if available
                            schedule_payload={
                                "hour": schedule_data.hour,
                                "minute": schedule_data.minute,
                                "period": schedule_data.period.value,
                                "frequency": schedule_data.frequency.value.lower(),
                                "daysOfWeek": schedule_data.days_of_week or [],
                                "dayOfMonth": schedule.day_of_month or 1,
                                "startDate": schedule_data.start_date.strftime(
                                    "%Y-%m-%d"
                                ),
                                "endDate": schedule_data.end_date.strftime("%Y-%m-%d")
                                if schedule_data.end_date
                                else "2030-12-31",
                                "timezone": schedule_data.time_zone,
                            },
                        )

                        # Update workflow in N8N using PUT endpoint
                        n8n_result = await n8n_service.update_workflow(
                            workflow.n8n_workflow_id, workflow_data
                        )

                        if n8n_result:
                            logger.info(
                                f"Successfully updated N8N workflow for schedule {schedule_id}"
                            )
                        else:
                            logger.warning(
                                f"Failed to update N8N workflow for schedule {schedule_id}"
                            )

                except Exception as n8n_error:
                    # Log N8N error but don't fail the schedule update
                    logger.error(f"N8N workflow update failed: {str(n8n_error)}")

                # Create activity log for schedule update
                activity_log = ActivityLog(
                    entity_type=EntityType.SCHEDULE,
                    entity_id=str(schedule_id),
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.SCHEDULE_UPDATED,
                    description="Updated schedule configuration",
                    activity_metadata={
                        "schedule_id": str(schedule_id),
                        "dashboard_id": str(schedule.dashboard_id),
                        "schedule_type": schedule_data.schedule_type.value,
                        "frequency": schedule_data.frequency.value,
                    },
                )
                session.add(activity_log)
                await session.commit()

                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:features",
                    f"entity:dashboard:{schedule.dashboard_id}",
                    f"collection:features:dashboard:{schedule.dashboard_id}",
                    f"resource:schedules",
                    f"entity:schedule:{schedule.schedule_id}",
                )

                return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error("=" * 50 + " Error in update_schedule_with_n8n " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_schedule_with_n8n " + "=" * 50
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while updating schedule",
            )

    @staticmethod
    async def delete_schedule(user_info: Any, schedule_id: UUID) -> bool:
        """
        Delete a schedule.

        Args:
            user_info: User information object
            schedule_id: Schedule ID

        Returns:
            Success status
        """
        try:
            # Get the schedule first to find dashboard_id for permission check
            async with db_manager.session() as session:
                stmt = select(Schedule.dashboard_id).where(
                    Schedule.schedule_id == schedule_id
                )
                result = await session.execute(stmt)
                schedule = result.scalar_one_or_none()

                if not schedule:
                    raise ValueError(f"Schedule with id {schedule_id} not found")

                dashboard_id = schedule

                # Check if user has write permission for the dashboard
                has_permission = await PermissionService.check_user_permission(
                    user_info=user_info,
                    dashboard_id=dashboard_id,
                    user_id=user_info["id"],
                    required_permission="write",
                )

                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You don't have permission to delete schedules for this dashboard",
                    )

                result = await CoreFeatures.delete_schedule(
                    session=session, schedule_id=schedule_id
                )
                # Create activity log for schedule deletion
                activity_log = ActivityLog(
                    entity_type=EntityType.SCHEDULE,
                    entity_id=str(schedule_id),
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.SCHEDULE_DELETED,
                    description="Deleted schedule for dashboard",
                    activity_metadata={"schedule_id": str(schedule_id)},
                )
                session.add(activity_log)

                # Delete n8n workflow
                try:
                    n8n_service = N8NService()

                    # Delete associated n8n workflow
                    success = await n8n_service.delete_workflow_by_schedule(
                        session, schedule_id
                    )
                    if success:
                        logger.info(f"Deleted n8n workflow for schedule {schedule_id}")
                    else:
                        logger.warning(
                            f"No n8n workflow found to delete for schedule {schedule_id}"
                        )

                except Exception as n8n_error:
                    # Log n8n error but don't fail the schedule deletion
                    logger.error(f"N8N workflow deletion failed: {str(n8n_error)}")

                await session.commit()

                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:features",
                    f"entity:dashboard:{dashboard_id}",
                    f"collection:features:dashboard:{dashboard_id}",
                    f"resource:schedules",
                )
                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in delete_schedule " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in delete_schedule " + "=" * 50)
            raise

    @staticmethod
    async def create_integrations(
        user_info: Any, integration_data: IntegrationCreate
    ) -> Any:
        """
        Create integrations for a dashboard.

        Args:
            user_info: User information object
            integration_data: Integration creation data

        Returns:
            Result from codebase/features.py create_integrations()
        """
        try:
            # Check if user has write permission for the dashboard
            has_permission = await PermissionService.check_user_permission(
                user_info=user_info,
                dashboard_id=integration_data.dashboard_id,
                user_id=user_info["id"],
                required_permission="write",
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to create integrations for this dashboard",
                )

            # Create integrations using codebase
            async with db_manager.session() as session:
                result = await CoreFeatures.create_integrations(
                    session=session,
                    integration_data=integration_data,
                    user_id=user_info["id"],
                    username=user_info["username"],
                )
                # Create activity log for integration creation
                integration_count = len(result) if isinstance(result, list) else 1
                activity_log = ActivityLog(
                    entity_type=EntityType.INTEGRATION,
                    entity_id=str(integration_data.dashboard_id),
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.INTEGRATION_ADDED,
                    description=f"Created {integration_count} integration(s) for dashboard",
                    activity_metadata={
                        "dashboard_id": str(integration_data.dashboard_id),
                        "integration_count": integration_count,
                    },
                )
                session.add(activity_log)
                await session.commit()

                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:features",
                    f"entity:dashboard:{integration_data.dashboard_id}",
                    f"collection:features:dashboard:{integration_data.dashboard_id}",
                    f"resource:integrations",
                )
                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in create_integrations " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in create_integrations " + "=" * 50)
            raise

    @staticmethod
    @cached_features(
        ttl=settings.CACHE_TTL_DEFAULT
    )  # Cache integrations using consistent TTL
    async def get_integrations_by_dashboard(user_info: Any, dashboard_id: UUID) -> Any:
        """
        Get all integrations for a specific dashboard.

        Args:
            user_info: User information object
            dashboard_id: Dashboard ID

        Returns:
            Result from codebase/features.py get_integrations_by_dashboard()
        """
        try:
            # Check if user has read permission for the dashboard
            has_permission = await PermissionService.check_user_permission(
                user_info=user_info,
                dashboard_id=dashboard_id,
                user_id=user_info["id"],
                required_permission="read",
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view integrations for this dashboard",
                )

            # Get integrations using codebase
            async with db_manager.session() as session:
                result = await CoreFeatures.get_integrations_by_dashboard(
                    session=session, dashboard_id=dashboard_id
                )
                return result

        except Exception as e:
            logger.error(
                "=" * 50 + " Error in get_integrations_by_dashboard " + "=" * 50
            )
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in get_integrations_by_dashboard " + "=" * 50
            )
            raise

    @staticmethod
    async def update_integration_config(
        user_info: Any, integration_id: UUID, config: dict
    ) -> Any:
        """
        Update integration configuration.

        Args:
            user_info: User information object
            integration_id: Integration ID
            config: New configuration

        Returns:
            Result from codebase/features.py update_integration_config()
        """
        try:
            # Get the integration first to find dashboard_id for permission check
            async with db_manager.session() as session:
                stmt = select(Integration.dashboard_id).where(
                    Integration.integration_id == integration_id
                )
                result = await session.execute(stmt)
                integration = result.scalar_one_or_none()

                if not integration:
                    raise ValueError(f"Integration with id {integration_id} not found")

                dashboard_id = integration

                # Check if user has write permission for the dashboard
                has_permission = await PermissionService.check_user_permission(
                    user_info=user_info,
                    dashboard_id=dashboard_id,
                    user_id=user_info["id"],
                    required_permission="write",
                )

                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You don't have permission to update integration configuration for this dashboard",
                    )

                result = await CoreFeatures.update_integration_config(
                    session=session, integration_id=integration_id, config=config
                )
                # Create activity log for integration update
                activity_log = ActivityLog(
                    entity_type=EntityType.INTEGRATION,
                    entity_id=str(integration_id),
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.INTEGRATION_UPDATED,
                    description="Updated integration configuration",
                    activity_metadata={
                        "integration_id": str(integration_id),
                    },
                )
                session.add(activity_log)
                await session.commit()

                # Invalidate cache using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:features",
                    f"entity:dashboard:{dashboard_id}",
                    f"collection:features:dashboard:{dashboard_id}",
                    f"resource:integrations",
                )
                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in update_integration_config " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_integration_config " + "=" * 50
            )
            raise

    @staticmethod
    async def delete_integration(user_info: Any, integration_id: UUID) -> bool:
        """
        Delete an integration.

        Args:
            user_info: User information object
            integration_id: Integration ID

        Returns:
            Success status
        """
        try:
            # Get the integration first to find dashboard_id for permission check
            async with db_manager.session() as session:
                stmt = select(Integration.dashboard_id).where(
                    Integration.integration_id == integration_id
                )
                result = await session.execute(stmt)
                integration = result.scalar_one_or_none()

                if not integration:
                    raise ValueError(f"Integration with id {integration_id} not found")

                dashboard_id = integration

                # Check if user has write permission for the dashboard
                has_permission = await PermissionService.check_user_permission(
                    user_info=user_info,
                    dashboard_id=dashboard_id,
                    user_id=user_info["id"],
                    required_permission="write",
                )

                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You don't have permission to delete integrations for this dashboard",
                    )

                result = await CoreFeatures.delete_integration(
                    session=session, integration_id=integration_id
                )
                # Create activity log for integration deletion
                activity_log = ActivityLog(
                    entity_type=EntityType.INTEGRATION,
                    entity_id=str(integration_id),
                    user_id=user_info["id"],
                    username=user_info["username"],
                    action_type=ActionType.INTEGRATION_REMOVED,
                    description="Deleted integration for dashboard",
                    activity_metadata={"integration_id": str(integration_id)},
                )
                session.add(activity_log)
                await session.commit()
                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in delete_integration " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in delete_integration " + "=" * 50)
            raise

    @staticmethod
    @cached_features(
        ttl=settings.CACHE_TTL_DEFAULT
    )  # Cache activity logs using consistent TTL
    async def get_activity_logs_by_dashboard(
        user_info: Any, dashboard_id: UUID, page: int = 1, page_size: int = 20
    ) -> dict:
        """
        Get activity logs for a specific dashboard with pagination.

        Args:
            user_info: User information object
            dashboard_id: Dashboard ID to get activity logs for
            page: Page number (starting from 1)
            page_size: Number of items per page

        Returns:
            Result from codebase/features.py get_activity_logs_by_dashboard()
        """
        try:
            # Check if user has permission to view the dashboard
            has_permission = await PermissionService.check_user_permission(
                user_info=user_info,
                dashboard_id=dashboard_id,
                user_id=user_info["id"],
                required_permission="read",
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view activity logs for this dashboard",
                )

            # Calculate offset
            offset = (page - 1) * page_size

            async with db_manager.session() as session:
                # Get total count
                from sqlalchemy import func

                count_stmt = select(func.count(ActivityLog.id)).where(
                    ActivityLog.entity_id == dashboard_id,
                    ActivityLog.entity_type == EntityType.DASHBOARD,
                )
                total_count = await session.scalar(count_stmt)

                # Get paginated results
                stmt = (
                    select(ActivityLog)
                    .where(
                        ActivityLog.entity_id == dashboard_id,
                        ActivityLog.entity_type == EntityType.DASHBOARD,
                    )
                    .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
                    .offset(offset)
                    .limit(page_size)
                )
                result = await session.execute(stmt)
                activity_logs = result.scalars().all()

                # Convert to dict format
                logs_data = []
                for log in activity_logs:
                    logs_data.append(
                        {
                            "id": str(log.id),
                            "entity_id": str(log.entity_id),
                            "entity_type": log.entity_type.value,
                            "user_id": str(log.user_id),
                            "username": log.username,
                            "action_type": log.action_type.value,
                            "description": log.description,
                            "activity_metadata": log.activity_metadata or {},
                            "created_at": log.created_at.isoformat(),
                        }
                    )

                # Calculate total pages
                total_pages = (
                    (total_count + page_size - 1) // page_size
                    if total_count and total_count > 0
                    else 1
                )

                return {
                    "logs": logs_data,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_items": total_count,
                        "total_pages": total_pages,
                        "has_next": page < total_pages,
                        "has_prev": page > 1,
                    },
                }

        except Exception as e:
            logger.error(
                "=" * 50 + " Error in get_activity_logs_by_dashboard " + "=" * 50
            )
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in get_activity_logs_by_dashboard " + "=" * 50
            )
            raise
