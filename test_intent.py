import asyncio
import os
import sys

# add current directory to path
sys.path.append("/home/sachin/Documents/bpcl_notification_be")

from app.services.ai_intent import classify_intent

async def main():
    intent = await classify_intent(
        "what ae m1 types notification we have, just count number",
        [],
    )
    print("Function:", intent.function_name)
    print("Params:", intent.parameters)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("/home/sachin/Documents/bpcl_notification_be/.env")
    asyncio.run(main())
