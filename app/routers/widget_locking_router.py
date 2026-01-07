"""
Widget Locking API Router for concurrent editing collaboration.
True async implementation optimized for high-frequency polling.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.dependencies import get_current_user
from app.schemas.widget_locking_schemas import (
    ActiveSessionsResponse,
    CleanupResponse,
    DashboardEditingSessionSchema,
    HeartbeatResponse,
    LockAcquisitionResponse,
    UserSessionSchema,
    WidgetLockAcquireSchema,
    WidgetLockHeartbeatSchema,
    WidgetLockReleaseSchema,
    WidgetLockSchema,
    WidgetLockStatusResponse,
)
from app.services.widget_locking_service import (
    WidgetLockingService,
    get_widget_locking_service,
)

router = APIRouter(prefix="/collaboration", tags=["widget-locking"])


@router.post(
    "/dashboards/{dashboard_id}/widgets/lock",
    response_model=LockAcquisitionResponse,
    status_code=status.HTTP_200_OK,
)
async def acquire_widget_lock(
    dashboard_id: str,
    lock_data: WidgetLockAcquireSchema,
    request: Request,
    current_user: dict = Depends(get_current_user),
    locking_service: WidgetLockingService = Depends(get_widget_locking_service),
):
    """
    Acquire a lock on a widget for concurrent editing.

    Args:
        dashboard_id: Dashboard ID
        lock_data: Widget lock acquisition data
        current_user: Authenticated user

    Returns:
        Lock acquisition result with session ID and expiration
    """
    try:
        # Validate dashboard ID
        try:
            dashboard_uuid = uuid.UUID(dashboard_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

        # Add client info to user info
        user_info = {
            "user_id": current_user["user_id"],
            "user_name": current_user.get("username", "Unknown"),
            "user_email": current_user.get("email"),
            "client_info": {
                "user_agent": request.headers.get("user-agent", "Unknown"),
                "ip_address": request.client.host if request.client else "Unknown",
            },
        }

        result = await locking_service.acquire_widget_lock(
            dashboard_id=dashboard_uuid,
            widget_id=lock_data.widget_id,
            user_info=user_info,
            lock_duration=lock_data.lock_duration,
        )

        if not result.success:
            raise HTTPException(status_code=409, detail=result.message)

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to acquire widget lock: {str(e)}"
        )


@router.post(
    "/dashboards/{dashboard_id}/widgets/heartbeat",
    response_model=HeartbeatResponse,
    status_code=status.HTTP_200_OK,
)
async def refresh_widget_lock(
    dashboard_id: str,
    heartbeat_data: WidgetLockHeartbeatSchema,
    current_user: dict = Depends(get_current_user),
    locking_service: WidgetLockingService = Depends(get_widget_locking_service),
):
    """
    Refresh widget lock heartbeat to extend expiration.
    Should be called every 10 seconds by the frontend.

    Args:
        dashboard_id: Dashboard ID
        heartbeat_data: Widget heartbeat data
        current_user: Authenticated user

    Returns:
        Heartbeat refresh result with new expiration
    """
    try:
        # Validate dashboard ID
        try:
            dashboard_uuid = uuid.UUID(dashboard_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

        user_info = {
            "user_id": current_user["user_id"],
            "user_name": current_user.get("username", "Unknown"),
        }

        result = await locking_service.refresh_widget_lock(
            dashboard_id=dashboard_uuid,
            widget_id=heartbeat_data.widget_id,
            user_info=user_info,
        )

        if not result.success:
            raise HTTPException(status_code=404, detail=result.message)

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh widget lock: {str(e)}"
        )


@router.delete(
    "/dashboards/{dashboard_id}/widgets/lock",
    status_code=status.HTTP_200_OK,
)
async def release_widget_lock(
    dashboard_id: str,
    release_data: WidgetLockReleaseSchema,
    current_user: dict = Depends(get_current_user),
    locking_service: WidgetLockingService = Depends(get_widget_locking_service),
):
    """
    Release a widget lock explicitly.

    Args:
        dashboard_id: Dashboard ID
        release_data: Widget lock release data
        current_user: Authenticated user

    Returns:
        Success status
    """
    try:
        # Validate dashboard ID
        try:
            dashboard_uuid = uuid.UUID(dashboard_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

        user_info = {
            "user_id": current_user["user_id"],
            "user_name": current_user.get("username", "Unknown"),
        }

        success = await locking_service.release_widget_lock(
            dashboard_id=dashboard_uuid,
            widget_id=release_data.widget_id,
            user_info=user_info,
        )

        if not success:
            raise HTTPException(
                status_code=403, detail="You don't own this widget lock"
            )

        return {"success": True, "message": "Widget lock released successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to release widget lock: {str(e)}"
        )


@router.get(
    "/dashboards/{dashboard_id}/widgets/{widget_id}/status",
    response_model=WidgetLockStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_widget_lock_status(
    dashboard_id: str,
    widget_id: str,
    current_user: dict = Depends(get_current_user),
    locking_service: WidgetLockingService = Depends(get_widget_locking_service),
):
    """
    Get current lock status for a widget.
    Optimized for frequent polling (every 2-3 seconds).

    Args:
        dashboard_id: Dashboard ID
        widget_id: Widget ID
        current_user: Authenticated user

    Returns:
        Widget lock status information
    """
    try:
        # Validate IDs
        try:
            dashboard_uuid = uuid.UUID(dashboard_id)
            widget_uuid = uuid.UUID(widget_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid dashboard or widget ID format"
            )

        result = await locking_service.get_widget_lock_status(
            widget_id=widget_uuid,
            current_user_id=current_user["user_id"],
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get widget lock status: {str(e)}"
        )


@router.get(
    "/dashboards/{dashboard_id}/active-sessions",
    response_model=ActiveSessionsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_active_sessions(
    dashboard_id: str,
    current_user: dict = Depends(get_current_user),
    locking_service: WidgetLockingService = Depends(get_widget_locking_service),
):
    """
    Get all active editing sessions for a dashboard.
    Shows who is currently editing and which widgets are locked.

    Args:
        dashboard_id: Dashboard ID
        current_user: Authenticated user

    Returns:
        Active sessions and widget locks information
    """
    try:
        # Validate dashboard ID
        try:
            dashboard_uuid = uuid.UUID(dashboard_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

        sessions, locks = await locking_service.get_active_sessions(
            dashboard_id=dashboard_uuid
        )

        # Convert to schemas
        session_schemas = [
            UserSessionSchema(
                session_id=sess.session_id,
                dashboard_id=sess.dashboard_id,
                user_id=sess.user_id,
                user_name=sess.user_name,
                user_email=sess.user_email,
                client_info=sess.client_info,
                connected_at=sess.connected_at,
                last_activity=sess.last_activity,
                locked_widgets=sess.locked_widgets,
            )
            for sess in sessions
        ]

        lock_schemas = [
            WidgetLockSchema(
                widget_id=lock.widget_id,
                dashboard_id=lock.dashboard_id,
                session_id=lock.session_id,
                user_id=lock.user_id,
                user_name=lock.user_name,
                locked_at=lock.locked_at,
                expires_at=lock.expires_at,
                last_heartbeat=lock.last_heartbeat,
                time_remaining=lock.time_remaining,
            )
            for lock in locks
        ]

        return ActiveSessionsResponse(
            dashboard_id=dashboard_uuid,
            active_sessions=session_schemas,
            total_sessions=len(sessions),
            widget_locks=lock_schemas,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get active sessions: {str(e)}"
        )


@router.post(
    "/dashboards/{dashboard_id}/edit/start",
    status_code=status.HTTP_200_OK,
)
async def start_dashboard_editing(
    dashboard_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    locking_service: WidgetLockingService = Depends(get_widget_locking_service),
):
    """
    Start dashboard editing session when user opens dashboard in edit mode.

    Args:
        dashboard_id: Dashboard ID
        current_user: Authenticated user
        request: HTTP request for client info

    Returns:
        Editing session information
    """
    try:
        # Validate dashboard ID
        try:
            dashboard_uuid = uuid.UUID(dashboard_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

        # Add client info to user info
        user_info = {
            "user_id": current_user["user_id"],
            "user_name": current_user.get("username", "Unknown"),
            "user_email": current_user.get("email"),
            "client_info": {
                "user_agent": request.headers.get("user-agent", "Unknown"),
                "ip_address": request.client.host if request.client else "Unknown",
            },
        }

        session = await locking_service.start_dashboard_editing(
            dashboard_id=dashboard_uuid,
            user_info=user_info,
        )

        return DashboardEditingSessionSchema(
            session_id=session.session_id,
            dashboard_id=session.dashboard_id,
            user_id=session.user_id,
            user_name=session.user_name,
            connected_at=session.connected_at,
            message="Dashboard editing session started successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start dashboard editing: {str(e)}"
        )


@router.post(
    "/dashboards/{dashboard_id}/edit/stop",
    status_code=status.HTTP_200_OK,
)
async def stop_dashboard_editing(
    dashboard_id: str,
    current_user: dict = Depends(get_current_user),
    locking_service: WidgetLockingService = Depends(get_widget_locking_service),
):
    """
    Stop dashboard editing session when user leaves edit mode.

    Args:
        dashboard_id: Dashboard ID
        current_user: Authenticated user

    Returns:
        Success status
    """
    try:
        # Validate dashboard ID
        try:
            dashboard_uuid = uuid.UUID(dashboard_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

        success = await locking_service.stop_dashboard_editing(
            dashboard_id=dashboard_uuid,
            user_id=current_user["user_id"],
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="No active editing session found"
            )

        return {
            "success": True,
            "message": "Dashboard editing session stopped successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to stop dashboard editing: {str(e)}"
        )


@router.post(
    "/dashboards/{dashboard_id}/edit/heartbeat",
    status_code=status.HTTP_200_OK,
)
async def refresh_dashboard_editing(
    dashboard_id: str,
    current_user: dict = Depends(get_current_user),
    locking_service: WidgetLockingService = Depends(get_widget_locking_service),
):
    """
    Refresh dashboard editing session heartbeat.
    Should be called periodically while user is editing the dashboard.

    Args:
        dashboard_id: Dashboard ID
        current_user: Authenticated user

    Returns:
        Success status
    """
    try:
        # Validate dashboard ID
        try:
            dashboard_uuid = uuid.UUID(dashboard_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dashboard ID format")

        success = await locking_service.refresh_dashboard_editing(
            dashboard_id=dashboard_uuid,
            user_id=current_user["user_id"],
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="No active editing session found"
            )

        return {
            "success": True,
            "message": "Dashboard editing session refreshed successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh dashboard editing: {str(e)}"
        )


@router.post(
    "/cleanup/stale-sessions",
    response_model=CleanupResponse,
    status_code=status.HTTP_200_OK,
)
async def cleanup_stale_sessions(
    current_user: dict = Depends(get_current_user),
    locking_service: WidgetLockingService = Depends(get_widget_locking_service),
):
    """
    Clean up stale sessions and expired locks.
    This endpoint can be called manually or scheduled as a background task.

    Args:
        current_user: Authenticated user (admin only in production)

    Returns:
        Cleanup results
    """
    try:
        # In production, add admin check here
        # if not current_user.get("is_admin"):
        #     raise HTTPException(status_code=403, detail="Admin access required")

        (
            expired_locks,
            stale_sessions,
        ) = await locking_service.cleanup_stale_sessions_and_locks()

        return CleanupResponse(
            cleaned_sessions=stale_sessions,
            cleaned_locks=expired_locks,
            message=f"Cleaned up {stale_sessions} stale sessions and {expired_locks} expired locks",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to cleanup stale sessions: {str(e)}"
        )


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check(
    locking_service: WidgetLockingService = Depends(get_widget_locking_service),
):
    """
    Health check for widget locking service.
    """
    try:
        await locking_service.initialize()
        return {
            "status": "healthy",
            "service": "widget_locking",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")
