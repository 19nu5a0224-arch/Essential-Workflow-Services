"""
Core N8N operations module for Dashboard API.

Provides database operations for N8N workflows and executions.
All operations are designed to work within existing database transactions.
"""

import traceback
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.enums import EntityType
from app.core.logging import logger
from app.dbmodels.features_models import Share
from app.dbmodels.n8n_models import N8NWorkflow, N8NWorkflowExecution


class CoreN8NOperations:
    """Core operations for N8N workflows and executions."""

    @staticmethod
    async def get_user_workflows(
        session: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 50,
        include_executions: bool = False,
    ) -> List[N8NWorkflow]:
        """
        Get all N8N workflows that a user has permission to see.

        Args:
            session: Database session
            user_id: User ID to filter workflows by permission
            page: Page number for pagination
            page_size: Number of workflows per page
            include_executions: Whether to include execution history

        Returns:
            List of N8N workflows
        """
        try:
            # Calculate offset for pagination
            offset = (page - 1) * page_size

            # Build base query with permission checks
            query = (
                select(N8NWorkflow)
                .join(N8NWorkflow.dashboard)
                .outerjoin(
                    Share,
                    and_(
                        Share.dashboard_id == N8NWorkflow.dashboard_id,
                        Share.entity_type == EntityType.USER,
                        Share.entity_id == user_id,
                    ),
                )
                .where(
                    or_(
                        # User owns the dashboard
                        N8NWorkflow.dashboard.has(owner_id=user_id),
                        # Dashboard is shared with the user
                        Share.share_id.isnot(None),
                    )
                )
                .order_by(N8NWorkflow.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )

            if include_executions:
                query = query.options(
                    # Eager load executions if requested
                    joinedload(N8NWorkflow.executions)
                )

            result = await session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            logger.error("=" * 50 + " Error in get_user_workflows " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in get_user_workflows " + "=" * 50)
            raise

    @staticmethod
    async def get_user_workflows_count(session: AsyncSession, user_id: UUID) -> int:
        """
        Get total count of N8N workflows that a user has permission to see.

        Args:
            session: Database session
            user_id: User ID to filter workflows by permission

        Returns:
            Total count of workflows
        """
        try:
            query = (
                select(N8NWorkflow)
                .join(N8NWorkflow.dashboard)
                .outerjoin(
                    Share,
                    and_(
                        Share.dashboard_id == N8NWorkflow.dashboard_id,
                        Share.entity_type == EntityType.USER,
                        Share.entity_id == user_id,
                    ),
                )
                .where(
                    or_(
                        N8NWorkflow.dashboard.has(owner_id=user_id),
                        Share.share_id.isnot(None),
                    )
                )
            )

            result = await session.execute(query)
            return len(result.scalars().all())

        except Exception as e:
            logger.error("=" * 50 + " Error in get_user_workflows_count " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in get_user_workflows_count " + "=" * 50
            )
            raise

    @staticmethod
    async def get_workflow_by_id(
        session: AsyncSession, workflow_id: UUID, user_id: UUID
    ) -> Optional[N8NWorkflow]:
        """
        Get specific N8N workflow by ID if user has permission.

        Args:
            session: Database session
            workflow_id: Workflow ID to retrieve
            user_id: User ID to check permissions

        Returns:
            N8N workflow if found and user has permission, None otherwise
        """
        try:
            query = (
                select(N8NWorkflow)
                .join(N8NWorkflow.dashboard)
                .outerjoin(
                    Share,
                    and_(
                        Share.dashboard_id == N8NWorkflow.dashboard_id,
                        Share.entity_type == EntityType.USER,
                        Share.entity_id == user_id,
                    ),
                )
                .where(
                    and_(
                        N8NWorkflow.workflow_id == workflow_id,
                        or_(
                            N8NWorkflow.dashboard.has(owner_id=user_id),
                            Share.share_id.isnot(None),
                        ),
                    )
                )
                .options(
                    # Eager load executions and related entities
                    joinedload(N8NWorkflow.executions),
                    joinedload(N8NWorkflow.dashboard),
                    joinedload(N8NWorkflow.schedule),
                )
            )

            result = await session.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("=" * 50 + " Error in get_workflow_by_id " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in get_workflow_by_id " + "=" * 50)
            raise
