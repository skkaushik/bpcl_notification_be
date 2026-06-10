"""
AI Intent Layer.

Uses an LLM to understand user intent and map it to
analytics engine functions. The LLM does NOT perform
any calculations — it only classifies intent and selects
the appropriate analytics function(s).
"""

import json
import logging
from typing import Optional

from google import genai
from openai import OpenAI

from app.config import settings
from app.models.schemas import AnalyticsIntent
from app.services.analytics_engine import ANALYTICS_FUNCTIONS

logger = logging.getLogger(__name__)


# ─── System Prompt ─────────────────────────────────────────────────────────────

def _build_intent_system_prompt() -> str:
    """Build the system prompt that teaches the LLM about available functions."""
    functions_desc = "\n".join(
        f"  - {name}: {info['description']} (params: {', '.join(info['params']) if info['params'] else 'none'})"
        for name, info in ANALYTICS_FUNCTIONS.items()
    )

    return f"""You are an intent classifier for a refinery maintenance notification intelligence system.
Your job is to understand the user's question about maintenance notifications and determine which analytics function to call.

AVAILABLE ANALYTICS FUNCTIONS:
{functions_desc}

DOMAIN KNOWLEDGE:
- Notification types: M1 (Breakdown), M2 (Preventive Maintenance), M3-M9 (other types)
- Priorities: 1 (Very High), 2 (High), 3 (Medium), 4 (Low)
- Work centers start with a department prefix (MS, MR, MI, ME, MC, FS), or fall under 'OTHERS' if no prefix matches. Followed by the unit name.
- "Unit", "Plant Name", and "Main Workctr" all refer to the exact same thing (Work Center).
- Common statuses: CRTD (Created), NOPR (No Processing), NOCO (No Completion), etc.
- "Critical" typically means priority 1 or 2, or breakdown notifications (M1)
- "Overdue" means the due date / required end date has passed
- "Backlog" means open + overdue notifications
- "Recurring" means equipment with multiple notifications (chronic issues)
- "Problematic equipment" means equipment with high notification count and/or breakdowns

INSTRUCTIONS:
1. Analyze the user's question carefully
2. Select the BEST matching function. If the user asks for a count (e.g. "count of M1", "how many open"), ALWAYS use a statistics function (like get_summary_stats, get_type_distribution) instead of a list function (like get_open_notifications), because list functions have a limit (max 50) and will give wrong counts.
3. Extract any relevant parameters from the question
4. Determine the best response_type: "summary" (text answer), "table" (data rows), "chart" (visualization), or "insight" (business analysis)
5. If a chart makes sense, specify chart_config with type ("bar", "pie", or "line") and title

Respond with ONLY valid JSON (no markdown fencing, no extra text):
{{
  "intent": "brief description of what user wants",
  "function_name": "exact_function_name_from_list",
  "parameters": {{}},
  "response_type": "summary|table|chart|insight",
  "chart_config": {{"type": "bar|pie|line", "title": "Chart Title"}}
}}

If chart is not relevant, set chart_config to null.
If you cannot determine the intent, use function_name "get_summary_stats" as a safe fallback.
"""


# ─── Intent Classification ─────────────────────────────────────────────────────

async def classify_intent(
    user_message: str,
    chat_history: list[dict],
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> AnalyticsIntent:
    """
    Use LLM to classify user intent and map to an analytics function.
    
    Args:
        user_message: The user's natural language question.
        chat_history: Previous conversation for context.
        provider: AI provider ('gemini' or 'openai'). Defaults to config.
        api_key: API key. Falls back to server config if not provided.
    
    Returns:
        AnalyticsIntent with function name and parameters.
    """
    active_provider = provider or settings.AI_PROVIDER
    active_key = api_key or (
        settings.GEMINI_API_KEY if active_provider == "gemini"
        else settings.OPENAI_API_KEY
    )

    if not active_key:
        raise ValueError(
            f"No API key available for provider '{active_provider}'. "
            "Set it in .env or pass via request."
        )

    system_prompt = _build_intent_system_prompt()

    # Build conversation context (last 4 exchanges for context)
    recent_history = chat_history[-8:] if chat_history else []

    try:
        if active_provider == "gemini":
            raw_response = await _classify_with_gemini(
                system_prompt, user_message, recent_history, active_key
            )
        else:
            raw_response = await _classify_with_openai(
                system_prompt, user_message, recent_history, active_key
            )

        intent = _parse_intent_response(raw_response)
        logger.info(f"Classified intent: {intent.function_name} for query: '{user_message[:80]}...'")
        return intent

    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        # Fallback to summary stats
        return AnalyticsIntent(
            intent="fallback_summary",
            function_name="get_summary_stats",
            parameters={},
            response_type="summary",
        )


async def _classify_with_gemini(
    system_prompt: str,
    user_message: str,
    history: list[dict],
    api_key: str,
) -> str:
    """Classify intent using Google Gemini."""
    client = genai.Client(api_key=api_key)

    # Build contents
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(genai.types.Content(
            role=role,
            parts=[genai.types.Part(text=msg["content"])]
        ))
    contents.append(genai.types.Content(
        role="user",
        parts=[genai.types.Part(text=user_message)]
    ))

    response = client.models.generate_content(
        model=settings.AI_MODEL if settings.AI_PROVIDER == "gemini" else "gemini-2.5-flash",
        contents=contents,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0,
            max_output_tokens=500,
        ),
    )

    return response.text


async def _classify_with_openai(
    system_prompt: str,
    user_message: str,
    history: list[dict],
    api_key: str,
) -> str:
    """Classify intent using OpenAI."""
    client = OpenAI(api_key=api_key)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0,
        max_tokens=500,
    )

    return response.choices[0].message.content


def _parse_intent_response(raw: str) -> AnalyticsIntent:
    """Parse the LLM's JSON response into an AnalyticsIntent."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse intent JSON: {e}. Raw: {raw[:200]}")
        return AnalyticsIntent(
            intent="parse_error",
            function_name="get_summary_stats",
            parameters={},
            response_type="summary",
        )

    # Validate function name
    fn_name = data.get("function_name", "get_summary_stats")
    if fn_name not in ANALYTICS_FUNCTIONS:
        logger.warning(f"Unknown function '{fn_name}', falling back to get_summary_stats")
        fn_name = "get_summary_stats"

    return AnalyticsIntent(
        intent=data.get("intent", "unknown"),
        function_name=fn_name,
        parameters=data.get("parameters", {}),
        response_type=data.get("response_type", "summary"),
        chart_config=data.get("chart_config"),
    )
