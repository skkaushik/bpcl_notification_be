"""
Email router — handles sending maintenance notification emails.

Uses in-memory pandas DataFrame first (fast path).
Falls back to MongoDB if memory is empty (e.g. after server restart).
"""

import logging
import pandas as pd
import socket
from fastapi import APIRouter, HTTPException
from app.services.email_service import get_email_config

from app.models.schemas import EmailSendRequest, EmailSendResponse
from app.services.data_store import data_store
from app.services.email_routing import send_group_emails
from app.db.mongodb import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])


@router.get("/email-config/{plant_name}")
async def fetch_email_config(plant_name: str):
    data = await get_email_config(plant_name)

    if not data:
        return {"success": False, "message": "Plant not found"}

    return {
        "success": True,
        "data": data
    }

@router.get("/smtp-test")
async def smtp_test():
    try:
        socket.create_connection(
            ("smtp.gmail.com", 587),
            timeout=10
        )

        return {
            "success": True,
            "message": "SMTP reachable"
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


async def _get_dataframe() -> pd.DataFrame:
    """
    Get the normalized DataFrame.
    1. Try in-memory (fast, no DB call)
    2. Fallback to MongoDB (survives server restarts)
    """
    # Fast path: in-memory
    session = data_store.get_latest_session()
    if session is not None:
        return session.normalized_df

    # Fallback: MongoDB
    try:
        latest_doc = await db.sessions.find_one(sort=[("created_at", -1)])
        if latest_doc and latest_doc.get("normalized_df"):
            df = pd.DataFrame(latest_doc["normalized_df"])
            df.replace(["nan", "NaN", "NaT", "None"], "", inplace=True)
            logger.info("Loaded data from MongoDB (server had restarted).")
            return df
    except Exception as e:
        logger.warning(f"MongoDB fallback failed: {e}")

    return None


@router.post("/send", response_model=EmailSendResponse)
async def send_emails(request: EmailSendRequest):
    """
    Send maintenance notification emails.
    No session ID or expiration checks required.
    """
    df = await _get_dataframe()
    if df is None or df.empty:
        raise HTTPException(
            status_code=404,
            detail="No data available. Please upload a file first.",
        )

    try:
        result = send_group_emails(
            df=df,
            unit_filter=request.unitFilter,
            type_filter=request.typeFilter,
            dept_filter=request.deptFilter,
            user_status_filter=request.userStatusFilter,
            system_status_filter=request.systemStatusFilter,
            start_date=request.startDate,
            end_date=request.endDate,
            age_filter=request.ageFilter,
            id_filter=request.idFilter,
        )

        if result.get("errors"):
            return EmailSendResponse(
                success=False,
                message="Completed with errors: " + "; ".join(result["errors"]),
                data=result,
            )

        if result["sent_count"] == 0:
            return EmailSendResponse(
                success=True,
                message=result.get("message", "No emails to send."),
                data=None,
            )

        return EmailSendResponse(
            success=True,
            message="Email sent successfully",
            data=None,
        )

    except Exception as e:
        logger.exception("Error in /api/email/send")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while sending emails: {str(e)}",
        )
