import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.logging import logger
from app.dbmodels.dashboard_models import Dashboard, DashboardVersion, VersionStatus
from app.dbmodels.features_models import Share
from app.schemas.dashboards_schema import (
    DashboardCreateSchema,
    DashboardUpdateContentSchema,
    DashboardUpdateDetailsSchema,
)


class DashboardNotFoundError(Exception):
    """Raised when a dashboard is not found."""

    pass


class DashboardDeletedError(Exception):
    """Raised when trying to access a deleted dashboard."""

    pass


class VersionNotFoundError(Exception):
    """Raised when a dashboard version is not found."""

    pass


class InvalidOperationError(Exception):
    """Raised when an invalid operation is attempted."""

    pass


class CoreDashboard:
    @staticmethod
    async def create_dashboard(
        session: AsyncSession, dashboard_data: DashboardCreateSchema, user_id: uuid.UUID
    ):
        try:
            # Ensure widget_ids exist for all widgets
            processed_content = []
            for widget in dashboard_data.content:
                # Create a copy of the widget to avoid modifying the original
                widget_copy = widget.copy()

                # Generate hex UUID if widget_id doesn't exist
                if "widget_id" not in widget_copy:
                    widget_copy["widget_id"] = uuid.uuid4().hex

                processed_content.append(widget_copy)

            new_dashboard = Dashboard(
                name=dashboard_data.name,
                description=dashboard_data.description,
                project_id=dashboard_data.project_id,
                workspace_id=dashboard_data.workspace_id,
                dashboard_metadata=dashboard_data.dashboard_metadata,
                owner_id=user_id,
                next_version_number=1,
            )
            session.add(new_dashboard)
            await session.flush()

            new_version = DashboardVersion(
                dashboard_id=new_dashboard.dashboard_id,
                version_number=1,
                status=VersionStatus.DRAFT,
                content=processed_content,  # Use processed content with widget_ids
                based_on_version_number=None,
                created_by=user_id,
                last_edited_by=user_id,
            )
            session.add(new_version)
            await session.flush()

            new_dashboard.current_draft_version_id = new_version.id
            new_dashboard.next_version_number = 2
            await session.flush()

            return new_dashboard

        except Exception as e:
            logger.error(f"Error creating dashboard: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    @staticmethod
    async def update_dashboard_details(
        session: AsyncSession,
        dashboard: Dashboard,
        update_data: DashboardUpdateDetailsSchema,
        user_id: uuid.UUID,
    ):
        try:
            if update_data.name is not None:
                dashboard.name = update_data.name
            if update_data.description is not None:
                dashboard.description = update_data.description
            if update_data.dashboard_metadata is not None:
                dashboard.dashboard_metadata = update_data.dashboard_metadata

            await session.flush()
            return dashboard

        except Exception as e:
            logger.error(f"Error updating dashboard details: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    @staticmethod
    async def create_or_update_draft(
        session: AsyncSession,
        content: DashboardUpdateContentSchema,
        create_new_draft: bool,
        dashboard: Dashboard,
        user_id: uuid.UUID,
    ):
        try:
            if create_new_draft:
                based_on_version_number = None
                if dashboard.current_published_version_id:
                    published_version = await session.get(
                        DashboardVersion, dashboard.current_published_version_id
                    )
                    if published_version:
                        based_on_version_number = published_version.version_number

                # Ensure widget_ids exist for all widgets
                processed_content = []
                for widget in content.content:
                    # Create a copy of the widget to avoid modifying the original
                    widget_copy = widget.copy()

                    # Generate hex UUID if widget_id doesn't exist
                    if "widget_id" not in widget_copy:
                        widget_copy["widget_id"] = uuid.uuid4().hex

                    processed_content.append(widget_copy)

                new_version = DashboardVersion(
                    dashboard_id=dashboard.dashboard_id,
                    version_number=dashboard.next_version_number,
                    status=VersionStatus.DRAFT,
                    content=processed_content,  # Use processed content with widget_ids
                    based_on_version_number=based_on_version_number,
                    created_by=user_id,
                    last_edited_by=user_id,
                )
                session.add(new_version)
                await session.flush()

                dashboard.current_draft_version_id = new_version.id
                dashboard.next_version_number += 1
                await session.flush()

                return new_version
            else:
                # For updating existing draft, ensure widget_ids exist for all widgets
                processed_content = []
                for widget in content.content:
                    # Create a copy of the widget to avoid modifying the original
                    widget_copy = widget.copy()

                    # Generate hex UUID if widget_id doesn't exist
                    if "widget_id" not in widget_copy:
                        widget_copy["widget_id"] = uuid.uuid4().hex

                    processed_content.append(widget_copy)

                stmt = (
                    update(DashboardVersion)
                    .where(DashboardVersion.id == dashboard.current_draft_version_id)
                    .values(
                        content=processed_content,  # Use processed content with widget_ids
                        last_edited_by=user_id,
                    )
                )
                await session.execute(stmt)
                await session.flush()

                draft_version = await session.get(
                    DashboardVersion, dashboard.current_draft_version_id
                )
                return draft_version

        except Exception as e:
            logger.error(f"Error creating or updating draft: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    @staticmethod
    async def publish_dashboard(
        session: AsyncSession,
        dashboard: Dashboard,
        draft_version: DashboardVersion,
        user_id: uuid.UUID,
    ):
        try:
            if dashboard.current_published_version_id:
                current_published = await session.get(
                    DashboardVersion, dashboard.current_published_version_id
                )
                if current_published:
                    current_published.status = VersionStatus.ARCHIVED
                    current_published.archived_at = datetime.now(timezone.utc)
                    current_published.archived_by = user_id
                    await session.flush()

            draft_version.status = VersionStatus.PUBLISHED
            draft_version.published_at = datetime.now(timezone.utc)
            draft_version.published_by = user_id

            dashboard.current_published_version_id = draft_version.id
            dashboard.current_draft_version_id = None

            await session.flush()
            return draft_version

        except Exception as e:
            logger.error(f"Error publishing dashboard: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    @staticmethod
    async def delete_dashboard_or_draft(
        session: AsyncSession,
        dashboard: Dashboard,
        draft_version_id: Optional[uuid.UUID] = None,
    ):
        """
        Delete either the entire dashboard with all versions or just a draft version.

        Args:
            session: Database session
            dashboard: Dashboard object
            draft_version_id: If provided, only delete this specific draft version.
                             If None, delete the entire dashboard.

        Returns:
            Deleted dashboard (if full deletion) or updated dashboard (if draft deletion)
        """
        try:
            if draft_version_id:
                # Delete only the specified draft version
                draft_version = await session.get(DashboardVersion, draft_version_id)
                if not draft_version:
                    raise VersionNotFoundError(
                        f"Draft version with id {draft_version_id} not found"
                    )

                if draft_version.dashboard_id != dashboard.dashboard_id:
                    raise InvalidOperationError(
                        "Draft version does not belong to this dashboard"
                    )

                if draft_version.status != VersionStatus.DRAFT:
                    raise InvalidOperationError("Can only delete draft versions")

                # Archive the draft version
                draft_version.status = VersionStatus.ARCHIVED
                draft_version.archived_at = datetime.now(timezone.utc)
                draft_version.archived_by = (
                    dashboard.owner_id
                )  # Use dashboard owner as archive user
                await session.flush()

                # Remove the draft reference from dashboard if this was the current draft
                if dashboard.current_draft_version_id == draft_version_id:
                    dashboard.current_draft_version_id = None
                    await session.flush()

                return dashboard
            else:
                # Delete the entire dashboard with all versions
                dashboard.deleted_at = datetime.now(timezone.utc)
                await session.flush()
                return dashboard

        except Exception as e:
            logger.error(f"Error deleting dashboard or draft: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    @staticmethod
    async def get_all_dashboards(
        session: AsyncSession, user_info: Any, page: int = 1, page_size: int = 50
    ) -> dict:
        """
        Get all dashboards accessible to user, categorized by ownership and sharing.

        Args:
            session: Database session
            user_info: User information object with teams, projects, workspaces attributes
            page: Page number for pagination (1-indexed)
            page_size: Number of dashboards per page

        Returns:
            dict: Categorized dashboards with the following structure:
                {
                    "my_dashboards": List[dict],     # Dashboards owned by user
                    "shared_with_me": List[dict],     # Dashboards shared to user
                    "shared_by_me": List[dict],       # Dashboards shared by user
                    "pagination": {
                        "page": int,
                        "page_size": int,
                        "total": int,
                        "has_next": bool
                    }
                }
        """

        try:
            user_id = user_info.get("id") or user_info.get("user_id")

            # Get user's teams, projects, workspaces
            user_teams = user_info.get("teams", [])
            user_projects = user_info.get("projects", [])
            user_workspaces = user_info.get("workspaces", [])

            team_ids = [
                uuid.UUID(str(team.get("id"))) for team in user_teams if team.get("id")
            ]
            project_ids = [
                uuid.UUID(str(project.get("id")))
                for project in user_projects
                if project.get("id")
            ]
            workspace_ids = [
                uuid.UUID(str(workspace.get("id")))
                for workspace in user_workspaces
                if workspace.get("id")
            ]

            # Query 1: Get all dashboards owned by user with shares eager loading
            owned_dashboards_stmt = (
                select(Dashboard)
                .options(joinedload(Dashboard.shares))
                .where(
                    and_(
                        Dashboard.owner_id == user_id,
                        Dashboard.deleted_at.is_(None),
                    )
                )
            )
            owned_dashboards_result = await session.execute(owned_dashboards_stmt)
            owned_dashboards = owned_dashboards_result.scalars().unique().all()

            # Query 2: Get dashboards shared with user via share table
            # Get all entity IDs that can have access to this user
            user_entities = [user_id]
            if team_ids:
                user_entities.extend(team_ids)
            if project_ids:
                user_entities.extend(project_ids)
            if workspace_ids:
                user_entities.extend(workspace_ids)

            # Apply pagination limits
            offset = (page - 1) * page_size
            limit = page_size

            shared_dashboards_stmt = (
                select(Dashboard)
                .options(joinedload(Dashboard.shares))
                .join(Share)
                .where(
                    and_(
                        Share.entity_id.in_(user_entities),
                        Dashboard.deleted_at.is_(None),
                        Dashboard.owner_id != user_id,  # Exclude user's own dashboards
                    )
                )
                .offset(offset)
                .limit(limit)
            )
            shared_dashboards_result = await session.execute(shared_dashboards_stmt)
            shared_dashboards = shared_dashboards_result.scalars().unique().all()

            # Count total for pagination
            count_stmt = (
                select(func.count(Dashboard.dashboard_id))
                .join(Share)
                .where(
                    and_(
                        Share.entity_id.in_(user_entities),
                        Dashboard.deleted_at.is_(None),
                        Dashboard.owner_id != user_id,
                    )
                )
            )
            count_result = await session.execute(count_stmt)
            total_shared = count_result.scalar() or 0

            # Transform dashboard objects to response format
            def transform_dashboard(dashboard: Dashboard) -> dict:
                return {
                    "dashboard_id": dashboard.dashboard_id,
                    "name": dashboard.name,
                    "description": dashboard.description,
                    "current_published_version_id": dashboard.current_published_version_id,
                    "current_draft_version_id": dashboard.current_draft_version_id,
                    "owner_id": dashboard.owner_id,
                    "project_id": dashboard.project_id,
                    "workspace_id": dashboard.workspace_id,
                    "created_at": dashboard.created_at,
                    "updated_at": dashboard.updated_at,
                    "dashboard_metadata": dashboard.dashboard_metadata,
                    "has_draft": dashboard.has_draft,
                    "has_published": dashboard.has_published,
                    "current_status": dashboard.current_status,
                }

            # Categorize owned dashboards programmatically
            my_dashboards_list = []
            shared_by_me_list = []

            # Apply pagination to owned dashboards
            owned_dashboards_paginated = owned_dashboards[offset : offset + limit]

            for dashboard in owned_dashboards_paginated:
                dashboard_dict = transform_dashboard(dashboard)
                has_shares = bool(dashboard.shares)  # Use eager loaded shares

                if has_shares:  # Has shares = shared_by_me
                    shared_by_me_list.append(dashboard_dict)
                else:  # No shares = my_dashboards (private)
                    my_dashboards_list.append(dashboard_dict)

            # Count total owned dashboards for pagination
            total_owned = len(owned_dashboards)

            # Transform shared dashboards
            shared_with_me_list = [transform_dashboard(d) for d in shared_dashboards]

            # Calculate pagination info
            total_results = (
                len(my_dashboards_list)
                + len(shared_with_me_list)
                + len(shared_by_me_list)
            )
            total_pages_owned = (
                (total_owned + page_size - 1) // page_size if total_owned > 0 else 1
            )
            total_pages_shared = (
                (total_shared + page_size - 1) // page_size if total_shared > 0 else 1
            )
            has_next = (page < total_pages_owned) or (page < total_pages_shared)

            return {
                "my_dashboards": my_dashboards_list,
                "shared_with_me": shared_with_me_list,
                "shared_by_me": shared_by_me_list,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_owned": total_owned,
                    "total_shared": total_shared,
                    "total_results": total_results,
                    "has_next": has_next,
                },
            }

        except Exception as e:
            logger.error(f"Error fetching all dashboards: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    @staticmethod
    async def get_dashboard_by_id(
        session: AsyncSession,
        dashboard_id: uuid.UUID,
        version_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """
        Get dashboard details by ID including content from the appropriate version.

        Args:
            session: Database session
            dashboard_id: Dashboard ID to fetch
            version_id: Optional version ID to get specific version content

        Returns:
            dict: Dashboard details with content from published or draft version
        """
        try:
            # Get dashboard with eager loading of both versions using joinedload
            stmt = (
                select(Dashboard)
                .options(
                    joinedload(Dashboard.published_version),
                    joinedload(Dashboard.draft_version),
                )
                .where(
                    and_(
                        Dashboard.dashboard_id == dashboard_id,
                        Dashboard.deleted_at.is_(None),
                    )
                )
            )
            dashboard = await session.scalar(stmt)

            if not dashboard:
                raise DashboardNotFoundError(
                    f"Dashboard with id {dashboard_id} not found"
                )

            # Determine which version to get content from
            version = None
            if version_id:
                # If specific version_id is provided, check loaded versions first
                if (
                    dashboard.published_version
                    and dashboard.published_version.id == version_id
                ):
                    version = dashboard.published_version
                elif (
                    dashboard.draft_version and dashboard.draft_version.id == version_id
                ):
                    version = dashboard.draft_version
                else:
                    # Fallback to database query if version not in loaded versions
                    version_stmt = select(DashboardVersion).where(
                        and_(
                            DashboardVersion.id == version_id,
                            DashboardVersion.dashboard_id == dashboard_id,
                        )
                    )
                    version = await session.scalar(version_stmt)
                    if not version:
                        raise VersionNotFoundError(
                            f"Version {version_id} not found for dashboard {dashboard_id}"
                        )
            elif dashboard.current_published_version_id and dashboard.published_version:
                version = dashboard.published_version
            elif dashboard.current_draft_version_id and dashboard.draft_version:
                version = dashboard.draft_version
            else:
                raise InvalidOperationError(
                    f"Dashboard with id {dashboard_id} has no versions"
                )

            if not version:
                raise VersionNotFoundError(
                    f"Version not found for dashboard {dashboard_id}"
                )

            # Build response structure
            response = {
                "dashboard_id": dashboard.dashboard_id,
                "name": dashboard.name,
                "description": dashboard.description,
                "owner_id": dashboard.owner_id,
                "project_id": dashboard.project_id,
                "workspace_id": dashboard.workspace_id,
                "current_published_version_id": dashboard.current_published_version_id,
                "current_draft_version_id": dashboard.current_draft_version_id,
                "version_id": version.id,
                "version_number": version.version_number,
                "version_status": version.status.value,
                "content": version.content,
                "created_at": dashboard.created_at,
                "updated_at": dashboard.updated_at,
                "dashboard_metadata": dashboard.dashboard_metadata,
                "version_created_at": version.created_at,
                "version_updated_at": version.updated_at,
                "created_by": version.created_by,
                "last_edited_by": version.last_edited_by,
            }

            # Add published info if available
            if version.published_at:
                response["published_at"] = version.published_at
                response["published_by"] = version.published_by

            return response

        except Exception as e:
            logger.error(f"Error fetching dashboard by id: {str(e)}")
            logger.error(traceback.format_exc())
            raise
