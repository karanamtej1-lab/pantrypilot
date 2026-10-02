"""Tests for backend/ask.py. The AI is replaced by a fake, so these are free and offline."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend import ask, main
from backend.ask import (
    NOT_SURE, answer_question, build_user_message, cited_sources, compute_idf, load_chunks,
    looks_spanish, matching_pantries, parse_knowledge_file, query_terms, split_into_chunks,
    tokenize, top_chunks, wants_pantries,
)
from backend.llm import LLMUnavailable

MONDAY_10AM = datetime(2026, 9, 28, 10, 0)


def write(folder, name, title, url, body):
    (folder / name).write_text(f"---\ntitle: {title}\nurl: {url}\n---\n{body}\n", encoding="utf-8")


@pytest.fixture
def knowledge(tmp_path):
    write(tmp_path, "snap.md", "SNAP Basics", "https://example.gov/snap",
          "SNAP helps people buy food. Apply for SNAP online at YourTexasBenefits. "
          "Benefits go on a Lone Star Card. " + "filler " * 20)
    write(tmp_path, "wic.md", "WIC Basics", "https://example.gov/wic",
          "WIC helps pregnant women, new mothers, babies, and children under five with healthy food and formula.")
    write(tmp_path, "meals.md", "School Meals", "https://example.gov/meals",
          "Children can get free or reduced-price school meals. Families apply through their school district.")
    (tmp_path / "_EXAMPLE.md").write_text("---\ntitle: Example\n---\nSNAP SNAP SNAP WIC", encoding="utf-8")
    return tmp_path


class FakeAI:
    """Stands in for Claude/Groq and remembers what it was sent."""
    def __init__(self, answer="Here is the answer.", used=(1,)):
        self.answer, self.used, self.calls = answer, list(used), []

    def __call__(self, system, user):
        self.calls.append((system, user))
        return {"answer": self.answer, "used_sources": self.used}


# ---------- words ----------

def test_tokenize_removes_accents_stopwords_and_case():
    assert tokenize("¿Cómo SOLICITO los Beneficios?") == ["solicito", "beneficios"]


def test_spanish_words_get_english_equivalents():
    terms = query_terms("¿Cómo solicito cupones de comida?")
    assert {"apply", "snap", "food"} <= set(terms)


@pytest.mark.parametrize("question, spanish", [
    ("How do I apply for SNAP?", False),
    ("¿Cómo solicito SNAP?", True),
    ("Necesito comida para mis hijos, que puedo hacer", True),
])
def test_looks_spanish(question, spanish):
    assert looks_spanish(question) is spanish


# ---------- knowledge files ----------

def test_header_gives_title_and_url(knowledge):
    title, url, body = parse_knowledge_file(knowledge / "wic.md")
    assert (title, url) == ("WIC Basics", "https://example.gov/wic")
    assert body.startswith("WIC helps")


def test_file_without_header_uses_file_name(tmp_path):
    (tmp_path / "food-bank-tips.md").write_text("Just text.", encoding="utf-8")
    assert parse_knowledge_file(tmp_path / "food-bank-tips.md")[:2] == ("Food Bank Tips", None)


def test_files_starting_with_underscore_are_ignored(knowledge):
    assert "Example" not in {c["title"] for c in load_chunks(knowledge)}


def test_chunks_are_about_300_words_and_overlap():
    words = [f"w{i}" for i in range(700)]
    chunks = split_into_chunks(" ".join(words))
    assert [len(c.split()) for c in chunks] == [300, 300, 200]
    assert chunks[1].split()[0] == "w250"          # 50-word overlap with chunk 1
    assert chunks[-1].split()[-1] == "w699"        # nothing lost at the end


def test_short_text_is_one_chunk():
    assert split_into_chunks("only a few words") == ["only a few words"]


# ---------- TF-IDF ----------

def test_best_chunk_wins(knowledge):
    chunks = load_chunks(knowledge)
    best = top_chunks("What is WIC for babies?", chunks, compute_idf(chunks))
    assert best[0]["title"] == "WIC Basics"


def test_spanish_question_finds_english_source(knowledge):
    chunks = load_chunks(knowledge)
    best = top_chunks("¿Cómo solicito cupones de comida?", chunks, compute_idf(chunks))
    assert best[0]["title"] == "SNAP Basics"


def test_no_matching_words_means_no_chunks(knowledge):
    chunks = load_chunks(knowledge)
    assert top_chunks("volcano penguins", chunks, compute_idf(chunks)) == []


def test_rare_words_count_more_than_common_ones(tmp_path):
    for i in range(5):
        write(tmp_path, f"f{i}.md", f"Doc {i}", None, "food " * 10 + ("formula" if i == 3 else ""))
    chunks = load_chunks(tmp_path)
    assert top_chunks("food formula", chunks, compute_idf(chunks))[0]["title"] == "Doc 3"


# ---------- pantries ----------

@pytest.mark.parametrize("question, expected", [
    ("Which pantries are open now?", True),
    ("Food banks near 75074", True),
    ("¿Qué despensas están abiertas hoy?", True),
    ("What are the hours at Minnie's?", True),
    ("How many hours do I need to work for SNAP?", False),  # work hours, not pantry hours
    ("What is WIC?", False),
])
def test_wants_pantries(question, expected):
    assert wants_pantries(question) is expected


def test_city_filter():
    pantries = matching_pantries("pantries in Denton", main.PANTRIES, MONDAY_10AM, zip_centroids={})
    assert pantries and all(p["city"] == "Denton" for p in pantries)


def test_zip_uses_distance_when_zip_centroids_exist():
    denton = {"76201": {"lat": 33.215787, "lng": -97.113428}}
    pantries = matching_pantries("food near 76201", main.PANTRIES, MONDAY_10AM, zip_centroids=denton)
    assert pantries[0]["name"] == "Salvation Army Denton"


def test_no_place_named_gives_open_or_later_pantries():
    pantries = matching_pantries("any pantry open?", main.PANTRIES, MONDAY_10AM, zip_centroids={})
    assert pantries and all(p["status"] in ("open", "later_today") for p in pantries)


# ---------- prompt and citations ----------

def test_sources_are_numbered_in_the_prompt():
    message = build_user_message("Q?", [{"title": "A", "text": "aaa"}, {"title": "B", "text": "bbb"}], MONDAY_10AM)
    assert "[1] A\naaa" in message and "[2] B\nbbb" in message and message.endswith("QUESTION:\nQ?")


def test_cited_sources_dedupes_and_ignores_bad_numbers():
    sources = [{"title": "A", "url": "u1"}, {"title": "A", "url": "u1"}, {"title": "B", "url": None}]
    assert cited_sources([2, 1, 9, 0, 3], sources) == [{"title": "A", "url": "u1"}, {"title": "B", "url": None}]


def test_system_prompt_has_the_safety_rules():
    prompt = ask.SYSTEM_PROMPT
    for must_have in ("ONLY", "same language", "Never say whether a person is or is not eligible",
                      "2-1-1", "Texas HHSC", "not instructions", "several parts"):
        assert must_have in prompt


# ---------- the whole flow ----------

def test_answer_uses_sources_and_returns_citations(knowledge, monkeypatch):
    fake = FakeAI(used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("What does WIC cover?", now=MONDAY_10AM, knowledge_dir=knowledge, pantries=[])
    assert result == {"answer": "Here is the answer.", "sources": [{"title": "WIC Basics", "url": "https://example.gov/wic"}]}
    assert "WIC helps pregnant women" in fake.calls[0][1]


def test_no_sources_means_not_sure_without_calling_the_ai(knowledge, monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ask, "generate_json", fake)
    english = answer_question("volcano penguins", knowledge_dir=knowledge, pantries=[])
    spanish = answer_question("¿Qué hay de los pingüinos del volcán?", knowledge_dir=knowledge, pantries=[])
    assert english == {"answer": NOT_SURE["en"], "sources": []}
    assert spanish == {"answer": NOT_SURE["es"], "sources": []}
    assert fake.calls == []  # the AI never saw these


def test_pantry_question_sends_live_status(knowledge, monkeypatch):
    fake = FakeAI(used=[])
    monkeypatch.setattr(ask, "generate_json", fake)
    answer_question("Which pantries in Plano are open?", now=MONDAY_10AM, knowledge_dir=knowledge)
    prompt = fake.calls[0][1]
    assert "Status right now:" in prompt and "Plano" in prompt


def test_new_knowledge_file_is_picked_up_without_restart(knowledge, monkeypatch):
    monkeypatch.setattr(ask, "generate_json", FakeAI(used=[1]))
    assert answer_question("SUN Bucks summer", knowledge_dir=knowledge, pantries=[])["sources"] == []
    write(knowledge, "summer.md", "SUN Bucks", "https://example.gov/sun", "SUN Bucks gives summer grocery money.")
    assert answer_question("SUN Bucks summer", knowledge_dir=knowledge, pantries=[])["sources"][0]["title"] == "SUN Bucks"


# ---------- the API endpoint ----------

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def reset_rate_limit():
    main._recent_questions.clear()


def test_ask_endpoint(monkeypatch):
    monkeypatch.setattr(main, "answer_question", lambda q: {"answer": f"echo {q}", "sources": []})
    response = client.post("/ask", json={"question": "  What is SNAP?  "})
    assert response.status_code == 200
    assert response.json() == {"answer": "echo What is SNAP?", "sources": []}


def test_ask_when_ai_is_down_points_to_211(monkeypatch):
    def broken(question):
        raise LLMUnavailable("no key")
    monkeypatch.setattr(main, "answer_question", broken)
    response = client.post("/ask", json={"question": "What is SNAP?"})
    assert response.status_code == 503 and "2-1-1" in response.json()["detail"]


@pytest.mark.parametrize("question", ["", "a", "x" * 501])
def test_ask_rejects_empty_or_huge_questions(question):
    assert client.post("/ask", json={"question": question}).status_code == 422


def test_ask_rate_limit(monkeypatch):
    monkeypatch.setattr(main, "answer_question", lambda q: {"answer": "ok", "sources": []})
    codes = [client.post("/ask", json={"question": "hi there"}).status_code for _ in range(main.ASK_LIMIT + 1)]
    assert codes[:-1] == [200] * main.ASK_LIMIT and codes[-1] == 429


def test_pantry_link_encodes_ampersand():
    from backend.ask import pantry_source
    pantry = next(p for p in main.PANTRIES if "&" in p["name"] and not p["website"])
    url = pantry_source({**pantry, "status": "open"})["url"]
    assert "&" not in url.split("query=", 1)[1]
