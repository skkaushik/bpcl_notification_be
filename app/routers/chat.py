"""
Chat router — handles AI-powered Q&A with analytics backend.

Flow:
  User question → AI Intent Layer → Analytics Engine → Response Generator → Response
"""

import logging
import pandas as pd
from fastapi import APIRouter, HTTPException
from httpx import request
from requests import session
from app.models.schemas import ChatRequest, ChatResponse
from app.services.data_store import data_store
from app.services.ai_intent import classify_intent
from app.services.analytics_engine import ANALYTICS_FUNCTIONS
from app.services.response_generator import generate_response
from app.db.mongodb import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

"""
    Send a natural language question about the uploaded notification data.
    
    The system will:
    1. Classify the user's intent via LLM
    2. Execute the matching analytics function (deterministic)
    3. Generate an insightful response via LLM
    
    The LLM never performs calculations directly.
     """

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    session = data_store.get_session(request.session_id)

    normalized_df = None

    # Memory check
    if session is not None:
        logger.info("Session loaded from memory")

    # MongoDB fallback
    else:
        mongo_session = await db.sessions.find_one({
            "session_id": request.session_id
        })

        if mongo_session is None:
            raise HTTPException(
                status_code=404,
                detail="Session not found."
            )

        normalized_df = pd.DataFrame(
            mongo_session["normalized_df"]
        )

        logger.info(
            f"Session loaded from MongoDB: {request.session_id}"
        )
    # Validate data exists
    if session:

        if session.row_count == 0:
            raise HTTPException(
                status_code=422,
                detail="Session has no data."
            )

    else:

        if len(normalized_df) == 0:
            raise HTTPException(
                status_code=422,
                detail="Session has no data."
            )
    # Save user message to history
    data_store.add_chat_message(request.session_id, "user", request.message)

    try:
        # ── Step 1: Classify intent ──────────────────────────────────────
        history = session.chat_history if session else []

        intent = await classify_intent(
            user_message=request.message,
            chat_history=history,
        )

        logger.info(
            f"[{request.session_id[:8]}] Intent: {intent.function_name} "
            f"(params: {intent.parameters})"
        )

        # ── Step 2: Execute analytics function ───────────────────────────
        fn_entry = ANALYTICS_FUNCTIONS.get(intent.function_name)
        if fn_entry is None:
            # Shouldn't happen due to validation in intent layer, but just in case
            fn_entry = ANALYTICS_FUNCTIONS["get_summary_stats"]

        analytics_fn = fn_entry["fn"]
        allowed_params = fn_entry["params"]

        # Build kwargs from intent parameters, only passing allowed ones
        kwargs = {}
        for param in allowed_params:
            if param in intent.parameters:
                kwargs[param] = intent.parameters[param]

        # Call the analytics function with the normalized DataFrame
        df = (
            session.normalized_df
            if session
            else normalized_df
        )

        analytics_data = analytics_fn(
            df,
            **kwargs
        )

        logger.info(
            f"[{request.session_id[:8]}] Analytics computed: "
            f"{type(analytics_data).__name__}"
        )

        # ── Step 3: Generate response ────────────────────────────────────
        response = await generate_response(
            user_message=request.message,
            intent=intent,
            analytics_data=analytics_data,
            chat_history=session.chat_history,
        )

        # Save assistant response to history
        data_store.add_chat_message(
            request.session_id, "assistant", response.data.message
        )

        return response
    

    except ValueError as e:
        # Missing API key or config error
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.exception(f"Chat error for session {request.session_id[:8]}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your question: {str(e)}",
        )
# @router.get("/mongo-test")
# async def mongo_test():

#     count = await db.sessions.count_documents({})

#     return {
#         "success": True,
#         "session_count": count
#     }


