"""
Chat router — handles AI-powered Q&A with analytics backend.

Flow:
  User question → AI Intent Layer → Analytics Engine → Response Generator → Response
"""

import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest, ChatResponse
from app.services.data_store import data_store
from app.services.ai_intent import classify_intent
from app.services.analytics_engine import ANALYTICS_FUNCTIONS
from app.services.response_generator import generate_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a natural language question about the uploaded notification data.
    
    The system will:
    1. Classify the user's intent via LLM
    2. Execute the matching analytics function (deterministic)
    3. Generate an insightful response via LLM
    
    The LLM never performs calculations directly.
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

    # Save user message to history
    data_store.add_chat_message(request.session_id, "user", request.message)

    try:
        # ── Step 1: Classify intent ──────────────────────────────────────
        intent = await classify_intent(
            user_message=request.message,
            chat_history=session.chat_history,
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
        analytics_data = analytics_fn(session.normalized_df, **kwargs)

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



