"""The one place PantryPilot talks to an AI model.

Claude first (if ANTHROPIC_API_KEY is in .env), otherwise Groq (GROQ_API_KEY).
Either way, generate_json() returns a Python dict matching ANSWER_SCHEMA.
"""

import json
import os

from dotenv import load_dotenv

from backend.config import CLAUDE_MODEL, GROQ_MODEL, MAX_ANSWER_TOKENS

load_dotenv()  # reads .env into environment variables; keys never go to the browser

# The shape every answer must have: the text, plus which numbered sources it used.
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "used_sources": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["answer", "used_sources"],
    "additionalProperties": False,
}


class LLMUnavailable(Exception):
    """No API key is set, or the AI service couldn't give an answer."""


def active_provider():
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude"
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    return None


def generate_json(system, user):
    provider = active_provider()
    if provider == "claude":
        return _ask_claude(system, user)
    if provider == "groq":
        return _ask_groq(system, user)
    raise LLMUnavailable("No AI key found. Add ANTHROPIC_API_KEY or GROQ_API_KEY to .env")


def _ask_claude(system, user):
    import anthropic

    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_ANSWER_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": "low",  # short factual answers from given text don't need deep thinking
                "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
            },
            # If a safety check declines the request, let Anthropic retry it on
            # its recommended fallback model instead of just failing.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIStatusError as error:
        raise LLMUnavailable(f"Claude API error {error.status_code}") from error
    except anthropic.APIConnectionError as error:
        raise LLMUnavailable("Couldn't reach the Claude API") from error

    if response.stop_reason == "refusal":
        raise LLMUnavailable("The model declined to answer")
    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        raise LLMUnavailable("Empty answer from Claude")
    return json.loads(text)  # structured output guarantees valid JSON


def _ask_groq(system, user):
    from groq import Groq, GroqError

    try:
        response = Groq().chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=MAX_ANSWER_TOKENS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system + "\n\nReply with a JSON object: "
                 '{"answer": "...", "used_sources": [1, 2]}'},
                {"role": "user", "content": user},
            ],
        )
        data = json.loads(response.choices[0].message.content)
    except (GroqError, json.JSONDecodeError, IndexError, TypeError) as error:
        raise LLMUnavailable("Groq API error") from error

    # Groq's JSON mode doesn't enforce our exact shape, so check it ourselves.
    if not isinstance(data.get("answer"), str):
        raise LLMUnavailable("Groq answer was missing the answer text")
    sources = data.get("used_sources", [])
    data["used_sources"] = [n for n in sources if isinstance(n, int)] if isinstance(sources, list) else []
    return data
