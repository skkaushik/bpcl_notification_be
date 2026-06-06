import asyncio
import os
import sys

sys.path.append("/home/sachin/Documents/bpcl_notification_be")

from app.models.schemas import AnalyticsIntent
from app.services.response_generator import generate_response

async def main():
    intent = AnalyticsIntent(
        intent="count m1 types",
        function_name="get_type_distribution",
        parameters={},
        response_type="summary"
    )
    analytics_data = [
        {"name": "M1", "value": 213},
        {"name": "M2", "value": 194},
        {"name": "M3", "value": 15},
    ]
    chat_history = []
    
    response = await generate_response(
        user_message="what ae m1 types notification we have, just count number",
        intent=intent,
        analytics_data=analytics_data,
        chat_history=chat_history
    )
    print("Response:")
    print(response.data.message)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("/home/sachin/Documents/bpcl_notification_be/.env")
    asyncio.run(main())
