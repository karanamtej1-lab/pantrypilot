"""Settings for the AI assistant. Change a model here and nowhere else."""

# Used when ANTHROPIC_API_KEY is set in .env (paid; see console.anthropic.com).
CLAUDE_MODEL = "claude-opus-5"

# Used when only GROQ_API_KEY is set (free tier). Groq retires models often;
# if this stops working, pick a current one from https://console.groq.com/docs/models
GROQ_MODEL = "openai/gpt-oss-120b"

# How much the assistant may write (a short, plain answer needs far less).
MAX_ANSWER_TOKENS = 2000
