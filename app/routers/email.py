"""
Email router — handles sending maintenance notification emails.

Frontend sends session_id + filters → backend does everything.
"""

import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import EmailSendRequest, EmailSendResponse
from app.services.data_store import data_store
from app.services.email_routing import send_group_emails

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])


@router.post("/send", response_model=EmailSendResponse)
async def send_emails(request: EmailSendRequest):
    """
    Send maintenance notification emails.

    The frontend sends session_id and dashboard filters.
    The backend loads the session data, applies filters,
    routes notifications to the correct recipients, and sends via SMTP.
    """
    # Validate session
    session = data_store.get_session(request.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found or expired. Please upload a file first.",
        )

    if session.row_count == 0:
        raise HTTPException(
            status_code=422,
            detail="Session has no data. Please upload a valid file.",
        )

    try:
        result = send_group_emails(
            df=session.normalized_df,
            unit_filter=request.unitFilter,
            type_filter=request.typeFilter,
            dept_filter=request.deptFilter,
            user_status_filter=request.userStatusFilter,
            system_status_filter=request.systemStatusFilter,
            start_date=request.startDate,
            end_date=request.endDate,
            age_filter=request.ageFilter,
        )

        if result.get("errors"):
            return EmailSendResponse(
                success=False,
                message="Completed with errors: " + "; ".join(result["errors"]),
                details=result,
            )

        if result["sent_count"] == 0:
            return EmailSendResponse(
                success=True,
                message=result.get("message", "No emails to send."),
                details=result,
            )

        return EmailSendResponse(
            success=True,
            message=(
                f"Successfully sent {result['sent_count']} email(s) "
                f"covering {result['total_notifications']} notifications."
            ),
            details=result,
        )

    except Exception as e:
        logger.exception("Error in /api/email/send")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while sending emails: {str(e)}",
        )
