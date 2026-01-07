"""
Authentication dependencies for FastAPI application.

This module provides robust, production-ready authentication with proper separation of concerns.
Designed with senior-level software engineering principles: separation of concerns, defensive programming,
and consistent error handling.
"""

import logging
from typing import Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.permission_service import PermissionService
from app.utils.cache import get_cache

logger = logging.getLogger(__name__)

# Create HTTPBearer instance for extracting Bearer tokens
security = HTTPBearer()

# Cache configuration
USER_INFO_CACHE_PREFIX = "user_info_"
USER_INFO_CACHE_TTL = 300  # 5 minutes


class AuthenticationService:
    """Service class handling authentication business logic with proper separation of concerns."""

    @staticmethod
    def _validate_credentials(credentials: HTTPAuthorizationCredentials) -> str:
        """
        Validate credentials and extract token with defensive programming.

        Args:
            credentials: HTTPAuthorizationCredentials from FastAPI's HTTPBearer

        Returns:
            str: Validated token string

        Raises:
            HTTPException: If credentials are missing or invalid
        """
        if not credentials:
            logger.warning("Missing authentication credentials")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = credentials.credentials

        if not token or not isinstance(token, str) or len(token.strip()) == 0:
            logger.warning("Invalid authentication token format")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return token.strip()

    @staticmethod
    def _generate_cache_key(token: str) -> str:
        """Generate consistent cache key for token-based lookup."""
        return f"{USER_INFO_CACHE_PREFIX}{token}"

    @staticmethod
    def _transform_user_info_to_dict(user_info, token: str) -> Dict:
        """
        Transform UserInfo object to consistent dictionary format.
        This ensures a stable interface for downstream consumers.
        """
        if not user_info or not user_info.user:
            raise ValueError("Invalid UserInfo object provided")

        return {
            # Core identification
            "id": user_info.user_id,  # Primary identifier for compatibility
            "user_id": user_info.user_id,  # Original user_id field
            "token": token,  # Original token for traceability
            # User metadata
            "is_superuser": user_info.is_superuser,
            "username": AuthenticationService._extract_username(user_info.user),
            # Access control data
            "workspaces": user_info.workspaces or [],
            "projects": user_info.projects or [],
            "teams": user_info.teams or [],
            "permissions": user_info.permissions or [],
            "roles": user_info.roles or [],
            # Raw user data for flexibility
            "user": user_info.user,
        }

    @staticmethod
    def _extract_username(user_data: Dict) -> str:
        """
        Extract username from user data with clear fallback logic.
        Single responsibility: username generation only.
        """
        if not user_data:
            return "User"

        first_name = user_data.get("first_name", "").strip()
        last_name = user_data.get("last_name", "").strip()

        # Prioritize combined name, then individual names, then fallback
        if first_name and last_name:
            return f"{first_name} {last_name}"
        elif first_name:
            return first_name
        elif last_name:
            return last_name
        else:
            return "User"

    @staticmethod
    async def _fetch_fresh_user_data(token: str) -> Dict:
        """
        Fetch fresh user data from external service with proper error handling.
        This is the only place that calls the external authentication service.
        """
        try:
            user_info = await PermissionService._fetch_user_info(token)

            if not user_info or not user_info.is_valid:
                logger.warning(f"Invalid user info returned for token: {token[:10]}...")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return AuthenticationService._transform_user_info_to_dict(user_info, token)

        except HTTPException:
            # Re-raise authentication errors
            raise
        except Exception as e:
            # Log and transform unexpected errors
            logger.error(f"Unexpected error during authentication: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable",
            ) from e

    @staticmethod
    async def authenticate_user(token: str) -> Dict:
        """
        Main authentication workflow with proper separation of concerns.

        Flow: Validate → Check Cache → Fetch Fresh → Cache → Return
        """
        # Step 1: Generate cache key
        cache_key = AuthenticationService._generate_cache_key(token)
        cache_manager = await get_cache()

        # Step 2: Check cache first (fast path)
        cached_data = await cache_manager.get_shared(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for token: {token[:10]}...")
            return cached_data

        # Step 3: Cache miss - fetch fresh data
        logger.debug(f"Cache miss for token: {token[:10]}..., fetching fresh data")
        user_dict = await AuthenticationService._fetch_fresh_user_data(token)

        # Step 4: Cache the result for future requests
        try:
            await cache_manager.set_shared(
                cache_key, user_dict, ttl=USER_INFO_CACHE_TTL
            )
            logger.debug(f"Cached user data for: {user_dict['user_id']}")
        except Exception as e:
            # Cache failures shouldn't break authentication
            logger.warning(f"Failed to cache user data: {str(e)}")

        return user_dict


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict:
    """
    FastAPI dependency for user authentication.

    This is the public interface - simple, focused, and robust.
    """
    try:
        # Step 1: Validate input
        token = AuthenticationService._validate_credentials(credentials)

        # Step 2: Perform authentication
        user_data = await AuthenticationService.authenticate_user(token)

        logger.debug(f"User authenticated successfully: {user_data['user_id']}")
        return user_data

    except HTTPException:
        # Re-raise authentication errors
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Critical authentication failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal authentication error",
        )


async def get_current_user_id(current_user: Dict = Depends(get_current_user)) -> str:
    """
    Convenience dependency for extracting user ID.

    Simple, focused, and consistent with the main dependency.
    """
    return current_user["user_id"]


async def get_current_user_workspaces(
    current_user: Dict = Depends(get_current_user),
) -> list:
    """
    Convenience dependency for extracting user workspaces.

    Useful for route-level workspace filtering.
    """
    return current_user.get("workspaces", [])


async def get_current_user_permissions(
    current_user: Dict = Depends(get_current_user),
) -> list:
    """
    Convenience dependency for extracting user permissions.

    Useful for fine-grained permission checks.
    """
    return current_user.get("permissions", [])
