"""
Background Session Cleanup Service for Widget Locking System.
Automatically cleans up stale sessions and expired locks on a schedule.
"""

from datetime import datetime, timedelta
from typing import Dict, Tuple

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.database import db_manager
from app.core.logging import logger
from app.services.widget_locking_service import get_widget_locking_service


class SessionCleanupService:
    """
    Background service for automatic cleanup of stale sessions and expired locks.
    Runs on a configurable schedule to maintain system performance.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.cleanup_interval = 30  # seconds
        self.session_timeout = timedelta(minutes=30)
        self.lock_expiration_threshold = timedelta(minutes=2)

    async def start_cleanup_service(self):
        """Start the background cleanup service."""
        if self.is_running:
            logger.warning("Cleanup service is already running")
            return

        try:
            # Schedule cleanup task to run every 30 seconds
            self.scheduler.add_job(
                self._cleanup_task,
                IntervalTrigger(seconds=self.cleanup_interval),
                id="session_cleanup",
                max_instances=1,
                misfire_grace_time=30,
                coalesce=True,
            )

            self.scheduler.start()
            self.is_running = True

            logger.info(
                f"Session cleanup service started (interval: {self.cleanup_interval}s)"
            )

        except Exception as e:
            logger.error(f"Failed to start cleanup service: {str(e)}")
            raise

    async def stop_cleanup_service(self):
        """Stop the background cleanup service."""
        if not self.is_running:
            logger.warning("Cleanup service is not running")
            return

        try:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Session cleanup service stopped")

        except Exception as e:
            logger.error(f"Failed to stop cleanup service: {str(e)}")
            raise

    async def _cleanup_task(self):
        """Background task to cleanup stale sessions and expired locks."""
        try:
            logger.debug("Starting background cleanup task...")

            # Get widget locking service
            locking_service = await get_widget_locking_service()

            # Run cleanup
            (
                expired_locks,
                stale_sessions,
            ) = await locking_service.cleanup_stale_sessions_and_locks()

            if expired_locks > 0 or stale_sessions > 0:
                logger.info(
                    f"Cleanup completed: {expired_locks} expired locks, {stale_sessions} stale sessions"
                )
            else:
                logger.debug("No stale sessions or expired locks found")

        except Exception as e:
            logger.error(f"Background cleanup task failed: {str(e)}")

    async def run_manual_cleanup(self) -> Tuple[int, int]:
        """
        Run manual cleanup operation.
        Useful for testing or immediate cleanup needs.

        Returns:
            Tuple of (expired_locks_count, stale_sessions_count)
        """
        try:
            logger.info("Running manual cleanup...")

            locking_service = await get_widget_locking_service()
            (
                expired_locks,
                stale_sessions,
            ) = await locking_service.cleanup_stale_sessions_and_locks()

            logger.info(
                f"Manual cleanup completed: {expired_locks} expired locks, {stale_sessions} stale sessions"
            )

            return expired_locks, stale_sessions

        except Exception as e:
            logger.error(f"Manual cleanup failed: {str(e)}")
            return 0, 0

    async def get_service_status(self) -> dict:
        """Get current status of the cleanup service."""
        return {
            "is_running": self.is_running,
            "cleanup_interval": self.cleanup_interval,
            "session_timeout": self.session_timeout.total_seconds(),
            "lock_expiration_threshold": self.lock_expiration_threshold.total_seconds(),
            "next_run_time": self._get_next_run_time(),
            "job_count": len(self.scheduler.get_jobs()) if self.scheduler else 0,
        }

    def _get_next_run_time(self) -> str:
        """Get next scheduled run time."""
        if not self.is_running or not self.scheduler:
            return "Not scheduled"

        jobs = self.scheduler.get_jobs()
        if jobs:
            next_run = jobs[0].next_run_time
            return next_run.isoformat() if next_run else "Not scheduled"

        return "Not scheduled"

    async def update_cleanup_interval(self, new_interval: int):
        """
        Update the cleanup interval dynamically.

        Args:
            new_interval: New interval in seconds (minimum: 10 seconds)
        """
        if new_interval < 10:
            raise ValueError("Cleanup interval must be at least 10 seconds")

        if self.is_running:
            await self.stop_cleanup_service()

        self.cleanup_interval = new_interval

        if self.is_running:
            await self.start_cleanup_service()

        logger.info(f"Cleanup interval updated to {new_interval} seconds")


# Global service instance
_cleanup_service = SessionCleanupService()


async def get_cleanup_service() -> SessionCleanupService:
    """Get the global cleanup service instance."""
    return _cleanup_service


async def start_background_cleanup() -> SessionCleanupService:
    """Start the background cleanup service."""
    await _cleanup_service.start_cleanup_service()
    return _cleanup_service


async def stop_background_cleanup():
    """Stop the background cleanup service."""
    await _cleanup_service.stop_cleanup_service()


async def run_manual_cleanup() -> Tuple[int, int]:
    """Run manual cleanup operation."""
    return await _cleanup_service.run_manual_cleanup()


async def get_cleanup_status() -> dict:
    """Get cleanup service status."""
    return await _cleanup_service.get_service_status()
