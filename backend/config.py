"""Settings for the AI assistant. Change a model here and nowhere else."""

# Used when ANTHROPIC_API_KEY is set in .env (paid; see console.anthropic.com).
CLAUDE_MODEL = "claude-opus-5"

# Used when GEMINI_API_KEY is set (free tier: https://aistudio.google.com/apikey).
# Google's OpenAI-compatible address, so the same client code works.
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-2.5-flash"

# Used when PUBLIK_API_KEY is set (and there's no Anthropic or Gemini key).
# publik is OpenAI-compatible: https://publikhq.com/developers
# Use publik's tier names only (publik-fast / publik-balanced / publik-smart), never vendor model names.
PUBLIK_BASE_URL = "https://publikhq.com/api/v1"
PUBLIK_MODEL = "publik-balanced"
PUBLIK_RETRY_SECONDS = 10  # publik docs: on a 503, wait 10 seconds and retry once

# How much the assistant may write (a short, plain answer needs far less).
MAX_ANSWER_TOKENS = 2000
