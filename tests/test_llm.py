"""Tests for backend/llm.py's publik API provider.

The real network is replaced by a fake OpenAI client, so these run offline, cost
nothing, and never use a real key.
"""

import logging

import httpx2
import openai
import pytest

from backend import config, llm
from backend.llm import LLMUnavailable, active_provider, generate_json, parse_json_answer

FAKE_KEY = "pk_test_not_a_real_key"


def status_error(code, body=None):
    request = httpx2.Request("POST", "https://publikhq.com/api/v1/chat/completions")
    return openai.APIStatusError(f"HTTP {code}", response=httpx2.Response(code, request=request), body=body)


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeOpenAI:
    """Records how it was created and called; answers with queued replies or errors."""
    instances = []

    def __init__(self, replies, **client_args):
        self.client_args = client_args
        self.calls = []
        self.replies = list(replies)
        self.chat = self
        self.completions = self
        FakeOpenAI.instances.append(self)

    def create(self, **request):
        self.calls.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(reply)


@pytest.fixture
def publik(monkeypatch):
    """Use publik (not Claude), with a fake key and a fake client. Returns a function to queue replies."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("PUBLIK_API_KEY", FAKE_KEY)
    monkeypatch.setattr(llm, "PUBLIK_RETRY_SECONDS", 0)  # don't really wait 10 seconds in tests
    FakeOpenAI.instances = []

    def queue(*replies):
        monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: FakeOpenAI(replies, **kwargs))
    return queue


# ---------- which provider ----------

def test_publik_is_used_when_its_key_is_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("PUBLIK_API_KEY", FAKE_KEY)
    assert active_provider() == "publik"


def test_claude_still_wins_if_both_keys_are_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-real")
    monkeypatch.setenv("PUBLIK_API_KEY", FAKE_KEY)
    assert active_provider() == "claude"


def test_no_key_means_unavailable_not_a_crash(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("PUBLIK_API_KEY", raising=False)
    assert active_provider() is None
    with pytest.raises(LLMUnavailable):
        generate_json("system", "user")


def test_groq_key_alone_no_longer_does_anything(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("PUBLIK_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_not_real")
    assert active_provider() is None


# ---------- the request we send ----------

def test_request_uses_publik_url_tier_model_and_env_key(publik):
    publik('{"answer": "Hi", "used_sources": [1]}')
    generate_json("SYSTEM RULES", "USER MESSAGE")
    client = FakeOpenAI.instances[0]
    assert client.client_args["base_url"] == "https://publikhq.com/api/v1"
    assert client.client_args["api_key"] == FAKE_KEY  # from the environment, never hard-coded
    request = client.calls[0]
    assert request["model"] == "publik-balanced" == config.PUBLIK_MODEL
    assert request["response_format"] == {"type": "json_object"}
    assert request["messages"][0]["role"] == "system" and "SYSTEM RULES" in request["messages"][0]["content"]
    assert request["messages"][1] == {"role": "user", "content": "USER MESSAGE"}


def test_returns_answer_and_sources(publik):
    publik('{"answer": "Here you go.", "used_sources": [2, 1]}')
    assert generate_json("s", "u") == {"answer": "Here you go.", "used_sources": [2, 1]}


# ---------- reading the answer ----------

def test_json_inside_code_fences_is_read(publik):
    publik('```json\n{"answer": "Fenced", "used_sources": []}\n```')
    assert generate_json("s", "u")["answer"] == "Fenced"


def test_bad_source_numbers_are_dropped(publik):
    publik('{"answer": "A", "used_sources": [1, "two", null, 3]}')
    assert generate_json("s", "u")["used_sources"] == [1, 3]


@pytest.mark.parametrize("reply", [
    "not json at all",
    '{"used_sources": [1]}',          # no answer
    '{"answer": "   ", "used_sources": []}',  # blank answer
    '["a list", "not an object"]',
])
def test_unusable_answers_become_unavailable(publik, reply):
    publik(reply)
    with pytest.raises(LLMUnavailable):
        generate_json("s", "u")


@pytest.mark.parametrize("text, expected", [
    ('{"answer": "x"}', {"answer": "x"}),
    ('Sure! {"answer": "x", "used_sources": [1]} Hope that helps.', {"answer": "x", "used_sources": [1]}),
])
def test_parse_json_answer(text, expected):
    assert parse_json_answer(text) == expected


# ---------- errors, following publik's docs ----------

def test_503_is_retried_once_then_succeeds(publik):
    publik(status_error(503), '{"answer": "Second try", "used_sources": []}')
    assert generate_json("s", "u")["answer"] == "Second try"
    assert len(FakeOpenAI.instances[0].calls) == 2


def test_503_twice_gives_up(publik):
    publik(status_error(503), status_error(503))
    with pytest.raises(LLMUnavailable):
        generate_json("s", "u")
    assert len(FakeOpenAI.instances[0].calls) == 2  # exactly one retry, no loop


def test_other_errors_are_not_retried(publik):
    publik(status_error(401))
    with pytest.raises(LLMUnavailable):
        generate_json("s", "u")
    assert len(FakeOpenAI.instances[0].calls) == 1


def test_402_logs_top_up_link_for_owner_but_never_the_key(publik, caplog):
    publik(status_error(402, body={"message": "Balance is empty", "top_up_url": "https://publikhq.com/top-up"}))
    with caplog.at_level(logging.ERROR, logger="pantrypilot.llm"), pytest.raises(LLMUnavailable):
        generate_json("s", "u")
    assert "https://publikhq.com/top-up" in caplog.text
    assert FAKE_KEY not in caplog.text


def test_connection_error_becomes_unavailable(publik):
    request = httpx2.Request("POST", "https://publikhq.com/api/v1/chat/completions")
    publik(openai.APIConnectionError(request=request))
    with pytest.raises(LLMUnavailable):
        generate_json("s", "u")


# ---------- Gemini (same OpenAI-compatible code path) ----------

GEMINI_FAKE = "AIza_test_not_a_real_key"


def test_gemini_is_used_before_publik(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_FAKE)
    monkeypatch.setenv("PUBLIK_API_KEY", FAKE_KEY)
    assert active_provider() == "gemini"


def test_gemini_request_uses_google_url_model_and_env_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_FAKE)
    FakeOpenAI.instances = []
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: FakeOpenAI(['{"answer": "Hola", "used_sources": [1]}'], **kwargs))
    assert generate_json("s", "u") == {"answer": "Hola", "used_sources": [1]}
    client = FakeOpenAI.instances[0]
    assert client.client_args["base_url"] == config.GEMINI_BASE_URL
    assert client.client_args["base_url"].startswith("https://generativelanguage.googleapis.com/")
    assert client.client_args["api_key"] == GEMINI_FAKE
    assert client.calls[0]["model"] == config.GEMINI_MODEL


def test_gemini_free_tier_limit_becomes_unavailable_and_is_logged(monkeypatch, caplog):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_FAKE)
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: FakeOpenAI([status_error(429)], **kwargs))
    with caplog.at_level(logging.ERROR, logger="pantrypilot.llm"), pytest.raises(LLMUnavailable):
        generate_json("s", "u")
    assert "Gemini API error 429" in caplog.text and GEMINI_FAKE not in caplog.text
