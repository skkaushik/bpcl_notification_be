"""
Upload router — handles file upload and session management.
"""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
from app.db.mongodb import db
from datetime import datetime
from app.config import settings
from app.models.schemas import UploadResponse
from app.services.file_parser import parse_file, FileParseError
from app.services.schema_normalizer import normalize_dataframe
from app.services.data_store import data_store
from app.services.analytics_engine import get_summary_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    print("🚀 UPLOAD API CALLED")

    # Validate file extension
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided."
        )

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if ext not in ("xlsx", "xls", "csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '.{ext}'. Use .xlsx, .xls, or .csv.",
        )

    # Read file content
    content = await file.read()

    # Check file size
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )

    # Parse file
    try:
        raw_df = parse_file(content, file.filename)
    except FileParseError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e)
        )

    # Normalize schema
    normalized_df, column_mapping = normalize_dataframe(raw_df)

    # Create session in memory (existing logic)
    session_id = data_store.create_session(
        file_name=file.filename,
        raw_df=raw_df,
        normalized_df=normalized_df,
        column_mapping=column_mapping,
    )

    # Debug
    print(normalized_df.dtypes)

    # Mongo-safe dataframe
    mongo_df = normalized_df.copy()

    for col in mongo_df.columns:
        mongo_df[col] = mongo_df[col].astype(str)

    mongo_data = mongo_df.to_dict("records")

    # Save session to MongoDB
    result = await db.sessions.insert_one({
        "session_id": session_id,
        "file_name": file.filename,
        "normalized_df": mongo_data,
        "column_mapping": column_mapping,
        "created_at": datetime.utcnow()
    })

    print("Mongo Inserted ID:", result.inserted_id)
    
    logger.info("================================")
    logger.info("✅ FILE UPLOAD SUCCESS")
    logger.info(f"📄 File Name: {file.filename}")
    logger.info(f"🆔 Session ID: {session_id}")
    logger.info(f"📊 Rows: {len(raw_df)}")
    logger.info(f"🗄 Mongo ID: {result.inserted_id}")
    logger.info("================================")

    logger.info(
        f"File uploaded: {file.filename} "
        f"({len(raw_df)} rows, "
        f"{len(column_mapping)} columns mapped) "
        f"→ session {session_id}"
    )

    return UploadResponse(
        data={
            "session_id": session_id
        }
    )