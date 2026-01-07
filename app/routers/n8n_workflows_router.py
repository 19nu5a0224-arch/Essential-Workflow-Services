"""
N8N Workflows Router APIs for Dashboard API.

Provides endpoints for managing and retrieving N8N workflows with proper authentication.
Users can only access workflows for dashboards they have permission to see.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.services.n8n_operations_service import N8NOperationsService

router = APIRouter(prefix="/n8n-workflows", tags=["n8n-workflows"])

n8n_operations_service = N8NOperationsService()


@router.get("/")
async def get_user_workflows(
    page: int = Query(1, description="Page number for pagination", ge=1),
    page_size: int = Query(
        50, description="Number of workflows per page", ge=1, le=100
    ),
    include_executions: bool = Query(
        False, description="Whether to include execution history"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Get all N8N workflows that the current user has permission to see.

    Returns workflows associated with dashboards that the user owns or has been shared with.

    Args:
        page: Page number for pagination (default: 1)
        page_size: Number of workflows per page (default: 50, max: 100)
        include_executions: Whether to include execution history (default: False)

    Returns:
        Paginated list of N8N workflows with optional execution history
    """
    try:
        result = await n8n_operations_service.get_user_workflows(
            user_info=current_user,
            page=page,
            page_size=page_size,
            include_executions=include_executions,
        )
        return result

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching workflows",
        )


@router.get("/{workflow_id}")
async def get_workflow_by_id(
    workflow_id: str,
    include_executions: bool = Query(
        True, description="Whether to include execution history"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Get specific N8N workflow by ID if user has permission.

    Args:
        workflow_id: UUID of the workflow to retrieve
        include_executions: Whether to include execution history (default: True)

    Returns:
        N8N workflow details with optional execution history
    """
    try:
        result = await n8n_operations_service.get_workflow_by_id(
            user_info=current_user,
            workflow_id=workflow_id,
            include_executions=include_executions,
        )
        return result

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching workflow",
        )
