"""The one place PantryPilot talks to an AI model.

Claude first (if ANTHROPIC_API_KEY is set), then Google Gemini (GEMINI_API_KEY),
then the publik API (PUBLIK_API_KEY). Gemini and publik both use the OpenAI-compatible client.
generate_json() returns a Python dict matching the schema it's given (ANSWER_SCHEMA by default).
Keys come only from environment variables (.env locally, Vercel settings online);
they are never hard-coded, logged, or sent to the browser.
"""

import json
import logging
import os
import re
import time

from dotenv import load_dotenv

from backend.config import (
    CLAUDE_MODEL, GEMINI_BASE_URL, GEMINI_MODEL, MAX_ANSWER_TOKENS, PUBLIK_BASE_URL, PUBLIK_MODEL,
    PUBLIK_RETRY_SECONDS,
)

log = logging.getLogger("pantrypilot.llm")

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
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("PUBLIK_API_KEY"):
        return "publik"
    return None


def generate_json(system, user, schema=None):
    schema = schema or ANSWER_SCHEMA
    provider = active_provider()
    if provider == "claude":
        return _ask_claude(system, user, schema)
    if provider == "gemini":
        return _ask_openai_compatible("Gemini", GEMINI_BASE_URL, GEMINI_MODEL, "GEMINI_API_KEY", system, user, schema)
    if provider == "publik":
        return _ask_openai_compatible("publik", PUBLIK_BASE_URL, PUBLIK_MODEL, "PUBLIK_API_KEY", system, user, schema)
    raise LLMUnavailable("No AI key found. Add GEMINI_API_KEY (or PUBLIK_API_KEY / ANTHROPIC_API_KEY) to .env")


def _ask_claude(system, user, schema=None):
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
                "format": {"type": "json_schema", "schema": schema or ANSWER_SCHEMA},
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


def _ask_openai_compatible(name, base_url, model, key_env, system, user, schema=None):
    schema = schema or ANSWER_SCHEMA
    """Ask any OpenAI-compatible API: Gemini or publik (https://publikhq.com/developers)."""
    from openai import APIConnectionError, APIStatusError, OpenAI

    client = OpenAI(
        api_key=os.environ[key_env],  # sent as "Authorization: Bearer ..."
        base_url=base_url,
        max_retries=0,  # we follow publik's own retry advice below instead
        timeout=25,     # seconds per try; worst case 25 + 10 wait + 25, within Vercel's function limit
    )
    messages = [
        {"role": "system", "content": system + "\n\nReply with ONLY a JSON object with these keys: "
         + json.dumps(schema["properties"])},
        {"role": "user", "content": user},
    ]

    for attempt in (1, 2):
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=MAX_ANSWER_TOKENS,
                response_format={"type": "json_object"},
                messages=messages,
            )
            break
        except APIStatusError as error:
            # 503 is temporary (publik docs; Gemini too), so retry once after 10 seconds.
            if error.status_code == 503 and attempt == 1:
                time.sleep(PUBLIK_RETRY_SECONDS)
                continue
            if error.status_code == 402:
                # Out of balance. The top-up link is for YOU (the app owner), so it goes to
                # the server log; visitors just get the friendly "dial 2-1-1" message.
                # The SDK usually passes the inner "error" object as body; accept both shapes.
                body = error.body if isinstance(error.body, dict) else {}
                details = body.get("error", body) if isinstance(body.get("error", body), dict) else {}
                log.error("%s balance empty: %s Top up: %s", name, details.get("message"), details.get("top_up_url"))
            else:
                log.error("%s API error %s", name, error.status_code)  # e.g. 429 = free-tier limit reached
            raise LLMUnavailable(f"{name} API error {error.status_code}") from error
        except APIConnectionError as error:
            raise LLMUnavailable(f"Couldn't reach the {name} API") from error

    try:
        data = parse_json_answer(response.choices[0].message.content)
    except (ValueError, IndexError, TypeError, AttributeError) as error:
        raise LLMUnavailable(f"{name} answer wasn't valid JSON") from error

    # JSON mode doesn't enforce our exact shape, so check it ourselves.
    if schema is not ANSWER_SCHEMA:
        return data  # other shapes (like the search plan) are checked by the caller
    if not isinstance(data.get("answer"), str) or not data["answer"].strip():
        raise LLMUnavailable(f"{name} answer was missing the answer text")
    sources = data.get("used_sources", [])
    data["used_sources"] = [n for n in sources if isinstance(n, int)] if isinstance(sources, list) else []
    return data


def parse_json_answer(text):
    """Read the model's JSON, even if it wrapped it in ```json fences or added a sentence."""
    if not isinstance(text, str):
        raise ValueError("no text")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)  # the outermost {...}
        if not match:
            raise ValueError("no JSON object found")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("JSON was not an object")
    return data
