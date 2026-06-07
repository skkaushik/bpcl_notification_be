"""
Response Generator.

Takes analytics results + user question + intent and uses
the LLM to generate a human-readable, insightful response.
The LLM summarizes and interprets pre-computed data — it
does NOT perform any calculations itself.
"""

import json
import logging
from typing import Optional, Any

from google import genai
from openai import OpenAI

from app.config import settings
from app.models.schemas import AnalyticsIntent, ChatResponse

logger = logging.getLogger(__name__)


# ─── System Prompt ─────────────────────────────────────────────────────────────

RESPONSE_SYSTEM_PROMPT = """You are an expert refinery maintenance intelligence assistant.
You are given pre-computed analytics data and must generate a helpful response.

CRITICAL RULES:
1. ALL numbers in the analytics data are EXACT and PRE-CALCULATED. Use them directly. Do NOT recalculate.
2. ANSWER DIRECTLY: Provide exactly what the user asked for. If they ask for a single metric (e.g., "total number of notifications"), just give them that metric. Do NOT provide extra tables, breakdowns, or insights unless explicitly requested.
3. Be concise and clear.
4. Keep responses strictly focused on the user's specific question. Do not add unprompted data.

RESPONSE FORMAT:
Respond with ONLY valid JSON (no markdown fencing). You MUST put ALL information directly inside the "message" field formatted as Markdown.

{
  "message": "Your complete natural language response here. If the user asks for a table, format it as a Markdown table here."
}

GUIDELINES:
- Do NOT output tables or extra statistics unless the user specifically asks for breakdowns, lists, or details.
- Only provide actionable insights or highlight concerning patterns if the user asks for an analysis, summary, or highlights.
"""


# ─── Response Generation ──────────────────────────────────────────────────────

async def generate_response(
    user_message: str,
    intent: AnalyticsIntent,
    analytics_data: Any,
    chat_history: list[dict],
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ChatResponse:
    """
    Generate a human-readable response from analytics results.
    
    Args:
        user_message: Original user question.
        intent: Classified intent from AI intent layer.
        analytics_data: Pre-computed results from analytics engine.
        chat_history: Conversation history for context.
        provider: AI provider override.
        api_key: API key override.
    
    Returns:
        ChatResponse with message, optional table/chart data, insights, and suggestions.
    """
    active_provider = provider or settings.AI_PROVIDER
    active_key = api_key or (
        settings.GEMINI_API_KEY if active_provider == "gemini"
        else settings.OPENAI_API_KEY
    )

    if not active_key:
        raise ValueError(f"No API key for provider '{active_provider}'.")

    # Build the user prompt with analytics context
    user_prompt = _build_response_prompt(user_message, intent, analytics_data)

    try:
        if active_provider == "gemini":
            raw = await _generate_with_gemini(user_prompt, chat_history, active_key)
        else:
            raw = await _generate_with_openai(user_prompt, chat_history, active_key)

        return _parse_response(raw, intent)

    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        # Fallback: return user-friendly error message without raw data
        error_msg = f"**Error from AI Provider:** {str(e)}\n\nPlease try again later or check your AI provider configuration."
        return ChatResponse(data={"message": error_msg})


def _build_response_prompt(
    user_message: str,
    intent: AnalyticsIntent,
    analytics_data: Any,
) -> str:
    """Build the prompt for response generation."""
    # Truncate large data for the LLM
    data_str = json.dumps(analytics_data, indent=2, default=str)
    if len(data_str) > 15000:
        # For large datasets, summarize
        if isinstance(analytics_data, list):
            data_str = json.dumps(analytics_data[:30], indent=2, default=str)
            data_str += f"\n\n... (showing 30 of {len(analytics_data)} total results)"
        else:
            data_str = data_str[:15000] + "\n... (truncated)"

    chart_instruction = ""
    if intent.chart_config:
        chart_instruction = f"""
The user's question suggests a chart would be helpful.
Suggested chart type: {intent.chart_config.get('type', 'bar')}
Suggested title: {intent.chart_config.get('title', 'Chart')}
Include chart_data in your response using the analytics data.
"""

    return f"""USER QUESTION: {user_message}

INTENT: {intent.intent}
ANALYTICS FUNCTION CALLED: {intent.function_name}
RESPONSE TYPE REQUESTED: {intent.response_type}

PRE-COMPUTED ANALYTICS DATA (these numbers are EXACT — use them directly):
{data_str}
{chart_instruction}
Generate your response now."""


async def _generate_with_gemini(
    user_prompt: str,
    history: list[dict],
    api_key: str,
) -> str:
    """Generate response using Gemini."""
    client = genai.Client(api_key=api_key)

    contents = []
    # Add recent history for context
    for msg in history[-6:]:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(genai.types.Content(
            role=role,
            parts=[genai.types.Part(text=msg["content"])]
        ))
    contents.append(genai.types.Content(
        role="user",
        parts=[genai.types.Part(text=user_prompt)]
    ))

    response = client.models.generate_content(
        model=settings.AI_MODEL if settings.AI_PROVIDER == "gemini" else "gemini-2.5-flash",
        contents=contents,
        config=genai.types.GenerateContentConfig(
            system_instruction=RESPONSE_SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=2000,
        ),
    )

    return response.text


async def _generate_with_openai(
    user_prompt: str,
    history: list[dict],
    api_key: str,
) -> str:
    """Generate response using OpenAI."""
    client = OpenAI(api_key=api_key)

    messages = [{"role": "system", "content": RESPONSE_SYSTEM_PROMPT}]
    for msg in history[-6:]:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_prompt})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
        max_tokens=2000,
    )

    return response.choices[0].message.content


def _parse_response(raw: str, intent: AnalyticsIntent) -> ChatResponse:
    """Parse the LLM's JSON response into a ChatResponse."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse response JSON, using raw text.")
        return ChatResponse(data={"message": raw})

    return ChatResponse(
        data={"message": data.get("message", "")}
    )
