"""
N8N Operations Service Layer

Handles N8N workflow operations with permission checks and proper error handling.
Follows the flow: API -> Service Layer -> Permission Layer -> Codebase -> Database
"""

import traceback
import uuid
from typing import Any

from fastapi import HTTPException, status

from app.codebase.n8n_operations import CoreN8NOperations
from app.core.database import db_manager
from app.core.logging import logger
from app.schemas.n8n_schema import (
    N8NWorkflowExecutionResponse,
    N8NWorkflowResponse,
    N8NWorkflowsResponse,
    N8NWorkflowsWithExecutionsResponse,
    N8NWorkflowWithExecutionsResponse,
)
from app.utils.cache import cached_n8n_workflows


class N8NOperationsService:
    """Service layer for N8N workflow operations."""

    @staticmethod
    @cached_n8n_workflows(ttl=60)  # Cache user workflows for 60 seconds
    async def get_user_workflows(
        user_info: Any,
        page: int = 1,
        page_size: int = 50,
        include_executions: bool = False,
    ) -> Any:
        """
        Get all N8N workflows that a user has permission to see.

        Args:
            user_info: User information object
            page: Page number for pagination (default: 1)
            page_size: Number of workflows per page (default: 50)
            include_executions: Whether to include execution history (default: False)

        Returns:
            N8NWorkflowsResponse or N8NWorkflowsWithExecutionsResponse
        """
        try:
            # Validate pagination parameters
            if page < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Page must be greater than 0",
                )
            if page_size < 1 or page_size > 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Page size must be between 1 and 100",
                )

            async with db_manager.session() as session:
                # Get workflows from database
                workflows = await CoreN8NOperations.get_user_workflows(
                    session=session,
                    user_id=user_info["id"],
                    page=page,
                    page_size=page_size,
                    include_executions=include_executions,
                )

                # Get total count for pagination
                total_count = await CoreN8NOperations.get_user_workflows_count(
                    session=session, user_id=user_info["id"]
                )

                # Convert to response format
                if include_executions:
                    workflows_data = [
                        N8NWorkflowWithExecutionsResponse(
                            workflow_id=workflow.workflow_id,
                            dashboard_id=workflow.dashboard_id,
                            schedule_id=workflow.schedule_id,
                            n8n_workflow_id=workflow.n8n_workflow_id,
                            n8n_tag_name=workflow.n8n_tag_name,
                            workflow_name=workflow.workflow_name,
                            workflow_data=workflow.workflow_data,
                            status=workflow.status,
                            last_activated_at=workflow.last_activated_at,
                            last_deactivated_at=workflow.last_deactivated_at,
                            last_error=workflow.last_error,
                            error_count=workflow.error_count,
                            created_at=workflow.created_at,
                            updated_at=workflow.updated_at,
                            executions=[
                                N8NWorkflowExecutionResponse(
                                    execution_id=execution.execution_id,
                                    workflow_id=execution.workflow_id,
                                    execution_status=execution.execution_status,
                                    started_at=execution.started_at,
                                    completed_at=execution.completed_at,
                                    duration_ms=execution.duration_ms,
                                    success_count=execution.success_count,
                                    error_count=execution.error_count,
                                    error_message=execution.error_message,
                                    n8n_execution_id=execution.n8n_execution_id,
                                    created_at=execution.created_at,
                                )
                                for execution in workflow.executions
                            ],
                        )
                        for workflow in workflows
                    ]
                    return N8NWorkflowsWithExecutionsResponse(
                        workflows=workflows_data,
                        total_count=total_count,
                        page=page,
                        page_size=page_size,
                    )
                else:
                    workflows_data = [
                        N8NWorkflowResponse(
                            workflow_id=workflow.workflow_id,
                            dashboard_id=workflow.dashboard_id,
                            schedule_id=workflow.schedule_id,
                            n8n_workflow_id=workflow.n8n_workflow_id,
                            n8n_tag_name=workflow.n8n_tag_name,
                            workflow_name=workflow.workflow_name,
                            workflow_data=workflow.workflow_data,
                            status=workflow.status,
                            last_activated_at=workflow.last_activated_at,
                            last_deactivated_at=workflow.last_deactivated_at,
                            last_error=workflow.last_error,
                            error_count=workflow.error_count,
                            created_at=workflow.created_at,
                            updated_at=workflow.updated_at,
                        )
                        for workflow in workflows
                    ]
                    return N8NWorkflowsResponse(
                        workflows=workflows_data,
                        total_count=total_count,
                        page=page,
                        page_size=page_size,
                    )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("=" * 50 + " Error in get_user_workflows " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in get_user_workflows " + "=" * 50)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while fetching workflows",
            )

    @staticmethod
    @cached_n8n_workflows(ttl=60)  # Cache workflow by ID for 60 seconds
    async def get_workflow_by_id(
        user_info: Any, workflow_id: str, include_executions: bool = True
    ) -> Any:
        """
        Get specific N8N workflow by ID if user has permission.

        Args:
            user_info: User information object
            workflow_id: Workflow ID to retrieve
            include_executions: Whether to include execution history (default: True)

        Returns:
            N8NWorkflowResponse or N8NWorkflowWithExecutionsResponse
        """
        try:
            # Validate workflow ID format
            try:
                workflow_uuid = uuid.UUID(workflow_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid workflow ID format",
                )

            async with db_manager.session() as session:
                # Get workflow from database with permission check
                workflow = await CoreN8NOperations.get_workflow_by_id(
                    session=session,
                    workflow_id=workflow_uuid,
                    user_id=user_info["id"],
                )

                if not workflow:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Workflow not found or you don't have permission to access it",
                    )

                # Convert to response format
                if include_executions:
                    return N8NWorkflowWithExecutionsResponse(
                        workflow_id=workflow.workflow_id,
                        dashboard_id=workflow.dashboard_id,
                        schedule_id=workflow.schedule_id,
                        n8n_workflow_id=workflow.n8n_workflow_id,
                        n8n_tag_name=workflow.n8n_tag_name,
                        workflow_name=workflow.workflow_name,
                        workflow_data=workflow.workflow_data,
                        status=workflow.status,
                        last_activated_at=workflow.last_activated_at,
                        last_deactivated_at=workflow.last_deactivated_at,
                        last_error=workflow.last_error,
                        error_count=workflow.error_count,
                        created_at=workflow.created_at,
                        updated_at=workflow.updated_at,
                        executions=[
                            N8NWorkflowExecutionResponse(
                                execution_id=execution.execution_id,
                                workflow_id=execution.workflow_id,
                                execution_status=execution.execution_status,
                                started_at=execution.started_at,
                                completed_at=execution.completed_at,
                                duration_ms=execution.duration_ms,
                                success_count=execution.success_count,
                                error_count=execution.error_count,
                                error_message=execution.error_message,
                                n8n_execution_id=execution.n8n_execution_id,
                                created_at=execution.created_at,
                            )
                            for execution in workflow.executions
                        ],
                    )
                else:
                    return N8NWorkflowResponse(
                        workflow_id=workflow.workflow_id,
                        dashboard_id=workflow.dashboard_id,
                        schedule_id=workflow.schedule_id,
                        n8n_workflow_id=workflow.n8n_workflow_id,
                        n8n_tag_name=workflow.n8n_tag_name,
                        workflow_name=workflow.workflow_name,
                        workflow_data=workflow.workflow_data,
                        status=workflow.status,
                        last_activated_at=workflow.last_activated_at,
                        last_deactivated_at=workflow.last_deactivated_at,
                        last_error=workflow.last_error,
                        error_count=workflow.error_count,
                        created_at=workflow.created_at,
                        updated_at=workflow.updated_at,
                    )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("=" * 50 + " Error in get_workflow_by_id " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in get_workflow_by_id " + "=" * 50)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while fetching workflow",
            )
