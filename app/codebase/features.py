"""
Core features module for Dashboard API.

Provides CRUD operations for Share, Schedule, and Integration features.
All operations are designed to work within existing database transactions.
"""

import asyncio
import traceback
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import EntityType, Permission
from app.core.logging import logger
from app.dbmodels.features_models import Integration, Schedule, Share
from app.schemas.features_schema import (
    IntegrationCreate,
    ScheduleBase,
    ScheduleCreate,
    ScheduleUpdate,
    ShareBase,
    ShareCreate,
)


class CoreFeatures:
    """Core operations for dashboard features: Share, Schedule, and Integration."""

    # ===== SHARE OPERATIONS =====

    @staticmethod
    async def _create_share(
        session: AsyncSession,
        dashboard_id: UUID,
        share_data: ShareBase,
        user_id: UUID,
    ) -> Share:
        """Create a single share entry."""
        try:
            new_share = Share(
                dashboard_id=dashboard_id,
                shared_by=user_id,
                entity_type=share_data.entity_type,
                entity_id=share_data.entity_id,
                entity_name=share_data.entity_name,
                permission=share_data.permission,
            )
            session.add(new_share)
            await session.flush()
            return new_share

        except Exception as e:
            logger.error("=" * 50 + " Error in _create_share " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in _create_share " + "=" * 50)
            raise

    @staticmethod
    async def create_shares(
        session: AsyncSession, share_data: ShareCreate, user_id: UUID
    ) -> List[Share]:
        """Create multiple shares for a dashboard."""
        try:
            if isinstance(share_data.share_info, list):
                # Create multiple shares concurrently
                results = []
                for share_info in share_data.share_info:
                    result = await CoreFeatures._create_share(
                        session, share_data.dashboard_id, share_info, user_id
                    )
                    results.append(result)
            else:
                # Create single share
                result = await CoreFeatures._create_share(
                    session,
                    share_data.dashboard_id,
                    share_data.share_info,
                    user_id,
                )
                results = [result]

            return results

        except Exception as e:
            logger.error("=" * 50 + " Error in create_shares " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in create_shares " + "=" * 50)
            raise

    @staticmethod
    async def get_shares_by_dashboard(
        session: AsyncSession, dashboard_id: UUID
    ) -> List[Share]:
        """Get all shares for a specific dashboard."""
        try:
            stmt = select(Share).where(Share.dashboard_id == dashboard_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error("=" * 50 + " Error in get_shares_by_dashboard " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in get_shares_by_dashboard " + "=" * 50
            )
            raise

    @staticmethod
    async def get_shares_by_entity(
        session: AsyncSession, entity_type: EntityType, entity_id: UUID
    ) -> List[Share]:
        """Get all shares for a specific entity."""
        try:
            stmt = select(Share).where(
                and_(Share.entity_type == entity_type, Share.entity_id == entity_id)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error("=" * 50 + " Error in get_shares_by_entity " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in get_shares_by_entity " + "=" * 50)
            raise

    @staticmethod
    async def update_share_permission(
        session: AsyncSession, share_id: UUID, new_permission: Permission
    ) -> Optional[Share]:
        """Update permission for a specific share."""
        try:
            stmt = (
                update(Share)
                .where(Share.share_id == share_id)
                .values(permission=new_permission)
                .returning(Share)
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("=" * 50 + " Error in update_share_permission " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_share_permission " + "=" * 50
            )
            raise

    @staticmethod
    async def delete_share(session: AsyncSession, share_id: UUID) -> bool:
        """Delete a specific share."""
        try:
            stmt = delete(Share).where(Share.share_id == share_id)
            await session.execute(stmt)
            await session.flush()
            return True

        except Exception as e:
            logger.error("=" * 50 + " Error in delete_share " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in delete_share " + "=" * 50)
            raise

    @staticmethod
    async def delete_shares_by_dashboard(
        session: AsyncSession, dashboard_id: UUID
    ) -> int:
        """Delete all shares for a specific dashboard."""
        try:
            stmt = delete(Share).where(Share.dashboard_id == dashboard_id)
            await session.execute(stmt)
            await session.flush()
            return True

        except Exception as e:
            logger.error("=" * 50 + " Error in delete_shares_by_dashboard " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in delete_shares_by_dashboard " + "=" * 50
            )
            raise

    # ===== SCHEDULE OPERATIONS =====

    @staticmethod
    async def _create_schedule(
        session: AsyncSession,
        dashboard_id: UUID,
        schedule_data: ScheduleBase,
        user_id: UUID,
        username: str,
    ) -> Schedule:
        """Create a single schedule entry."""
        try:
            new_schedule = Schedule(
                dashboard_id=dashboard_id,
                created_by=user_id,
                created_by_username=username,
                schedule_type=schedule_data.schedule_type,
                frequency=schedule_data.frequency,
                hour=schedule_data.hour,
                minute=schedule_data.minute,
                period=schedule_data.period,
                start_date=schedule_data.start_date,
                end_date=schedule_data.end_date,
                days_of_week=schedule_data.days_of_week,
                timezone=schedule_data.time_zone,
            )
            session.add(new_schedule)
            await session.flush()
            return new_schedule

        except Exception as e:
            logger.error("=" * 50 + " Error in _create_schedule " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in _create_schedule " + "=" * 50)
            raise

    @staticmethod
    async def create_schedules(
        session: AsyncSession,
        schedule_data: ScheduleCreate,
        user_id: UUID,
        username: str,
    ) -> List[Schedule]:
        """Create multiple schedules for a dashboard."""
        try:
            if isinstance(schedule_data.schedule_info, list):
                # Create multiple schedules concurrently
                results = []
                for schedule_info in schedule_data.schedule_info:
                    result = await CoreFeatures._create_schedule(
                        session,
                        schedule_data.dashboard_id,
                        schedule_info,
                        user_id,
                        username,
                    )
                    results.append(result)

            else:
                # Create single schedule
                result = await CoreFeatures._create_schedule(
                    session,
                    schedule_data.dashboard_id,
                    schedule_data.schedule_info,
                    user_id,
                    username,
                )
                results = [result]

            return results

        except Exception as e:
            logger.error("=" * 50 + " Error in create_schedules " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in create_schedules " + "=" * 50)
            raise

    @staticmethod
    async def get_schedules_by_dashboard(
        session: AsyncSession, dashboard_id: UUID
    ) -> List[Schedule]:
        """Get all schedules for a specific dashboard."""
        try:
            stmt = select(Schedule).where(Schedule.dashboard_id == dashboard_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error("=" * 50 + " Error in get_schedules_by_dashboard " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in get_schedules_by_dashboard " + "=" * 50
            )
            raise

    @staticmethod
    async def get_active_schedules(session: AsyncSession) -> List[Schedule]:
        """Get all active schedules."""
        try:
            stmt = select(Schedule).where(Schedule.is_active)
            result = await session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error("=" * 50 + " Error in get_active_schedules " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in get_active_schedules " + "=" * 50)
            raise

    @staticmethod
    async def update_schedule_status(
        session: AsyncSession, schedule_id: UUID, is_active: bool
    ) -> Optional[Schedule]:
        """Update active status for a schedule."""
        try:
            stmt = (
                update(Schedule)
                .where(Schedule.schedule_id == schedule_id)
                .values(is_active=is_active)
                .returning(Schedule)
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("=" * 50 + " Error in update_schedule_status " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_schedule_status " + "=" * 50
            )
            raise

    @staticmethod
    async def update_schedule_last_run(
        session: AsyncSession, schedule_id: UUID, last_run_at: datetime
    ) -> Optional[Schedule]:
        """Update last run timestamp for a schedule."""
        try:
            stmt = (
                update(Schedule)
                .where(Schedule.schedule_id == schedule_id)
                .values(last_run_at=last_run_at)
                .returning(Schedule)
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("=" * 50 + " Error in update_schedule_last_run " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_schedule_last_run " + "=" * 50
            )
            raise

    @staticmethod
    async def update_schedule(
        session: AsyncSession, schedule_id: UUID, update_data: ScheduleUpdate
    ) -> Optional[Schedule]:
        """Update schedule configuration."""
        try:
            # Build update dictionary from the schema data
            update_values = {
                "schedule_type": update_data.schedule_type,
                "frequency": update_data.frequency,
                "hour": update_data.hour,
                "minute": update_data.minute,
                "period": update_data.period,
                "start_date": update_data.start_date,
                "end_date": update_data.end_date,
                "days_of_week": update_data.days_of_week,
                "timezone": update_data.time_zone,
            }

            # Remove None values to avoid overwriting with null
            update_values = {k: v for k, v in update_values.items() if v is not None}

            stmt = (
                update(Schedule)
                .where(Schedule.schedule_id == schedule_id)
                .values(**update_values)
                .returning(Schedule)
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("=" * 50 + " Error in update_schedule " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in update_schedule " + "=" * 50)
            raise

    @staticmethod
    async def delete_schedule(session: AsyncSession, schedule_id: UUID) -> bool:
        """Delete a specific schedule."""
        try:
            stmt = delete(Schedule).where(Schedule.schedule_id == schedule_id)
            await session.execute(stmt)
            await session.flush()
            return True

        except Exception as e:
            logger.error("=" * 50 + " Error in delete_schedule " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in delete_schedule " + "=" * 50)
            raise

    @staticmethod
    async def delete_schedules_by_dashboard(
        session: AsyncSession, dashboard_id: UUID
    ) -> int:
        """Delete all schedules for a specific dashboard."""
        try:
            stmt = delete(Schedule).where(Schedule.dashboard_id == dashboard_id)
            await session.execute(stmt)
            await session.flush()
            return True

        except Exception as e:
            logger.error(
                "=" * 50 + " Error in delete_schedules_by_dashboard " + "=" * 50
            )
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in delete_schedules_by_dashboard " + "=" * 50
            )
            raise

    # ===== INTEGRATION OPERATIONS =====

    @staticmethod
    async def _create_integration(
        session: AsyncSession,
        dashboard_id: UUID,
        integration_type: str,
        user_id: UUID,
        username: str,
        config: Optional[dict] = None,
    ) -> Integration:
        """Create a single integration entry."""
        try:
            new_integration = Integration(
                dashboard_id=dashboard_id,
                name=integration_type,
                added_by=user_id,
                created_by_username=username,
                config=config,
            )
            session.add(new_integration)
            await session.flush()
            return new_integration

        except Exception as e:
            logger.error("=" * 50 + " Error in _create_integration " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in _create_integration " + "=" * 50)
            raise

    @staticmethod
    async def create_integrations(
        session: AsyncSession,
        integration_data: IntegrationCreate,
        user_id: UUID,
        username: str,
    ) -> List[Integration]:
        """Create multiple integrations for a dashboard."""
        try:
            if isinstance(integration_data.integration_type, list):
                # Create multiple integrations concurrently
                results = []
                for integration_type in integration_data.integration_type:
                    result = await CoreFeatures._create_integration(
                        session,
                        integration_data.dashboard_id,
                        integration_type.value
                        if hasattr(integration_type, "value")
                        else integration_type,
                        user_id,
                        username,
                    )
                    results.append(result)
            else:
                # Create single integration
                result = await CoreFeatures._create_integration(
                    session,
                    integration_data.dashboard_id,
                    integration_data.integration_type.value
                    if hasattr(integration_data.integration_type, "value")
                    else integration_data.integration_type,
                    user_id,
                    username,
                )
                results = [result]

            return results

        except Exception as e:
            logger.error("=" * 50 + " Error in create_integrations " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in create_integrations " + "=" * 50)
            raise

    @staticmethod
    async def get_integrations_by_dashboard(
        session: AsyncSession, dashboard_id: UUID
    ) -> List[Integration]:
        """Get all integrations for a specific dashboard."""
        try:
            stmt = select(Integration).where(Integration.dashboard_id == dashboard_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

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
    async def get_active_integrations(session: AsyncSession) -> List[Integration]:
        """Get all active integrations."""
        try:
            stmt = select(Integration).where(Integration.is_active)
            result = await session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error("=" * 50 + " Error in get_active_integrations " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in get_active_integrations " + "=" * 50
            )
            raise

    @staticmethod
    async def update_integration_config(
        session: AsyncSession, integration_id: UUID, config: dict
    ) -> Optional[Integration]:
        """Update configuration for an integration."""
        try:
            stmt = (
                update(Integration)
                .where(Integration.integration_id == integration_id)
                .values(config=config)
                .returning(Integration)
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("=" * 50 + " Error in update_integration_config " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_integration_config " + "=" * 50
            )
            raise

    @staticmethod
    async def update_integration_status(
        session: AsyncSession, integration_id: UUID, is_active: bool
    ) -> Optional[Integration]:
        """Update active status for an integration."""
        try:
            stmt = (
                update(Integration)
                .where(Integration.integration_id == integration_id)
                .values(is_active=is_active)
                .returning(Integration)
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("=" * 50 + " Error in update_integration_status " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_integration_status " + "=" * 50
            )
            raise

    @staticmethod
    async def update_integration_sync_status(
        session: AsyncSession,
        integration_id: UUID,
        last_sync_at: datetime,
        status: str,
        error: Optional[str] = None,
    ) -> Optional[Integration]:
        """Update sync status for an integration."""
        try:
            stmt = (
                update(Integration)
                .where(Integration.integration_id == integration_id)
                .values(
                    last_sync_at=last_sync_at,
                    last_sync_status=status,
                    last_sync_error=error,
                )
                .returning(Integration)
            )
            result = await session.execute(stmt)
            await session.flush()
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(
                "=" * 50 + " Error in update_integration_sync_status " + "=" * 50
            )
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in update_integration_sync_status " + "=" * 50
            )
            raise

    @staticmethod
    async def delete_integration(session: AsyncSession, integration_id: UUID) -> bool:
        """Delete a specific integration."""
        try:
            stmt = delete(Integration).where(
                Integration.integration_id == integration_id
            )
            await session.execute(stmt)
            await session.flush()
            return True

        except Exception as e:
            logger.error("=" * 50 + " Error in delete_integration " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in delete_integration " + "=" * 50)
            raise

    @staticmethod
    async def delete_integrations_by_dashboard(
        session: AsyncSession, dashboard_id: UUID
    ) -> int:
        """Delete all integrations for a specific dashboard."""
        try:
            stmt = delete(Integration).where(Integration.dashboard_id == dashboard_id)
            await session.execute(stmt)
            await session.flush()
            return True

        except Exception as e:
            logger.error(
                "=" * 50 + " Error in delete_integrations_by_dashboard " + "=" * 50
            )
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50
                + " Error ended in delete_integrations_by_dashboard "
                + "=" * 50
            )
            raise
