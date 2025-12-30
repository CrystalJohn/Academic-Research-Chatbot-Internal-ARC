"""
Auth API endpoints for user authentication related operations.

Endpoints:
- POST /api/auth/send-welcome-email - Send welcome email after verification
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.common.email_service import get_email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class WelcomeEmailRequest(BaseModel):
    """Request body for sending welcome email."""

    email: str
    display_name: str


class WelcomeEmailResponse(BaseModel):
    """Response for welcome email."""

    success: bool
    message: str


@router.post("/send-welcome-email", response_model=WelcomeEmailResponse)
async def send_welcome_email(request: WelcomeEmailRequest):
    """
    Send welcome email after successful email verification.

    This endpoint is called by the frontend after the user verifies their email.
    It sends a welcome email with account information (excluding password for security).
    """
    try:
        email_service = get_email_service()
        success = email_service.send_welcome_email(
            to_email=request.email,
            display_name=request.display_name,
        )

        if success:
            return WelcomeEmailResponse(
                success=True,
                message="Welcome email sent successfully",
            )
        else:
            # Don't fail the verification flow if email fails
            logger.warning(f"Failed to send welcome email to {request.email}")
            return WelcomeEmailResponse(
                success=False,
                message="Email could not be sent, but your account is verified",
            )

    except Exception as e:
        logger.error(f"Error sending welcome email: {e}")
        # Don't fail the verification flow
        return WelcomeEmailResponse(
            success=False,
            message="Email service temporarily unavailable",
        )
