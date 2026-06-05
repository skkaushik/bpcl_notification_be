import asyncio
from google import genai
from openai import OpenAI

async def main():
    try:
        print("Testing genai.Client")
        client = genai.Client(api_key="dummy")
        print("genai.Client created successfully")
    except Exception as e:
        print(f"genai failed: {type(e).__name__}: {e}")

    try:
        print("Testing OpenAI")
        client = OpenAI(api_key="dummy")
        print("OpenAI created successfully")
    except Exception as e:
        print(f"OpenAI failed: {type(e).__name__}: {e}")

asyncio.run(main())
