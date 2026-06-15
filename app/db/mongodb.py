from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
import logging

logger = logging.getLogger(__name__)

try:
    client = AsyncIOMotorClient(settings.MONGODB_URL)

    db = client[settings.DATABASE_NAME]

    logger.info("✅ MongoDB client initialized successfully")
    logger.info(f"📂 Database: {settings.DATABASE_NAME}")

except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {str(e)}")