# PantryPilot

A web app that helps people in **Collin County and Denton County, Texas** find food and navigate food assistance. Built for the **Congressional App Challenge** (deadline **October 26, 2026**).

The developer is a beginner. When helping: explain each step simply, keep changes small, and prefer plain readable code over clever code.

## Features

1. **Pantry Map**: a Leaflet + OpenStreetMap map of food pantries in Collin and Denton County, with an **"Open now"** filter based on each pantry's hours.
2. **AI Assistant**: answers food-assistance questions (SNAP, WIC, pantries, school meals) using Claude (`anthropic` SDK) when ANTHROPIC_API_KEY is set, otherwise Groq's free API (`groq` SDK). All AI calls go through `backend/llm.py`.
3. **Hours Coach**: SNAP recipients log work, volunteer, and training hours. A Monte Carlo simulation estimates their chance of reaching **80 hours this month**.

## Stack

- **Backend:** Python, FastAPI, Uvicorn, NumPy, `anthropic` + `groq` SDKs, `python-dotenv`
- **AI models:** set ONLY in `backend/config.py` (`CLAUDE_MODEL`, `GROQ_MODEL`). Never hard-code a model name anywhere else.
- **Frontend:** plain HTML, CSS, and JavaScript (no framework, no build step)
- **Map:** Leaflet with OpenStreetMap tiles
- **Data:** JSON files (no database)
- **Tests:** pytest

## Folder layout

```
backend/     FastAPI app (API routes, AI assistant, Monte Carlo simulation)
frontend/    HTML/CSS/JS pages served to the browser
data/        JSON data (pantries, hours, locations)
knowledge/   Trusted source documents the AI assistant is allowed to use (see knowledge/_EXAMPLE.md for the format)
tests/       pytest tests
AI_LOG.md    Log of what AI helped with and what the developer changed
```

## Rules for the AI Assistant feature (must never be broken)

1. **Trusted sources only.** Answer ONLY from the documents in `knowledge/`. Never use general knowledge or guesses. If the answer isn't in the sources, say so and point the user to the official agency (e.g., Texas HHS / 2-1-1).
2. **Always cite.** Every answer names the source document(s) it came from.
3. **English and Spanish.** Reply in the language the user writes in.
4. **Never decide eligibility.** Never tell someone they do or don't qualify for SNAP, WIC, or any program. Explain the rules the sources state, and direct them to apply or check with the official agency.
5. **Privacy.** Don't ask for or store names, SSNs, case numbers, or addresses.

## Rules for the Hours Coach

- The Monte Carlo result is an **estimate, not a guarantee**. Always label it that way in the UI.
- It is not an official determination of SNAP work requirements. Link to official info.
- Keep the simulation logic in a plain function that is easy to unit test (deterministic when given a random seed).

## Project rules

- **Never commit secrets.** API keys live in `.env` (git-ignored) as `GROQ_API_KEY` and optionally `ANTHROPIC_API_KEY`. Never hard-code it or send it to the frontend. `.env.example` shows the format with a placeholder.
- The frontend never calls an AI API directly. It calls our FastAPI backend.
- Pantry data must list where it came from and when it was last checked.
- Log meaningful AI help in `AI_LOG.md` (the Congressional App Challenge asks about AI use).
- Write a pytest test for backend logic (especially the Monte Carlo and "open now" logic).

## Commands

```bash
source venv/bin/activate          # activate the virtual environment
pip install -r requirements.txt   # install dependencies
pytest                            # run tests
```
