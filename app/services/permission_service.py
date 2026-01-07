"""
Permission Service for Dashboard Access Control
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select

from app.core.database import db_manager
from app.core.enums import EntityType
from app.core.logging import logger
from app.dbmodels.dashboard_models import Dashboard
from app.dbmodels.features_models import Share
from app.utils.cache import get_cache

# Cache configuration
CACHE_TTL = 300  # 5 minutes
AUTH_API_BASE = "https://eanalyticsapi.phenomecloud.com/api/v1"


class UserInfo:
    """User information model."""

    def __init__(self, user_data: Dict[str, Any], system_info: Dict[str, Any]):
        self.is_valid: bool = user_data.get("is_valid", False)
        self.user: Dict[str, Any] = user_data.get("user", {})
        self.system_info: Dict[str, Any] = system_info
        self.cached_at: datetime = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert UserInfo to dictionary for JSON serialization."""
        return {
            "is_valid": self.is_valid,
            "user": self.user,
            "system_info": self.system_info,
            "cached_at": self.cached_at.isoformat(),
            "user_id": self.user_id,
            "is_superuser": self.is_superuser,
            "workspaces": self.workspaces,
            "projects": self.projects,
            "teams": self.teams,
            "permissions": self.permissions,
            "roles": self.roles,
        }

    @property
    def user_id(self) -> Optional[str]:
        return str(self.user.get("id")) if self.user and self.user.get("id") else None

    @property
    def is_superuser(self) -> bool:
        return self.user.get("is_superuser", False) if self.user else False

    @property
    def workspaces(self) -> List[Dict[str, Any]]:
        return self.system_info.get("workspaces", [])

    @property
    def projects(self) -> List[Dict[str, Any]]:
        return self.system_info.get("projects", [])

    @property
    def teams(self) -> List[Dict[str, Any]]:
        return self.system_info.get("teams", [])

    @property
    def permissions(self) -> List[str]:
        return self.system_info.get("authenticated_user_permissions", [])

    @property
    def roles(self) -> List[str]:
        return self.system_info.get("roles", []) + self.user.get("roles", [])

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        if self.is_superuser:
            return True
        return permission in self.permissions or "*" in self.permissions

    def has_access_to_workspace(self, workspace_id: str) -> bool:
        """Check if user has access to a specific workspace."""
        if self.is_superuser:
            return True
        return any(str(ws.get("id")) == workspace_id for ws in self.workspaces)

    def has_access_to_project(self, project_id: str) -> bool:
        """Check if user has access to a specific project."""
        if self.is_superuser:
            return True
        return any(str(proj.get("id")) == project_id for proj in self.projects)

    def belongs_to_team(self, team_id: str) -> bool:
        """Check if user belongs to a specific team."""
        if self.is_superuser:
            return True
        return any(str(team.get("id")) == team_id for team in self.teams)


