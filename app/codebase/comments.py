"""
Core Comments Module - Database operations for comments following CoreDashboard pattern.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.dbmodels.comment_models import Comment, CommentLike


class CommentNotFoundError(Exception):
    """Raised when comment is not found."""


class CommentPermissionError(Exception):
    """Raised when user doesn't have permission to perform action."""


class CoreComments:
    """Core comment operations following CoreDashboard pattern."""

    @staticmethod
    async def create_comment(
        session: AsyncSession,
        entity_type: str,
        entity_id: UUID,
        content: str,
        user_id: UUID,
        parent_comment_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Create a new comment or reply.

        Args:
            session: Database session
            entity_type: Entity type (dashboard, workflow, report)
            entity_id: Entity ID
            content: Comment content
            user_id: User ID
            parent_comment_id: Optional parent comment ID for replies

        Returns:
            Dictionary with comment data
        """
        try:
            # Validate entity type
            valid_entity_types = ["dashboard", "workflow", "report"]
            if entity_type not in valid_entity_types:
                raise ValueError(
                    f"Invalid entity type. Must be one of: {valid_entity_types}"
                )

            comment = Comment(
                id=uuid.uuid4(),
                entity_type=entity_type,
                entity_id=entity_id,
                content=content,
                user_id=user_id,
                parent_comment_id=parent_comment_id,
            )

            session.add(comment)
            await session.flush()
            await session.refresh(comment)

            # If this is a reply, increment parent's reply count
            if parent_comment_id:
                await session.execute(
                    update(Comment)
                    .where(Comment.id == parent_comment_id)
                    .values(reply_count=Comment.reply_count + 1)
                )

            # Convert to response format
            response = {
                "id": comment.id,
                "entity_type": comment.entity_type,
                "entity_id": comment.entity_id,
                "content": comment.content,
                "user_id": comment.user_id,
                "parent_comment_id": comment.parent_comment_id,
                "like_count": comment.like_count,
                "reply_count": comment.reply_count,
                "is_edited": comment.is_edited,
                "is_deleted": comment.is_deleted,
                "is_pinned": comment.is_pinned,
                "created_at": comment.created_at,
                "updated_at": comment.updated_at,
                "edited_at": comment.edited_at,
                "username": "User",  # Will be populated by service layer
                "has_liked": False,
                "replies": [],
            }

            await session.commit()
            return response

        except SQLAlchemyError as e:
            logger.error(f"Database error creating comment: {e}")
            await session.rollback()
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating comment: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def update_comment(
        session: AsyncSession,
        comment_id: UUID,
        content: str,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Update comment content.

        Args:
            session: Database session
            comment_id: Comment ID to update
            content: New content
            user_id: User ID for permission check

        Returns:
            Updated comment data
        """
        try:
            # Get comment
            query = select(Comment).where(Comment.id == comment_id)
            result = await session.execute(query)
            comment = result.scalar_one_or_none()

            if not comment:
                raise CommentNotFoundError("Comment not found")

            if comment.user_id != user_id:
                raise CommentPermissionError(
                    "User does not have permission to update this comment"
                )

            # Update comment
            await session.execute(
                update(Comment)
                .where(Comment.id == comment_id)
                .values(content=content, is_edited=True, edited_at=datetime.now())
            )

            await session.flush()
            await session.refresh(comment)

            # Convert to response format
            response = {
                "id": comment.id,
                "entity_type": comment.entity_type,
                "entity_id": comment.entity_id,
                "content": comment.content,
                "user_id": comment.user_id,
                "parent_comment_id": comment.parent_comment_id,
                "like_count": comment.like_count,
                "reply_count": comment.reply_count,
                "is_edited": comment.is_edited,
                "is_deleted": comment.is_deleted,
                "is_pinned": comment.is_pinned,
                "created_at": comment.created_at,
                "updated_at": comment.updated_at,
                "edited_at": comment.edited_at,
                "username": "User",  # Will be populated by service layer
                "has_liked": False,
                "replies": [],
            }

            await session.commit()
            return response

        except SQLAlchemyError as e:
            logger.error(f"Database error updating comment: {e}")
            await session.rollback()
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating comment: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def delete_comment(
        session: AsyncSession,
        comment_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Soft delete a comment.

        Args:
            session: Database session
            comment_id: Comment ID to delete
            user_id: User ID for permission check

        Returns:
            Success status
        """
        try:
            # Get comment
            query = select(Comment).where(Comment.id == comment_id)
            result = await session.execute(query)
            comment = result.scalar_one_or_none()

            if not comment:
                raise CommentNotFoundError("Comment not found")

            if comment.user_id != user_id:
                raise CommentPermissionError(
                    "User does not have permission to delete this comment"
                )

            # Soft delete
            await session.execute(
                update(Comment).where(Comment.id == comment_id).values(is_deleted=True)
            )

            # If this is a reply, decrement parent's reply count
            if comment.parent_comment_id is not None:
                await session.execute(
                    update(Comment)
                    .where(Comment.id == comment.parent_comment_id)
                    .values(reply_count=Comment.reply_count - 1)
                )

            await session.commit()
            return True

        except SQLAlchemyError as e:
            logger.error(f"Database error deleting comment: {e}")
            await session.rollback()
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting comment: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def toggle_like(
        session: AsyncSession,
        comment_id: UUID,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Toggle like status for a comment.

        Args:
            session: Database session
            comment_id: Comment ID to like/unlike
            user_id: User ID

        Returns:
            Updated comment data
        """
        try:
            # Check if like exists
            like_query = select(CommentLike).where(
                and_(
                    CommentLike.comment_id == comment_id,
                    CommentLike.user_id == user_id,
                )
            )
            like_result = await session.execute(like_query)
            existing_like = like_result.scalar_one_or_none()

            # Get comment
            comment_query = select(Comment).where(Comment.id == comment_id)
            comment_result = await session.execute(comment_query)
            comment = comment_result.scalar_one_or_none()

            if not comment:
                raise CommentNotFoundError("Comment not found")

            if existing_like is not None:
                # Unlike
                await session.delete(existing_like)
                await session.execute(
                    update(Comment)
                    .where(Comment.id == comment_id)
                    .values(like_count=Comment.like_count - 1)
                )
                has_liked = False
            else:
                # Like
                new_like = CommentLike(comment_id=comment_id, user_id=user_id)
                session.add(new_like)
                await session.execute(
                    update(Comment)
                    .where(Comment.id == comment_id)
                    .values(like_count=Comment.like_count + 1)
                )
                has_liked = True

            await session.flush()
            await session.refresh(comment)

            # Convert to response format
            response = {
                "id": comment.id,
                "entity_type": comment.entity_type,
                "entity_id": comment.entity_id,
                "content": comment.content,
                "user_id": comment.user_id,
                "parent_comment_id": comment.parent_comment_id,
                "like_count": comment.like_count,
                "reply_count": comment.reply_count,
                "is_edited": comment.is_edited,
                "is_deleted": comment.is_deleted,
                "is_pinned": comment.is_pinned,
                "created_at": comment.created_at,
                "updated_at": comment.updated_at,
                "edited_at": comment.edited_at,
                "username": "User",  # Will be populated by service layer
                "has_liked": has_liked,
                "replies": [],
            }

            await session.commit()
            return response

        except SQLAlchemyError as e:
            logger.error(f"Database error toggling like: {e}")
            await session.rollback()
            raise
        except Exception as e:
            logger.error(f"Unexpected error toggling like: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_comments_tree(
        session: AsyncSession,
        entity_type: str,
        entity_id: UUID,
        user_id: Optional[UUID] = None,
        limit: int = 20,
        offset: int = 0,
        max_reply_depth: int = 3,
    ) -> Dict[str, Any]:
        """
        Get hierarchical comment tree with optimized single query.

        Args:
            session: Database session
            entity_type: Entity type
            entity_id: Entity ID
            user_id: Optional user ID for like status
            limit: Number of root comments per page
            offset: Pagination offset
            max_reply_depth: Maximum reply depth

        Returns:
            Dictionary with comment tree data
        """
        try:
            # Get all non-deleted comments for this entity
            query = (
                select(Comment)
                .where(
                    and_(
                        Comment.entity_type == entity_type,
                        Comment.entity_id == entity_id,
                        Comment.is_deleted.is_(False),
                    )
                )
                .order_by(Comment.created_at.desc())
            )

            result = await session.execute(query)
            all_comments = result.scalars().all()

            # Convert to dict for easy lookup
            comment_dict = {comment.id: comment for comment in all_comments}
            root_comments = []
            total_likes = 0

            # Build hierarchy using a reply map instead of modifying ORM objects
            reply_map = {}

            # Build hierarchy and identify root comments
            for comment in all_comments:
                if comment.parent_comment_id is None:
                    # This is a root comment
                    root_comments.append(comment)
                else:
                    # This is a reply, add to parent's replies
                    parent = comment_dict.get(comment.parent_comment_id)
                    if parent:
                        if parent.id not in reply_map:
                            reply_map[parent.id] = []
                        reply_map[parent.id].append(comment)

            # Get all likes for this entity in a single query
            likes_dict = {}
            if user_id:
                like_query = select(CommentLike).where(
                    CommentLike.user_id == user_id,
                    CommentLike.comment_id.in_([c.id for c in all_comments]),
                )
                like_result = await session.execute(like_query)
                liked_comments = like_result.scalars().all()
                likes_dict = {like.comment_id: True for like in liked_comments}

            # Apply pagination to root comments
            total_root_count = len(root_comments)
            paginated_roots = root_comments[offset : offset + limit]
            has_more = offset + limit < total_root_count

            # Convert to response format
            def build_comment_tree(comment, depth=0, reply_map=None):
                if depth > max_reply_depth:
                    return None

                comment_data = {
                    "id": comment.id,
                    "entity_type": comment.entity_type,
                    "entity_id": comment.entity_id,
                    "content": comment.content,
                    "user_id": comment.user_id,
                    "parent_comment_id": comment.parent_comment_id,
                    "like_count": comment.like_count,
                    "reply_count": comment.reply_count,
                    "is_edited": comment.is_edited,
                    "is_deleted": comment.is_deleted,
                    "is_pinned": comment.is_pinned,
                    "created_at": comment.created_at,
                    "updated_at": comment.updated_at,
                    "edited_at": comment.edited_at,
                    "username": "User",  # Will be populated by service layer
                    "has_liked": False,
                    "replies": [],
                }

                # Check if user liked this comment
                if user_id:
                    comment_data["has_liked"] = likes_dict.get(comment.id, False)

                # Recursively build replies
                if reply_map and comment.id in reply_map:
                    for reply in sorted(
                        reply_map[comment.id], key=lambda x: x.created_at
                    ):
                        reply_data = build_comment_tree(reply, depth + 1, reply_map)
                        if reply_data:
                            comment_data["replies"].append(reply_data)

                return comment_data

            # Build response tree
            response_comments = []
            for root_comment in paginated_roots:
                comment_data = build_comment_tree(root_comment, reply_map=reply_map)
                if comment_data:
                    response_comments.append(comment_data)
                    total_likes += root_comment.like_count

            # Calculate total comments count
            total_comments_count = len(all_comments)

            return {
                "comments": response_comments,
                "total_comments": total_comments_count,
                "total_likes": total_likes,
                "has_more": has_more,
                "next_offset": offset + limit if has_more else None,
            }

        except SQLAlchemyError as e:
            logger.error(f"Database error getting comment tree: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting comment tree: {e}")
            raise

    @staticmethod
    async def get_comment_by_id(
        session: AsyncSession,
        comment_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific comment by ID.

        Args:
            session: Database session
            comment_id: Comment ID
            user_id: Optional user ID for like status

        Returns:
            Comment data or None if not found
        """
        try:
            query = select(Comment).where(Comment.id == comment_id)
            result = await session.execute(query)
            comment = result.scalar_one_or_none()

            if not comment:
                return None

            # Convert to response format
            comment_data = {
                "id": comment.id,
                "entity_type": comment.entity_type,
                "entity_id": comment.entity_id,
                "content": comment.content,
                "user_id": comment.user_id,
                "parent_comment_id": comment.parent_comment_id,
                "like_count": comment.like_count,
                "reply_count": comment.reply_count,
                "is_edited": comment.is_edited,
                "is_deleted": comment.is_deleted,
                "is_pinned": comment.is_pinned,
                "created_at": comment.created_at,
                "updated_at": comment.updated_at,
                "edited_at": comment.edited_at,
                "username": "User",  # Will be populated by service layer
                "has_liked": False,
                "replies": [],
            }

            # Add like status if user_id provided
            if user_id:
                like_query = select(CommentLike).where(
                    and_(
                        CommentLike.comment_id == comment.id,
                        CommentLike.user_id == user_id,
                    )
                )
                like_result = await session.execute(like_query)
                comment_data["has_liked"] = like_result.scalar_one_or_none() is not None

            return comment_data

        except SQLAlchemyError as e:
            logger.error(f"Database error getting comment by ID: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting comment by ID: {e}")
            raise
