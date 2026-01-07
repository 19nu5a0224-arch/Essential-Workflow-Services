"""
Widget Locking Service for concurrent editing collaboration.
True async implementation optimized for high-frequency polling.
Uses CoreWidgetLocking pattern for database operations.
"""

import uuid
from datetime import datetime, timedelta, timezone
datetime.now(timezone.utc)
from typing import Any, Dict, List, Tuple
from uuid import UUID

from sqlalchemy import select

from app.codebase.widget_locking import CoreWidgetLocking
from app.core.database import db_manager
from app.core.logging import logger
from app.dbmodels.widget_locking_models import UserSession, WidgetLock
from app.schemas.widget_locking_schemas import (
    HeartbeatResponse,
    LockAcquisitionResponse,
    UserSessionSchema,
    WidgetLockSchema,
    WidgetLockStatusResponse,
)
from app.utils.cache import generate_predictable_key, get_cache


class WidgetLockingService:
    """
    High-performance widget locking service for real-time collaboration.
    Optimized for concurrent polling requests every 2-10 seconds.
    Uses CoreWidgetLocking pattern for database operations.
    """

    def __init__(self):
        self.cache_manager = None
        self._initialized = False
        self.lock_expiration_threshold = timedelta(minutes=2)  # Default lock duration
        self.session_timeout = timedelta(minutes=5)  # Session timeout
        self.heartbeat_interval = timedelta(seconds=10)  # Heartbeat frequency

    async def initialize(self):
        """Initialize the service and cache."""
        if not self._initialized:
            self.cache_manager = await get_cache()
            self._initialized = True

    # Cache key generation for widget locking
    def _cache_key_widget_lock(self, widget_id: uuid.UUID) -> str:
        return generate_predictable_key("widget_lock", widget_id)

    def _cache_key_dashboard_sessions(self, dashboard_id: uuid.UUID) -> str:
        return generate_predictable_key("dashboard_sessions", dashboard_id)

    def _cache_key_widget_status(self, widget_id: uuid.UUID) -> str:
        return generate_predictable_key("widget_status", widget_id)

    def _cache_key_session_locks(self, session_id: uuid.UUID) -> str:
        return generate_predictable_key("session_locks", session_id)

    # Core locking operations
    async def acquire_widget_lock(
        self,
        dashboard_id: uuid.UUID,
        widget_id: uuid.UUID,
        user_info: Dict,
        lock_duration: int = 60,
    ) -> LockAcquisitionResponse:
        """
        Acquire a lock on a widget for concurrent editing.
        Uses CoreWidgetLocking pattern for database operations.
        """
        try:
            # Check cache first
            # Ensure cache manager is initialized
            if not self._initialized:
                await self.initialize()
            cache_key = self._cache_key_widget_lock(widget_id)
            existing_lock = await self.cache_manager.get_shared(cache_key)
            print("existing_lock", existing_lock)
            if existing_lock:
                existing_lock_data = WidgetLockSchema(**existing_lock)
                if existing_lock_data.time_remaining > 0:
                    return LockAcquisitionResponse(
                        success=False,
                        widget_id=widget_id,
                        session_id=uuid.uuid4(),  # Placeholder
                        expires_at=datetime.now(timezone.utc),
                        message=f"Widget is locked by {existing_lock_data.user_name}",
                    )

            # Check database for active lock using CoreWidgetLocking pattern
            async with db_manager.session() as session:
                db_lock = await CoreWidgetLocking.get_active_widget_lock(session, widget_id)
                if db_lock and not db_lock.is_expired:
                    return LockAcquisitionResponse(
                        success=False,
                        widget_id=widget_id,
                        session_id=db_lock.session_id,
                        expires_at=db_lock.expires_at,
                        message=f"Widget is locked by {db_lock.user_name}",
                    )
            # Use CoreWidgetLocking to acquire lock (includes session creation)
            async with db_manager.session() as session:
                widget_lock = await CoreWidgetLocking.acquire_widget_lock(
                    session=session,
                    dashboard_id=dashboard_id,
                    widget_id=widget_id,
                    user_info=user_info,
                    lock_duration=lock_duration,
                )

            # Ensure cache manager is initialized
            if not self._initialized:
                await self.initialize()

            # Update cache
            lock_data = WidgetLockSchema(
                widget_id=widget_lock.widget_id,
                dashboard_id=widget_lock.dashboard_id,
                session_id=widget_lock.session_id,
                user_id=widget_lock.user_id,
                user_name=widget_lock.user_name,
                locked_at=widget_lock.locked_at,
                expires_at=widget_lock.expires_at,
                last_heartbeat=widget_lock.last_heartbeat,
                time_remaining=widget_lock.time_remaining,
            )

            await self.cache_manager.set_shared(
                cache_key, lock_data.dict(), ttl=min(lock_duration, 30)
            )

            # Invalidate dashboard sessions cache using tags
            await self.cache_manager.delete_multi_level_by_tags(
                "resource:dashboard_sessions",
                f"entity:dashboard:{dashboard_id}",
            )

            # Log collaboration event using CoreWidgetLocking
            async with db_manager.session() as session:
                await CoreWidgetLocking.log_collaboration_event(
                    session,
                    dashboard_id,
                    user_info,
                    "lock_acquired",
                    widget_id=widget_id,
                    event_data={"duration": lock_duration},
                )

            return LockAcquisitionResponse(
                success=True,
                widget_id=widget_id,
                session_id=widget_lock.session_id,
                expires_at=widget_lock.expires_at,
                message="Widget lock acquired successfully",
            )

        except Exception as e:
            logger.error(f"Failed to acquire widget lock: {str(e)}")
            await session.rollback()
            return LockAcquisitionResponse(
                success=False,
                widget_id=widget_id,
                session_id=uuid.uuid4(),
                expires_at=datetime.now(timezone.utc),
                message=f"Failed to acquire lock: {str(e)}",
            )

    async def refresh_widget_lock(
        self,
        dashboard_id: uuid.UUID,
        widget_id: uuid.UUID,
        user_info: Dict,
    ) -> HeartbeatResponse:
        """
        Refresh widget lock heartbeat with strict type checking.
        """
        try:
            # 1. Standardize the Request User ID to a UUID object
            raw_user_id = user_info.get("user_id")
            request_user_id = raw_user_id if isinstance(raw_user_id, UUID) else UUID(str(raw_user_id))

            async with db_manager.session() as session:
                # 2. Get the active lock
                widget_lock = await CoreWidgetLocking.get_active_widget_lock(
                    session, widget_id
                )

                # 3. Check if lock exists
                if not widget_lock:
                    return HeartbeatResponse(
                        success=False,
                        widget_id=widget_id,
                        expires_at=datetime.now(timezone.utc),
                        message="Widget lock not found or already released",
                    )

                # 4. DEBUG LOGGING (Check your terminal/logs for these lines)
                logger.debug(f"Lock Owner ID: {widget_lock.user_id} ({type(widget_lock.user_id)})")
                logger.debug(f"Request User ID: {request_user_id} ({type(request_user_id)})")

                # 5. Ownership Check (Compare UUID to UUID)
                if widget_lock.user_id != request_user_id:
                    return HeartbeatResponse(
                        success=False,
                        widget_id=widget_id,
                        expires_at=widget_lock.expires_at,
                        message="You don't own this widget lock",
                    )

                # 6. Check Expiration
                if widget_lock.is_expired:
                    return HeartbeatResponse(
                        success=False,
                        widget_id=widget_id,
                        expires_at=widget_lock.expires_at,
                        message="Widget lock has expired",
                    )

                # 7. Perform the Refresh
                updated_lock = await CoreWidgetLocking.refresh_widget_lock(
                    session=session,
                    widget_lock=widget_lock,
                    lock_duration=int(self.lock_expiration_threshold.total_seconds()),
                )

                # 8. Update User Session Activity in the same transaction
                user_session = await CoreWidgetLocking.get_user_session(
                    session, widget_lock.session_id
                )
                if user_session:
                    user_session.last_activity = datetime.now(timezone.utc)
                
                await session.commit()

            # 9. Update Cache
            cache_key = self._cache_key_widget_lock(widget_id)
            lock_data = WidgetLockSchema(
                widget_id=updated_lock.widget_id,
                dashboard_id=updated_lock.dashboard_id,
                session_id=updated_lock.session_id,
                user_id=updated_lock.user_id,
                user_name=updated_lock.user_name,
                locked_at=updated_lock.locked_at,
                expires_at=updated_lock.expires_at,
                last_heartbeat=updated_lock.last_heartbeat,
                time_remaining=updated_lock.time_remaining,
            )
            
            if not self._initialized: await self.initialize()
            await self.cache_manager.set_shared(cache_key, lock_data.dict(), ttl=30)

            return HeartbeatResponse(
                success=True,
                widget_id=widget_id,
                expires_at=updated_lock.expires_at,
                message="Widget lock heartbeat refreshed",
            )

        except Exception as e:
            logger.error(f"Service Error: refresh_widget_lock failed: {str(e)}")
            return HeartbeatResponse(
                success=False,
                widget_id=widget_id,
                expires_at=datetime.now(timezone.utc),
                message=f"Internal Error: {str(e)}",
            )
        
    async def release_widget_lock(
        self,
        dashboard_id: uuid.UUID,
        widget_id: uuid.UUID,
        user_info: Dict,
    ) -> bool:
        """
        Release a widget lock.
        """
        try:
            # 1. Perform DB Release
            async with db_manager.session() as session:
                success = await CoreWidgetLocking.release_widget_lock(
                    session=session,
                    dashboard_id=dashboard_id,
                    widget_id=widget_id,
                    user_info=user_info,
                )

            if not success:
                return False # Ownership check failed

            # 2. Handle Cache Invalidation
            if not self._initialized:
                await self.initialize()

            cache_key = self._cache_key_widget_lock(widget_id)
            status_key = self._cache_key_widget_status(widget_id)
            
            await self.cache_manager.delete_shared(cache_key)
            await self.cache_manager.delete_shared(status_key)
            
            # Invalidate dashboard sessions cache
            await self.cache_manager.delete_multi_level_by_tags(
                "resource:dashboard_sessions",
                f"entity:dashboard:{dashboard_id}",
            )

            # 3. Log Event (separate session to ensure logging even if primary fails)
            async with db_manager.session() as session:
                await CoreWidgetLocking.log_collaboration_event(
                    session,
                    dashboard_id,
                    user_info,
                    "lock_released",
                    widget_id=widget_id,
                )
                await session.commit()

            return True

        except Exception as e:
            logger.error(f"Service Error: Failed to release widget lock: {str(e)}")
            return False

    async def get_widget_lock_status(
        self, widget_id: uuid.UUID, current_user_id: uuid.UUID
    ) -> WidgetLockStatusResponse:
        """
        Get current lock status for a widget.
        Uses CoreWidgetLocking pattern for database operations.
        """
        try:
            # Ensure cache manager is initialized
            if not self._initialized:
                await self.initialize()

            # Try cache first
            cache_key = self._cache_key_widget_status(widget_id)
            cached_status = await self.cache_manager.get_shared(cache_key)

            if cached_status:
                return WidgetLockStatusResponse(**cached_status)

            # Get active lock using CoreWidgetLocking pattern
            async with db_manager.session() as session:
                widget_lock = await CoreWidgetLocking.get_active_widget_lock(
                    session, widget_id
                )
                if not widget_lock or datetime.now(timezone.utc) > widget_lock.expires_at:
                    status = WidgetLockStatusResponse(
                        widget_id=widget_id,
                        is_locked=False,
                        locked_by=None,
                        locked_by_user_id=None,
                        locked_at=None,
                        expires_at=None,
                        time_remaining=0,
                        can_acquire=True,
                    )
                else:
                    status = WidgetLockStatusResponse(
                        widget_id=widget_id,
                        is_locked=True,
                        locked_by=widget_lock.user_name,
                        locked_by_user_id=widget_lock.user_id,
                        locked_at=widget_lock.locked_at,
                        expires_at=widget_lock.expires_at,
                        time_remaining=widget_lock.time_remaining,
                        can_acquire=(widget_lock.user_id == current_user_id),
                    )

            # Ensure cache manager is initialized
            if not self._initialized:
                await self.initialize()

            # Cache for 2 seconds to reduce database load during polling
            await self.cache_manager.set_shared(cache_key, status.dict(), ttl=2)

            return status

        except Exception as e:
            logger.error(f"Failed to get widget lock status: {str(e)}")
            return WidgetLockStatusResponse(
                widget_id=widget_id,
                is_locked=False,
                locked_by=None,
                locked_by_user_id=None,
                locked_at=None,
                expires_at=None,
                time_remaining=0,
                can_acquire=True,
            )

    async def get_active_sessions(
        self, dashboard_id: uuid.UUID
    ) -> Tuple[List[UserSession], List[WidgetLock]]:
        """
        Get all active sessions and locks for a dashboard.
        Optimized for collaboration UI updates.
        """
        try:
            # Try cache first
            cache_key = self._cache_key_dashboard_sessions(dashboard_id)
            cached_data = await self.cache_manager.get_shared(cache_key)

            if cached_data:
                sessions = [UserSession(**sess) for sess in cached_data["sessions"]]
                locks = [WidgetLock(**lock) for lock in cached_data["locks"]]
                return sessions, locks

            async with db_manager.session() as session:
                sessions, locks = await CoreWidgetLocking.get_active_sessions(
                    session, dashboard_id
                )

                # Cache for 3 seconds (polling interval)
                cache_data = {
                    "sessions": [sess.__dict__ for sess in sessions],
                    "locks": [lock.__dict__ for lock in locks],
                }
                await self.cache_manager.set_shared(cache_key, cache_data, ttl=3)

                return list(sessions), list(locks)

        except Exception as e:
            logger.error(f"Failed to get active sessions: {str(e)}")
            return [], []

    async def start_dashboard_editing(
        self, dashboard_id: uuid.UUID, user_info: dict
    ) -> Any:
        """
        Start dashboard editing session when user opens dashboard in edit mode.

        Args:
            dashboard_id: Dashboard ID
            user_info: User information

        Returns:
            UserSession object
        """
        try:
            # Ensure cache manager is initialized
            if not self._initialized:
                await self.initialize()

            logger.debug(
                f"start_dashboard_editing - Creating session: dashboard_id={dashboard_id}, user_info={user_info}"
            )
            logger.debug(
                f"start_dashboard_editing - User ID: {user_info.get('user_id')}"
            )

            # Use CoreWidgetLocking to get or create user session
            async with db_manager.session() as session:
                user_session = await CoreWidgetLocking.get_or_create_user_session(
                    session, dashboard_id, user_info
                )
                logger.debug(
                    f"start_dashboard_editing - Session created: {user_session.session_id}"
                )
                logger.debug(
                    f"start_dashboard_editing - Session details: user_name={user_session.user_name}, is_active={user_session.is_active}"
                )

            # Update cache for active sessions
            cache_key = self._cache_key_dashboard_sessions(dashboard_id)
            await self.cache_manager.delete_shared(cache_key)

            # Log collaboration event
            async with db_manager.session() as session:
                await CoreWidgetLocking.log_collaboration_event(
                    session,
                    dashboard_id,
                    user_info,
                    "dashboard_edit_started",
                    event_data={"session_id": str(user_session.session_id)},
                )

            return user_session

        except Exception as e:
            logger.error(f"Failed to start dashboard editing: {str(e)}")
            raise

    async def stop_dashboard_editing(
        self, dashboard_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """
        Stop dashboard editing session when user leaves edit mode.

        Args:
            dashboard_id: Dashboard ID
            user_id: User ID

        Returns:
            True if session was stopped, False if no session found
        """
        try:
            # Ensure cache manager is initialized
            if not self._initialized:
                await self.initialize()

            logger.debug(
                f"stop_dashboard_editing - Looking for session: dashboard_id={dashboard_id}, user_id={user_id}"
            )
            logger.debug(f"stop_dashboard_editing - User ID type: {type(user_id)}")

            # Use CoreWidgetLocking to find and stop user session
            async with db_manager.session() as session:
                # Find active session for this user and dashboard
                user_id_uuid = user_id if isinstance(user_id, UUID) else UUID(user_id)
                logger.debug(
                    f"stop_dashboard_editing - Converted user_id: {user_id_uuid}"
                )

                stmt = select(UserSession).where(
                    UserSession.dashboard_id == dashboard_id,
                    UserSession.user_id == user_id_uuid,
                    UserSession.is_active,
                )
                result = await session.execute(stmt)
                user_session = result.scalar_one_or_none()

                if not user_session:
                    logger.debug(
                        f"stop_dashboard_editing - No session found. Query: dashboard_id={dashboard_id}, user_id={user_id_uuid}, is_active=True"
                    )
                    logger.debug(
                        "stop_dashboard_editing - Checking if session exists but is inactive..."
                    )

                    # Check if session exists but is inactive
                    stmt_inactive = select(UserSession).where(
                        UserSession.dashboard_id == dashboard_id,
                        UserSession.user_id == user_id_uuid,
                        UserSession.is_active == False,
                    )
                    result_inactive = await session.execute(stmt_inactive)
                    inactive_session = result_inactive.scalar_one_or_none()

                    if inactive_session:
                        logger.debug(
                            f"stop_dashboard_editing - Found inactive session: {inactive_session.session_id}"
                        )
                        return True  # Session already stopped

                    logger.debug("stop_dashboard_editing - No session found at all")

                    # Check if session was cleaned up by APScheduler but user still has locks
                    # Try to cleanup any remaining locks for this user
                    stmt_locks = select(WidgetLock).where(
                        WidgetLock.dashboard_id == dashboard_id,
                        WidgetLock.user_id == user_id_uuid,
                        WidgetLock.is_active == True,
                    )
                    result_locks = await session.execute(stmt_locks)
                    active_locks = result_locks.scalars().all()

                    if active_locks:
                        logger.debug(
                            f"stop_dashboard_editing - Cleaning up {len(active_locks)} orphaned locks"
                        )
                        for lock in active_locks:
                            lock.is_active = False
                        await session.flush()
                        logger.debug(
                            "stop_dashboard_editing - Orphaned locks cleaned up"
                        )

                    # Consider session cleanup successful if we found no session
                    # This handles the case where APScheduler already cleaned it up
                    return True

                # Mark session as inactive
                logger.debug(
                    f"stop_dashboard_editing - Found active session: {user_session.session_id}"
                )
                logger.debug(
                    f"stop_dashboard_editing - Session details: user_name={user_session.user_name}, connected_at={user_session.connected_at}, last_activity={user_session.last_activity}"
                )

                user_session.is_active = False
                await session.commit()
                logger.debug("stop_dashboard_editing - Session marked as inactive")

            # Update cache for active sessions
            cache_key = self._cache_key_dashboard_sessions(dashboard_id)
            await self.cache_manager.delete_shared(cache_key)

            # Log collaboration event
            async with db_manager.session() as session:
                await CoreWidgetLocking.log_collaboration_event(
                    session,
                    dashboard_id,
                    {"user_id": user_id},
                    "dashboard_edit_stopped",
                    event_data={"session_id": str(user_session.session_id)},
                )

            return True

        except Exception as e:
            logger.error(f"Failed to stop dashboard editing: {str(e)}")
            return False

    async def refresh_dashboard_editing(
        self, dashboard_id: UUID, user_id:UUID
    ) -> bool:
        """
        Refresh dashboard editing session heartbeat.

        Args:
            dashboard_id: Dashboard ID
            user_id: User ID

        Returns:
            True if session was refreshed, False if no session found
        """
        try:
            # Ensure cache manager is initialized
            if not self._initialized:
                await self.initialize()

            # Use CoreWidgetLocking to find and refresh user session
            async with db_manager.session() as session:
                # Find active session for this user and dashboard
                user_id_uuid = user_id if isinstance(user_id, UUID) else UUID(user_id)
                logger.debug(
                    f"refresh_dashboard_editing - Looking for session: dashboard_id={dashboard_id}, user_id={user_id_uuid}"
                )

                stmt = select(UserSession).where(
                    UserSession.dashboard_id == dashboard_id,
                    UserSession.user_id == user_id_uuid,
                    UserSession.is_active,
                )
                result = await session.execute(stmt)
                user_session = result.scalar_one_or_none()

                if not user_session:
                    logger.debug(
                        f"refresh_dashboard_editing - No active session found for user {user_id_uuid} on dashboard {dashboard_id}"
                    )
                    logger.debug(
                        "refresh_dashboard_editing - Attempting to recreate session"
                    )

                    # Try to find any session (even inactive) for this user and dashboard
                    stmt_any = select(UserSession).where(
                        UserSession.dashboard_id == dashboard_id,
                        UserSession.user_id == user_id_uuid,
                    )
                    result_any = await session.execute(stmt_any)
                    any_session = result_any.scalar_one_or_none()

                    if any_session:
                        logger.debug(
                            f"refresh_dashboard_editing - Found existing session (inactive): {any_session.session_id}"
                        )
                        # Reactivate the session
                        any_session.is_active = True
                        any_session.last_activity = datetime.now(timezone.utc)
                        await session.commit()
                        logger.debug("refresh_dashboard_editing - Session reactivated")
                        return True
                    else:
                        logger.debug(
                            "refresh_dashboard_editing - No session found to reactivate"
                        )
                        return False

                # Update last activity
                user_session.last_activity = datetime.now(timezone.utc)
                await session.commit()
                logger.debug(
                    f"refresh_dashboard_editing - Session heartbeat updated: {user_session.session_id}"
                )

            # Update cache for active sessions
            cache_key = self._cache_key_dashboard_sessions(dashboard_id)
            await self.cache_manager.delete_shared(cache_key)

            return True

        except Exception as e:
            logger.error(f"Failed to refresh dashboard editing: {str(e)}")
            return False

    async def cleanup_stale_sessions_and_locks(self) -> Tuple[int, int]:
        # Ensure service is initialized
        if not self._initialized:
            await self.initialize()
        """
        Clean up stale sessions and expired locks.
        Uses CoreWidgetLocking pattern for database operations.
        """
        try:
            # Use CoreWidgetLocking for cleanup
            async with db_manager.session() as session:
                (
                    expired_locks_count,
                    stale_sessions_count,
                ) = await CoreWidgetLocking.cleanup_stale_sessions_and_locks(session)

            # Clear relevant cache
            # Clear relevant cache using tags
            await self.cache_manager.delete_multi_level_by_tags("resource:widget_lock")
            await self.cache_manager.delete_multi_level_by_tags(
                "resource:dashboard_sessions"
            )
            await self.cache_manager.delete_multi_level_by_tags(
                "resource:widget_status"
            )

            # Cleanup completed silently
            return expired_locks_count, stale_sessions_count

        except Exception as e:
            logger.error(f"Failed to cleanup stale sessions and locks: {str(e)}")
            await session.rollback()
            return 0, 0

    # Following CoreWidgetLocking pattern, database operations are handled by CoreWidgetLocking class


# Global service instance
_widget_locking_service = WidgetLockingService()


async def get_widget_locking_service() -> WidgetLockingService:
    """Get the global widget locking service instance."""
    return _widget_locking_service


async def initialize_widget_locking_service():
    """Initialize the widget locking service."""
    await _widget_locking_service.initialize()
