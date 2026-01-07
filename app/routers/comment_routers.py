"""
Comment Router Module - API endpoints for comment operations following dashboard pattern.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status

from app.auth.dependencies import get_current_user
from app.schemas.comments_schema import (
    CommentAction,
    CommentCreateRequest,
    CommentOperationResponse,
    CommentResponse,
    CommentTreeResponse,
    CommentType,
    CommentUpdateRequest,
)
from app.services.comment_service import CommentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comments", tags=["comments"])


@router.post(
    "/{entity_type}/{entity_id}/{comment_type}",
    response_model=CommentOperationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    entity_type: str = Path(
        ..., description="Entity type: dashboard, workflow, report"
    ),
    entity_id: UUID = Path(..., description="Entity ID"),
    comment_type: CommentType = Path(..., description="Comment type: create or reply"),
    request: CommentCreateRequest = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new comment or reply.

    - CREATE: Root comment (parent_comment_id should be null)
    - REPLY: Reply to existing comment (parent_comment_id required)
    """
    try:
        logger.info(
            f"Creating {comment_type.value} comment for {entity_type}/{entity_id}"
        )

        # Validate entity type
        valid_entity_types = ["dashboard", "workflow", "report"]
        if entity_type not in valid_entity_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid entity type. Must be one of: {valid_entity_types}",
            )

        result = await CommentService.create_comment(
            entity_type=entity_type,
            entity_id=entity_id,
            comment_type=comment_type,
            content=request.content,
            parent_comment_id=request.parent_comment_id,
            user_id=current_user["user_id"],
        )

        response = CommentOperationResponse(
            success=True,
            action=CommentAction.CREATE,
            comment_id=result["id"],
            message=f"{comment_type.value.capitalize()} comment created successfully",
            data=CommentResponse(**result),
        )

        logger.info(f"Comment created successfully - ID: {result['id']}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating comment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create comment",
        )


@router.get("/{entity_type}/{entity_id}", response_model=CommentTreeResponse)
async def get_comments(
    entity_type: str = Path(
        ..., description="Entity type: dashboard, workflow, report"
    ),
    entity_id: UUID = Path(..., description="Entity ID"),
    limit: int = Query(
        20, ge=1, le=100, description="Number of root comments per page"
    ),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    max_reply_depth: int = Query(3, ge=1, le=10, description="Maximum reply depth"),
    current_user: dict = Depends(get_current_user),
):
    """
    Get hierarchical comment tree with nested replies (YouTube/Instagram style).

    Returns root comments with nested replies up to specified depth.
    """
    try:
        logger.info(f"Getting comments for {entity_type}/{entity_id}")

        # Validate entity type
        valid_entity_types = ["dashboard", "workflow", "report"]
        if entity_type not in valid_entity_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid entity type. Must be one of: {valid_entity_types}",
            )

        result = await CommentService.get_hierarchical_comments(
            entity_type=entity_type,
            entity_id=str(entity_id),
            user_id=str(current_user["user_id"]),
            limit=limit,
            offset=offset,
            max_reply_depth=max_reply_depth,
        )

        response = CommentTreeResponse(
            entity_type=entity_type,
            entity_id=entity_id,
            comments=[CommentResponse(**comment) for comment in result["comments"]],
            total_comments=result["total_comments"],
            total_likes=result["total_likes"],
            has_more=result["has_more"],
            next_offset=result["next_offset"],
        )

        logger.info(f"Returning {len(result['comments'])} comments")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting comments: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get comments",
        )


@router.put("/{comment_id}", response_model=CommentOperationResponse)
async def update_comment(
    comment_id: UUID = Path(..., description="Comment ID to update"),
    request: CommentUpdateRequest = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Update comment content.

    Only the comment author can update their own comments.
    """
    try:
        logger.info(f"Updating comment {comment_id}")

        result = await CommentService.update_comment(
            comment_id=comment_id,
            content=request.content,
            user_id=current_user["user_id"],
        )

        response = CommentOperationResponse(
            success=True,
            action=CommentAction.UPDATE,
            comment_id=comment_id,
            message="Comment updated successfully",
            data=CommentResponse(**result),
        )

        logger.info("Comment updated successfully")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating comment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update comment",
        )


@router.post("/{comment_id}/like", response_model=CommentOperationResponse)
async def like_comment(
    comment_id: UUID = Path(..., description="Comment ID to like/unlike"),
    current_user: dict = Depends(get_current_user),
):
    """
    Like or unlike a comment (toggles like status).

    Toggles the like status for the current user.
    """
    try:
        logger.info(f"Toggling like for comment {comment_id}")

        result = await CommentService.toggle_comment_like(
            comment_id=comment_id,
            user_id=current_user["user_id"],
        )

        action = CommentAction.LIKE if result["has_liked"] else CommentAction.UNLIKE

        response = CommentOperationResponse(
            success=True,
            action=action,
            comment_id=comment_id,
            message=f"Comment {'liked' if result['has_liked'] else 'unliked'} successfully",
            data=CommentResponse(**result),
        )

        logger.info(f"Like toggled - has_liked: {result['has_liked']}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error liking comment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to like comment",
        )


@router.delete("/{comment_id}", response_model=CommentOperationResponse)
async def delete_comment(
    comment_id: UUID = Path(..., description="Comment ID to delete"),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a comment.

    Soft delete that preserves comment thread integrity.
    Only the comment author can delete their own comments.
    """
    try:
        logger.info(f"Deleting comment {comment_id}")

        success = await CommentService.delete_comment(
            comment_id=comment_id,
            user_id=current_user["user_id"],
        )

        response = CommentOperationResponse(
            success=True,
            action=CommentAction.DELETE,
            comment_id=comment_id,
            message="Comment deleted successfully",
            data=None,
        )

        logger.info("Comment deleted successfully")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting comment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete comment",
        )
