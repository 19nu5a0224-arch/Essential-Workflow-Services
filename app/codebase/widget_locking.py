"""
Core Widget Locking Operations
Database operations for widget locking and collaboration tracking
Following CoreDashboard pattern
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.dbmodels.widget_locking_models import (
    CollaborationEvent,
    UserSession,
    WidgetLock,
)


class CoreWidgetLocking:
    """
    Core widget locking operations following CoreDashboard pattern.
    Handles database operations for widget locking and session management.
    Compatible with existing WidgetLockingService methods.
    """

    # @staticmethod
    # async def acquire_widget_lock(
    #     session: AsyncSession,
    #     dashboard_id: UUID,
    #     widget_id: UUID,
    #     user_info: dict,
    #     lock_duration: int = 60,
    # ) -> WidgetLock:
    #     """
    #     Acquire a widget lock for concurrent editing.

    #     Args:
    #         session: Database session
    #         dashboard_id: Dashboard ID
    #         widget_id: Widget ID to lock
    #         user_session: User session acquiring the lock
    #         lock_duration: Lock duration in seconds (default: 60)

    #     Returns:
    #         Created WidgetLock object

    #     Raises:
    #         Exception: If lock acquisition fails
    #     """
    #     try:
    #         # Clean up any expired locks for this widget first
    #         await CoreWidgetLocking._cleanup_expired_locks(session, widget_id)

    #         # Check for existing active lock
    #         existing_lock = await CoreWidgetLocking.get_active_widget_lock(
    #             session, widget_id
    #         )
    #         if existing_lock and datetime.now(timezone.utc) < existing_lock.expires_at:
    #             raise ValueError(f"Widget is locked by {existing_lock.user_name}")

    #         # Get or create user session first
    #         user_session = await CoreWidgetLocking.get_or_create_user_session(
    #             session, dashboard_id, user_info
    #         )

    #         # Create new widget lock
    #         expires_at = datetime.now(timezone.utc) + timedelta(seconds=lock_duration)
    #         user_id = user_info["user_id"]
    #         user_id_uuid = user_id if isinstance(user_id, UUID) else UUID(user_id)
    #         widget_lock = WidgetLock(
    #             widget_id=widget_id,
    #             dashboard_id=dashboard_id,
    #             session_id=user_session.session_id,
    #             user_id=user_id_uuid,
    #             user_name=user_info.get("user_name", "Unknown"),
    #             locked_at=datetime.now(timezone.utc),
    #             expires_at=expires_at,
    #             last_heartbeat=datetime.now(timezone.utc),
    #             is_active=True,
    #         )

    #         session.add(widget_lock)
    #         await session.commit()

    #         # Update user session's locked widgets
    #         if widget_id not in user_session.locked_widgets:
    #             user_session.locked_widgets.append(widget_id)
    #             user_session.last_activity = datetime.now(timezone.utc)
    #             await session.flush()

    #         await session.refresh(widget_lock)
    #         return widget_lock

    #     except Exception as e:
    #         logger.error(f"Failed to acquire widget lock: {str(e)}")
    #         raise

    @staticmethod
    async def acquire_widget_lock(
        session: AsyncSession,
        dashboard_id: UUID,
        widget_id: UUID,
        user_info: dict,
        lock_duration: int = 60,
    ) -> WidgetLock:
        """
        Acquire a widget lock using Upsert logic to prevent Primary Key violations.
        """
        try:
            # 1. Check for an existing row for this widget (Active or Inactive)
            stmt = select(WidgetLock).where(WidgetLock.widget_id == widget_id)
            result = await session.execute(stmt)
            widget_lock = result.scalar_one_or_none()

            # 2. Validation: If an ACTIVE lock exists and belongs to someone else, block acquisition
            if widget_lock and widget_lock.is_active:
                # Check if it's actually expired but still marked active in DB
                if datetime.now(timezone.utc) < widget_lock.expires_at:
                    request_user_id = user_info["user_id"]
                    request_user_id = request_user_id if isinstance(request_user_id, UUID) else UUID(str(request_user_id))
                    
                    if widget_lock.user_id != request_user_id:
                        raise ValueError(f"Widget is currently locked by {widget_lock.user_name}")

            # 3. Get or create user session
            user_session = await CoreWidgetLocking.get_or_create_user_session(
                session, dashboard_id, user_info
            )

            # 4. Prepare data
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=lock_duration)
            user_id = user_info["user_id"]
            user_id_uuid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))

            if widget_lock:
                # UPSERT: Update the existing row instead of inserting
                widget_lock.dashboard_id = dashboard_id
                widget_lock.session_id = user_session.session_id
                widget_lock.user_id = user_id_uuid
                widget_lock.user_name = user_info.get("user_name", "Unknown")
                widget_lock.locked_at = now
                widget_lock.expires_at = expires_at
                widget_lock.last_heartbeat = now
                widget_lock.is_active = True
                logger.debug(f"Updated existing lock for widget {widget_id}")
            else:
                # INSERT: Create new row if it never existed
                widget_lock = WidgetLock(
                    widget_id=widget_id,
                    dashboard_id=dashboard_id,
                    session_id=user_session.session_id,
                    user_id=user_id_uuid,
                    user_name=user_info.get("user_name", "Unknown"),
                    locked_at=now,
                    expires_at=expires_at,
                    last_heartbeat=now,
                    is_active=True,
                )
                session.add(widget_lock)
                logger.debug(f"Created new lock for widget {widget_id}")

            # 5. Update user session's tracking list
            if widget_id not in user_session.locked_widgets:
                # Use a new list to trigger SQLAlchemy change detection
                user_session.locked_widgets = user_session.locked_widgets + [widget_id]
                user_session.last_activity = now

            await session.commit()
            await session.refresh(widget_lock)
            return widget_lock

        except Exception as e:
            logger.error(f"Failed to acquire widget lock: {str(e)}")
            await session.rollback()
            raise

    @staticmethod
    async def get_active_widget_lock(
        session: AsyncSession, widget_id: UUID
    ) -> Optional[WidgetLock]:
        """
        Get active lock for a widget.

        Args:
            session: Database session
            widget_id: Widget ID

        Returns:
            Active WidgetLock or None if no active lock
        """
        try:
            stmt = select(WidgetLock).where(
            (WidgetLock.widget_id == widget_id) & (WidgetLock.is_active == True)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to get active widget lock: {str(e)}")
            raise

    @staticmethod
    async def refresh_widget_lock(
        session: AsyncSession, widget_lock: WidgetLock, lock_duration: int = 60
    ) -> WidgetLock:
        """
        Refresh widget lock heartbeat and extend expiration.

        Args:
            session: Database session
            widget_lock: WidgetLock to refresh
            lock_duration: New lock duration in seconds

        Returns:
            Updated WidgetLock object

        Raises:
            Exception: If refresh fails
        """
        try:
            new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=lock_duration)

            stmt = (
                update(WidgetLock)
                .where(WidgetLock.widget_id == widget_lock.widget_id)
                .values(
                    expires_at=new_expires_at,
                    last_heartbeat=datetime.now(timezone.utc),
                )
            )
            await session.execute(stmt)
            await session.flush()

            # Refresh the object
            await session.refresh(widget_lock)
            return widget_lock

        except Exception as e:
            logger.error(f"Failed to refresh widget lock: {str(e)}")
            raise

    # @staticmethod
    # async def release_widget_lock(
    #     session: AsyncSession, dashboard_id: UUID, widget_id: UUID, user_info: dict
    # ) -> bool:
    #     """
    #     Release a widget lock.

    #     Args:
    #         session: Database session
    #         widget_id: Widget ID to release
    #         user_id: User ID attempting to release the lock

    #     Returns:
    #         True if lock was released, False if user doesn't own the lock

    #     Raises:
    #         Exception: If release operation fails
    #     """
    #     try:
    #         widget_lock = await CoreWidgetLocking.get_active_widget_lock(
    #             session, widget_id
    #         )

    #         if not widget_lock:
    #             return True  # No lock exists, consider it released

    #         user_id = user_info["user_id"]
    #         user_id_uuid = user_id if isinstance(user_id, UUID) else UUID(user_id)
    #         if widget_lock.user_id != user_id_uuid:
    #             return False  # User doesn't own the lock

    #         # Mark lock as inactive
    #         stmt = (
    #             update(WidgetLock)
    #             .where(WidgetLock.widget_id == widget_id)
    #             .values(is_active=False)
    #         )
    #         await session.execute(stmt)
    #         await session.flush()

    #         # Remove from user session's locked widgets
    #         user_session = await CoreWidgetLocking.get_user_session(
    #             session, widget_lock.session_id
    #         )
    #         if user_session:
    #             if widget_id in user_session.locked_widgets:
    #                 user_session.locked_widgets.remove(widget_id)
    #                 await session.flush()

    #         return True

    #     except Exception as e:
    #         logger.error(f"Failed to release widget lock: {str(e)}")
    #         raise

    @staticmethod
    async def release_widget_lock(
            session: AsyncSession, dashboard_id: UUID, widget_id: UUID, user_info: dict
        ) -> bool:
            """
            Release a widget lock.
            """
            try:
                # 1. Fetch the lock ensuring it belongs to the correct dashboard
                stmt = select(WidgetLock).where(
                    WidgetLock.widget_id == widget_id,
                    WidgetLock.dashboard_id == dashboard_id,
                    WidgetLock.is_active == True
                )
                result = await session.execute(stmt)
                widget_lock = result.scalar_one_or_none()

                if not widget_lock:
                    return True  # No active lock exists, consider it released

                # 2. Strict UUID conversion for comparison
                user_id_raw = user_info["user_id"]
                request_user_id = user_id_raw if isinstance(user_id_raw, UUID) else UUID(str(user_id_raw))
                
                # Ensure we compare UUID objects to UUID objects
                if widget_lock.user_id != request_user_id:
                    logger.warning(f"User {request_user_id} tried to release lock owned by {widget_lock.user_id}")
                    return False 

                # 3. Mark lock as inactive
                widget_lock.is_active = False
                
                # 4. Remove from user session's locked widgets list
                user_session = await CoreWidgetLocking.get_user_session(
                    session, widget_lock.session_id
                )
                if user_session and widget_id in user_session.locked_widgets:
                    # Use a new list to ensure SQLAlchemy detects the change in the ARRAY column
                    new_locked_widgets = [w for w in user_session.locked_widgets if w != widget_id]
                    user_session.locked_widgets = new_locked_widgets

                # 5. COMMIT the changes to the DB
                await session.commit()
                return True

            except Exception as e:
                logger.error(f"Failed to release widget lock: {str(e)}")
                await session.rollback()
                raise

    @staticmethod
    async def get_or_create_user_session(
        session: AsyncSession, dashboard_id: UUID, user_info: dict
    ) -> UserSession:
        """
        Get existing user session or create a new one.

        Args:
            session: Database session
            dashboard_id: Dashboard ID
            user_info: User information dict

        Returns:
            UserSession object

        Raises:
            Exception: If session creation fails
        """
        try:
            # Check for existing active session
            user_id = user_info["user_id"]
            user_id_uuid = user_id if isinstance(user_id, UUID) else UUID(user_id)
            stmt = select(UserSession).where(
                UserSession.dashboard_id == dashboard_id,
                UserSession.user_id == user_id_uuid,
                UserSession.is_active,
            )
            result = await session.execute(stmt)
            existing_session = result.scalar_one_or_none()

            if existing_session:
                # Update last activity
                existing_session.last_activity = datetime.now(timezone.utc)
                await session.flush()
                return existing_session

            # Create new session
            user_session = UserSession(
                session_id=uuid.uuid4(),
                dashboard_id=dashboard_id,
                user_id=user_id_uuid,
                user_name=user_info.get("user_name", "Unknown"),
                user_email=user_info.get("user_email"),
                client_info=user_info.get("client_info"),
                connected_at=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc),
                is_active=True,
                locked_widgets=[],
            )

            session.add(user_session)
            await session.commit()
            return user_session

        except Exception as e:
            logger.error(f"Failed to get/create user session: {str(e)}")
            raise

    @staticmethod
    async def get_user_session(
        session: AsyncSession, session_id: UUID
    ) -> Optional[UserSession]:
        """
        Get user session by session ID.

        Args:
            session: Database session
            session_id: Session ID

        Returns:
            UserSession or None if not found
        """
        try:
            stmt = select(UserSession).where(
                UserSession.session_id == session_id, UserSession.is_active
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to get user session: {str(e)}")
            return None

    @staticmethod
    async def get_active_sessions(
        session: AsyncSession, dashboard_id: UUID
    ) -> Tuple[List[UserSession], List[WidgetLock]]:
        """
        Get all active sessions and locks for a dashboard.

        Args:
            session: Database session
            dashboard_id: Dashboard ID

        Returns:
            Tuple of (active_sessions, active_locks)

        Raises:
            Exception: If query fails
        """
        try:
            # Get active sessions
            stmt_sessions = select(UserSession).where(
                UserSession.dashboard_id == dashboard_id,
                UserSession.is_active,
            )
            result_sessions = await session.execute(stmt_sessions)
            active_sessions = result_sessions.scalars().all()

            # Get active locks for this dashboard
            stmt_locks = select(WidgetLock).where(
                WidgetLock.dashboard_id == dashboard_id,
                WidgetLock.is_active,
            )
            result_locks = await session.execute(stmt_locks)
            active_locks = result_locks.scalars().all()

            return list(active_sessions), list(active_locks)

        except Exception as e:
            logger.error(f"Failed to get active sessions: {str(e)}")
            raise

    @staticmethod
    async def cleanup_stale_sessions_and_locks(
        session: AsyncSession, session_timeout_minutes: int = 5
    ) -> Tuple[int, int]:
        """
        Clean up stale sessions and expired locks.

        Args:
            session: Database session
            session_timeout_minutes: Session timeout in minutes (default: 5)

        Returns:
            Tuple of (expired_locks_count, stale_sessions_count)

        Raises:
            Exception: If cleanup fails
        """
        try:
            # Count expired locks first
            count_stmt = select(WidgetLock).where(
                WidgetLock.expires_at <= datetime.now(timezone.utc)
            )
            count_result = await session.execute(count_stmt)
            expired_locks_count = len(count_result.scalars().all())

            # Clean expired locks
            expired_locks_stmt = delete(WidgetLock).where(
                WidgetLock.expires_at <= datetime.now(timezone.utc)
            )
            await session.execute(expired_locks_stmt)

            # Clean stale sessions
            stale_time = datetime.now(timezone.utc) - timedelta(minutes=session_timeout_minutes)

            # Get stale sessions first to release their locks
            stale_sessions_stmt = select(UserSession).where(
                UserSession.last_activity <= stale_time,
                UserSession.is_active,
            )
            stale_sessions_result = await session.execute(stale_sessions_stmt)
            stale_sessions = stale_sessions_result.scalars().all()

            # Release locks for stale sessions
            for user_session in stale_sessions:
                # Remove all locks associated with this session
                release_locks_stmt = delete(WidgetLock).where(
                    WidgetLock.session_id == user_session.session_id
                )
                await session.execute(release_locks_stmt)

                # Mark session as inactive
                user_session.is_active = False

            await session.flush()

            stale_sessions_count = len(stale_sessions)
            await session.flush()

            # Cleanup completed silently
            return expired_locks_count, stale_sessions_count

        except Exception as e:
            logger.error(f"Failed to cleanup stale sessions: {str(e)}")
            await session.rollback()
            raise

    @staticmethod
    async def log_collaboration_event(
        session: AsyncSession,
        dashboard_id: UUID,
        user_info: dict,
        event_type: str,
        widget_id: Optional[UUID] = None,
        event_data: Optional[dict] = None,
    ) -> CollaborationEvent:
        """
        Log collaboration event for audit trail.

        Args:
            session: Database session
            dashboard_id: Dashboard ID
            user_info: User information
            event_type: Event type (lock_acquired, lock_released, etc.)
            widget_id: Widget ID (optional)
            event_data: Additional event data (optional)

        Returns:
            Created CollaborationEvent object

        Raises:
            Exception: If logging fails
        """
        try:
            user_id = user_info["user_id"]
            user_id_uuid = user_id if isinstance(user_id, UUID) else UUID(user_id)
            event = CollaborationEvent(
                event_id=uuid.uuid4(),
                dashboard_id=dashboard_id,
                widget_id=widget_id,
                user_id=user_id_uuid,
                user_name=user_info.get("user_name", "Unknown"),
                event_type=event_type,
                event_data=event_data,
                created_at=datetime.now(timezone.utc),
            )

            session.add(event)
            await session.flush()
            return event

        except Exception as e:
            logger.error(f"Failed to log collaboration event: {str(e)}")
            raise

    @staticmethod
    async def _cleanup_expired_locks(session: AsyncSession, widget_id: UUID) -> None:
        """
        Internal method to cleanup expired locks for a widget.

        Args:
            session: Database session
            widget_id: Widget ID
        """
        try:
            stmt = (
                delete(WidgetLock)
                .where(WidgetLock.widget_id == widget_id)
                .where(WidgetLock.expires_at <= datetime.now(timezone.utc))  
            )
            await session.execute(stmt)
            await session.flush() 

        except Exception as e:
            logger.error(f"Failed to cleanup expired locks: {str(e)}")
            raise
