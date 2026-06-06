import asyncio
import os
import sys
import json

sys.path.append("/home/sachin/Documents/bpcl_notification_be")

from app.services.ai_intent import classify_intent

async def main():
    history = [
        {"role": "user", "content": "total number of notification"},
        {"role": "assistant", "content": json.dumps({"message": "The total number of notifications is 467. M1 is 213."})},
    ]
    intent = await classify_intent(
        "what ae m1 types notification we have, just count number",
        history,
    )
    print("Function:", intent.function_name)
    print("Params:", intent.parameters)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("/home/sachin/Documents/bpcl_notification_be/.env")
    asyncio.run(main())
