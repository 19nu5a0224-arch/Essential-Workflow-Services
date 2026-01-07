"""
Comment Service Module - Business logic for comment operations following DashboardService pattern.
"""

import traceback
import uuid
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.auth.dependencies import get_current_user
from app.codebase.comments import (
    CommentNotFoundError,
    CommentPermissionError,
    CoreComments,
)
from app.core.database import db_manager
from app.core.logging import logger
from app.schemas.comments_schema import (
    CommentAction,
    CommentCreateRequest,
    CommentOperationResponse,
    CommentResponse,
    CommentTreeResponse,
    CommentType,
    CommentUpdateRequest,
)
from app.utils.cache import cached_comments, get_cache


class CommentService:
    """Service for handling comment operations with permission checks and caching."""

    @staticmethod
    async def create_comment(
        entity_type: str,
        entity_id: UUID,
        comment_type: CommentType,
        content: str,
        user_id: UUID,
        parent_comment_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Create a new comment or reply.

        Args:
            entity_type: Entity type (dashboard, workflow, report)
            entity_id: Entity ID
            comment_type: Comment type (create or reply)
            content: Comment content
            user_id: User ID
            parent_comment_id: Parent comment ID for replies

        Returns:
            Result from CoreComments.create_comment()
        """
        # Validate comment type and parent relationship
        if comment_type == CommentType.REPLY and not parent_comment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reply comment must have parent_comment_id",
            )

        if comment_type == CommentType.CREATE and parent_comment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Root comment cannot have parent_comment_id",
            )

        try:
            async with db_manager.session() as session:
                result = await CoreComments.create_comment(
                    session=session,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    content=content,
                    user_id=user_id,
                    parent_comment_id=parent_comment_id,
                )

                # Invalidate cache for this entity's comments using tags
                cache_manager = await get_cache()
                await cache_manager.delete_multi_level_by_tags(
                    f"resource:comments",
                    f"entity:{entity_type}:{entity_id}",
                    f"collection:comments:{entity_type}:{entity_id}",
                )

                return result

        except ValueError as e:
            logger.error(f"Validation error creating comment: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            logger.error("=" * 50 + " Error in create_comment " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in create_comment " + "=" * 50)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create comment",
            )

    @staticmethod
    @cached_comments(ttl=2)  # Cache comments for 2 seconds
    async def get_hierarchical_comments(
        entity_type: str,
        entity_id: str,
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        max_reply_depth: int = 3,
    ) -> Dict[str, Any]:
        """
        Get hierarchical comment tree with caching.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            user_id: Optional user ID for like status
            limit: Number of root comments per page
            offset: Pagination offset
            max_reply_depth: Maximum reply depth

        Returns:
            Hierarchical comment tree data
        """
        try:
            # Convert user_id to UUID if provided
            uuid_user_id = None
            if user_id:
                uuid_user_id = UUID(user_id)

            uuid_entity_id = UUID(entity_id)

            async with db_manager.session() as session:
                result = await CoreComments.get_comments_tree(
                    session=session,
                    entity_type=entity_type,
                    entity_id=uuid_entity_id,
                    user_id=uuid_user_id,
                    limit=limit,
                    offset=offset,
                    max_reply_depth=max_reply_depth,
                )

                return result

        except Exception as e:
            logger.error("=" * 50 + " Error in get_hierarchical_comments " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error(
                "=" * 50 + " Error ended in get_hierarchical_comments " + "=" * 50
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get comments",
            )

    @staticmethod
    async def update_comment(
        comment_id: UUID,
        content: str,
        user_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Update comment content.

        Args:
            comment_id: Comment ID to update
            content: New content
            user_id: User ID for permission check

        Returns:
            Updated comment data
        """
        try:
            async with db_manager.session() as session:
                result = await CoreComments.update_comment(
                    session=session,
                    comment_id=comment_id,
                    content=content,
                    user_id=user_id,
                )

                # Invalidate cache for this comment and its entity using pattern matching
                if result:
                    cache_manager = await get_cache()
                    await cache_manager.delete_multi_level_by_tags(
                        f"resource:comments",
                        f"entity:comment:{comment_id}",
                        f"entity:{result['entity_type']}:{result['entity_id']}",
                        f"collection:comments:{result['entity_type']}:{result['entity_id']}",
                    )

                return result

        except CommentNotFoundError:
            logger.warning(f"Comment {comment_id} not found for update")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        except CommentPermissionError:
            logger.warning(
                f"User {user_id} does not have permission to update comment {comment_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this comment",
            )
        except Exception as e:
            logger.error("=" * 50 + " Error in update_comment " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in update_comment " + "=" * 50)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update comment",
            )

    @staticmethod
    async def delete_comment(
        comment_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Delete a comment.

        Args:
            comment_id: Comment ID to delete
            user_id: User ID for permission check

        Returns:
            Success status
        """
        try:
            async with db_manager.session() as session:
                # Get comment first to know which entity cache to invalidate
                comment_data = await CoreComments.get_comment_by_id(session, comment_id)

                success = await CoreComments.delete_comment(
                    session=session,
                    comment_id=comment_id,
                    user_id=user_id,
                )

                # Invalidate cache for this comment and its entity using pattern matching
                if success and comment_data:
                    cache_manager = await get_cache()
                    await cache_manager.delete_multi_level_by_tags(
                        f"resource:comments",
                        f"entity:comment:{comment_id}",
                        f"entity:{comment_data['entity_type']}:{comment_data['entity_id']}",
                        f"collection:comments:{comment_data['entity_type']}:{comment_data['entity_id']}",
                    )

                return success

        except CommentNotFoundError:
            logger.warning(f"Comment {comment_id} not found for deletion")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        except CommentPermissionError:
            logger.warning(
                f"User {user_id} does not have permission to delete comment {comment_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this comment",
            )
        except Exception as e:
            logger.error("=" * 50 + " Error in delete_comment " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in delete_comment " + "=" * 50)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete comment",
            )

    @staticmethod
    async def toggle_comment_like(
        comment_id: UUID,
        user_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Toggle like status for a comment.

        Args:
            comment_id: Comment ID to like/unlike
            user_id: User ID

        Returns:
            Updated comment data
        """
        try:
            async with db_manager.session() as session:
                result = await CoreComments.toggle_like(
                    session=session,
                    comment_id=comment_id,
                    user_id=user_id,
                )

                # Invalidate cache for this comment and its entity using pattern matching
                if result:
                    cache_manager = await get_cache()
                    await cache_manager.delete_multi_level_by_tags(
                        f"resource:comments",
                        f"entity:comment:{comment_id}",
                        f"entity:{result['entity_type']}:{result['entity_id']}",
                        f"collection:comments:{result['entity_type']}:{result['entity_id']}",
                    )

                return result

        except CommentNotFoundError:
            logger.warning(f"Comment {comment_id} not found for like toggle")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        except Exception as e:
            logger.error("=" * 50 + " Error in toggle_comment_like " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in toggle_comment_like " + "=" * 50)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to toggle like",
            )

    @staticmethod
    @cached_comments(ttl=2)  # Cache comment for 2 seconds
    async def get_comment_by_id(
        comment_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific comment by ID with caching.

        Args:
            comment_id: Comment ID
            user_id: Optional user ID for like status

        Returns:
            Comment data or None if not found
        """
        try:
            async with db_manager.session() as session:
                return await CoreComments.get_comment_by_id(
                    session=session,
                    comment_id=comment_id,
                    user_id=user_id,
                )

        except Exception as e:
            logger.error("=" * 50 + " Error in get_comment_by_id " + "=" * 50)
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=" * 50 + " Error ended in get_comment_by_id " + "=" * 50)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get comment",
            )