class PermissionService:
    """Service for handling dashboard permissions and access control."""

    # Permission hierarchy definitions
    READ_PERMISSIONS = {"read"}
    WRITE_PERMISSIONS = {"read", "write"}
    ADMIN_PERMISSIONS = {"read", "write", "admin"}

    @staticmethod
    async def check_create_dashboard(
        user_info: Any,
        project_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> bool:
        """
        Check if user has ability to create dashboard.

        Args:
            user_info: User information object with projects and workspaces attributes
            project_id: Project ID to check access for
            workspace_id: Workspace ID to check access for

        Returns:
            bool: True if user can create dashboard, False otherwise
        """
        # Check if project_id or workspace_id is in user_info
        if project_id:
            # Check if project_id exists in user_info.projects
            user_projects = (
                user_info.get("projects", [])
                if isinstance(user_info, dict)
                else getattr(user_info, "projects", [])
            )
            if isinstance(user_projects, list):
                for project in user_projects:
                    if str(project.get("id", "")) == str(project_id):
                        return True

        if workspace_id:
            # Check if workspace_id exists in user_info.workspaces
            user_workspaces = (
                user_info.get("workspaces", [])
                if isinstance(user_info, dict)
                else getattr(user_info, "workspaces", [])
            )
            if isinstance(user_workspaces, list):
                for workspace in user_workspaces:
                    if str(workspace.get("id", "")) == str(workspace_id):
                        return True

        # If neither project_id nor workspace_id is in user_info, return False
        return project_id is None and workspace_id is None

    @staticmethod
    async def check_user_permission(
        user_info: Any,
        dashboard_id: uuid.UUID,
        user_id: uuid.UUID,
        required_permission: str,
    ) -> bool:
        """
        Check user permission by verifying ownership or share table access.

        Args:
            user_info: User information object
            dashboard_id: Dashboard identifier
            user_id: User identifier
            required_permission: Required permission level ('read', 'write', 'admin')

        Returns:
            bool: True if user has required permission, False otherwise
        """
        # First check if user is owner of dashboard
        is_owner = await PermissionService._is_dashboard_owner(dashboard_id, user_id)
        if is_owner:
            return True

        # Check share table with specified conditions
        user_permission = await PermissionService._get_user_permission_from_share(
            user_info, dashboard_id, user_id
        )

        if not user_permission:
            return False

        # Compare permissions according to rules
        return PermissionService._has_sufficient_permission(
            user_permission, required_permission
        )

    @staticmethod
    async def _is_dashboard_owner(dashboard_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """
        Check if user is the owner of the dashboard.

        Args:
            dashboard_id: Dashboard identifier
            user_id: User identifier

        Returns:
            bool: True if user is owner, False otherwise
        """
        try:
            async with db_manager.session() as session:
                stmt = select(Dashboard).where(Dashboard.dashboard_id == dashboard_id)
                result = await session.execute(stmt)
                dashboard = result.scalar_one_or_none()

                if dashboard and str(dashboard.owner_id) == str(user_id):
                    return True
                return False
        except Exception:
            # In case of any database error, assume user is not owner
            return False

    @staticmethod
    async def _get_user_permission_from_share(
        user_info: Any, dashboard_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[str]:
        """
        Get user permission from share table based on specified conditions.

        Args:
            user_info: User information object with teams, projects, workspaces
            dashboard_id: Dashboard identifier
            user_id: User identifier

        Returns:
            str or None: Permission level if found, None otherwise
        """
        try:
            async with db_manager.session() as session:
                # Check direct user share
                stmt = select(Share).where(
                    Share.dashboard_id == dashboard_id,
                    Share.entity_type == EntityType.USER,
                    Share.entity_id == uuid.UUID(str(user_id)),
                )
                result = await session.execute(stmt)
                share = result.scalar_one_or_none()
                if share:
                    return share.permission.value

                # Check team shares
                user_teams = (
                    user_info.get("teams", [])
                    if isinstance(user_info, dict)
                    else getattr(user_info, "teams", [])
                )
                if isinstance(user_teams, list):
                    team_ids = [
                        str(team.get("id")) for team in user_teams if team.get("id")
                    ]
                    if team_ids:
                        stmt = select(Share).where(
                            Share.dashboard_id == dashboard_id,
                            Share.entity_type == EntityType.TEAM,
                            Share.entity_id.in_(
                                [uuid.UUID(team_id) for team_id in team_ids]
                            ),
                        )
                        result = await session.execute(stmt)
                        share = result.scalar_one_or_none()
                        if share:
                            return share.permission.value

                # Check project shares
                user_projects = (
                    user_info.get("projects", [])
                    if isinstance(user_info, dict)
                    else getattr(user_info, "projects", [])
                )
                if isinstance(user_projects, list):
                    project_ids = [
                        str(project.get("id"))
                        for project in user_projects
                        if project.get("id")
                    ]
                    if project_ids:
                        stmt = select(Share).where(
                            Share.dashboard_id == dashboard_id,
                            Share.entity_type == EntityType.PROJECT,
                            Share.entity_id.in_(
                                [uuid.UUID(project_id) for project_id in project_ids]
                            ),
                        )
                        result = await session.execute(stmt)
                        share = result.scalar_one_or_none()
                        if share:
                            return share.permission.value

                # Check workspace shares
                user_workspaces = (
                    user_info.get("workspaces", [])
                    if isinstance(user_info, dict)
                    else getattr(user_info, "workspaces", [])
                )
                if isinstance(user_workspaces, list):
                    workspace_ids = [
                        str(workspace.get("id"))
                        for workspace in user_workspaces
                        if workspace.get("id")
                    ]
                    if workspace_ids:
                        stmt = select(Share).where(
                            Share.dashboard_id == dashboard_id,
                            Share.entity_type == EntityType.WORKSPACE,
                            Share.entity_id.in_(
                                [
                                    uuid.UUID(workspace_id)
                                    for workspace_id in workspace_ids
                                ]
                            ),
                        )
                        result = await session.execute(stmt)
                        share = result.scalar_one_or_none()
                        if share:
                            return share.permission.value

                return None
        except Exception:
            # In case of any database error, return None
            return None

    @staticmethod
    def _has_sufficient_permission(
        user_permission: str, required_permission: str
    ) -> bool:
        """
        Check if user has sufficient permission for the required action.

        Args:
            user_permission: User's actual permission level
            required_permission: Required permission level

        Returns:
            bool: True if user has sufficient permission, False otherwise
        """
        # Permission weight system - higher permissions include lower ones
        PERMISSION_WEIGHTS = {"read": 1, "write": 2, "admin": 3}

        user_weight = PERMISSION_WEIGHTS.get(user_permission, 0)
        required_weight = PERMISSION_WEIGHTS.get(required_permission, 0)
        return user_weight >= required_weight

    @staticmethod
    async def _fetch_user_info(token: str) -> Optional[UserInfo]:
        """Fetch user info from external APIs with caching."""
        cache_key = f"user_info:{token}"
        cache = await get_cache()

        # Try to get from cache first
        cached_user_info = await cache.get_shared(cache_key)
        if cached_user_info:
            logger.debug("Cache hit for user info")
            return cached_user_info

        logger.debug("Cache miss for user info, fetching from API")
        client = httpx.AsyncClient(timeout=30.0)
        try:
            # Validate session
            auth_response = await client.post(
                f"{AUTH_API_BASE}/auth/validate-session",
                params={"token": token},
                headers={"Authorization": f"Bearer {token}"},
            )
            auth_response.raise_for_status()
            user_data = auth_response.json()

            if not user_data.get("is_valid"):
                logger.warning("Invalid session token")
                return None

            # Get system info
            system_response = await client.get(
                f"{AUTH_API_BASE}/users/system-info",
                headers={"Authorization": f"Bearer {token}"},
            )
            system_response.raise_for_status()
            system_info = system_response.json()

            user_info = UserInfo(user_data, system_info)

            # Cache the serialized data
            await cache.set_shared(cache_key, user_info.to_dict(), ttl=CACHE_TTL)
            logger.debug("User info cached successfully")

            return user_info

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error while fetching user info: {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error while fetching user info: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while fetching user info: {e}")
            return None
        finally:
            await client.aclose()
