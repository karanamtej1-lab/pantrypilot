"""Tests for backend/ask.py. The AI is replaced by a fake, so these are free and offline."""

from datetime import datetime

from pathlib import Path

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


def strip_quotes(sources):
    """Source cards now carry a quote; compare just title + url."""
    return [{"title": s["title"], "url": s["url"]} for s in sources]


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


OFF_TOPIC_PLAN = {"on_topic": False, "greeting": False, "eligibility": False,
                  "wants_pantries": False, "city": "", "queries": []}


class FakeAI:
    """Stands in for the AI. `calls` = answer requests; `plans` = search-planning requests."""
    def __init__(self, answer="Here is the answer.", used=(1,), plan=None):
        self.answer, self.used, self.calls, self.plans = answer, list(used), [], []
        self.plan = plan if plan is not None else OFF_TOPIC_PLAN

    def __call__(self, system, user, schema=None):
        if schema is ask.PLAN_SCHEMA:
            self.plans.append(user)
            return dict(self.plan)
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
    assert result["answer"] == "Here is the answer."
    assert strip_quotes(result["sources"]) == [{"title": "WIC Basics", "url": "https://example.gov/wic"}]
    assert "WIC helps pregnant women" in fake.calls[0][1]


def test_no_sources_means_not_sure_without_calling_the_ai(knowledge, monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ask, "generate_json", fake)
    english = answer_question("volcano penguins", knowledge_dir=knowledge, pantries=[])
    spanish = answer_question("¿Qué hay de los pingüinos del volcán?", knowledge_dir=knowledge, pantries=[])
    assert (english["answer"], english["sources"]) == (NOT_SURE["en"], [])
    assert (spanish["answer"], spanish["sources"]) == (NOT_SURE["es"], [])
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
    monkeypatch.setattr(main, "answer_question", lambda q, **kw: {"answer": f"echo {q}", "sources": []})
    response = client.post("/ask", json={"question": "  What is SNAP?  "})
    assert response.status_code == 200
    assert response.json() == {"answer": "echo What is SNAP?", "sources": []}


def test_ask_when_ai_is_down_points_to_211(monkeypatch):
    def broken(question, **kw):
        raise LLMUnavailable("no key")
    monkeypatch.setattr(main, "answer_question", broken)
    response = client.post("/ask", json={"question": "What is SNAP?"})
    assert response.status_code == 503 and "2-1-1" in response.json()["detail"]


@pytest.mark.parametrize("question", ["", "a", "x" * 501])
def test_ask_rejects_empty_or_huge_questions(question):
    assert client.post("/ask", json={"question": question}).status_code == 422


def test_ask_rate_limit(monkeypatch):
    monkeypatch.setattr(main, "answer_question", lambda q, **kw: {"answer": "ok", "sources": []})
    codes = [client.post("/ask", json={"question": "hi there"}).status_code for _ in range(main.ASK_LIMIT + 1)]
    assert codes[:-1] == [200] * main.ASK_LIMIT and codes[-1] == 429


def test_pantry_link_encodes_ampersand():
    from backend.ask import pantry_source
    pantry = next(p for p in main.PANTRIES if "&" in p["name"] and not p["website"])
    url = pantry_source({**pantry, "status": "open"})["url"]
    assert "&" not in url.split("query=", 1)[1]


# ---------- fixes from the 32-question eval (Oct 2) ----------

from backend.ask import ELIGIBILITY_REPLY, is_eligibility_question, pantry_source, requested_features


@pytest.mark.parametrize("question, features", [
    ("Which pantries offer Spanish support?", ["Spanish spoken"]),
    ("¿Qué despensas ofrecen ayuda en español?", ["Spanish spoken"]),
    ("Which pantries have drive-thru service?", ["drive-thru"]),
    ("any drive through pantry in Denton", ["drive-thru"]),
    ("Can I find a pantry that does not require ID?", ["no ID needed"]),
    ("pantry without an ID", ["no ID needed"]),
    ("despensa sin identificación", ["no ID needed"]),
    ("Which pantries are open now?", []),
    ("Do I need an ID?", []),  # asking ABOUT ID is not asking for "no ID"
])
def test_requested_features(question, features):
    assert requested_features(question) == features


def test_feature_filter_returns_only_marked_pantries():
    spanish = matching_pantries("Which pantries offer Spanish support?", main.PANTRIES, MONDAY_10AM, {})
    drive = matching_pantries("Which pantries have drive-thru service?", main.PANTRIES, MONDAY_10AM, {})
    no_id = matching_pantries("a pantry that does not require ID", main.PANTRIES, MONDAY_10AM, {})
    assert spanish and all(p["spanish"] is True for p in spanish)
    assert len(drive) == sum(1 for p in main.PANTRIES if p["drive_thru"] is True)
    assert no_id and all(p["id_required"] is False for p in no_id)


def test_feature_and_city_combine():
    found = matching_pantries("drive-thru pantries in Denton", main.PANTRIES, MONDAY_10AM, {})
    assert found and all(p["city"] == "Denton" and p["drive_thru"] for p in found)


def test_city_question_can_show_more_than_five():
    denton = sum(1 for p in main.PANTRIES if p["city"] == "Denton")
    assert len(matching_pantries("pantries in Denton", main.PANTRIES, MONDAY_10AM, {})) == min(denton, 10)


@pytest.mark.parametrize("question", [
    "¿Cómo puedo encontrar un banco de alimentos cerca de mí?",
    "¿Dónde puedo encontrar ayuda alimentaria en Denton?",
    "Are there food banks in Allen?",
])
def test_new_pantry_trigger_words(question):
    assert wants_pantries(question)


@pytest.mark.parametrize("question", [
    "What's the weather in Frisco today?",  # a city alone must NOT trigger pantries
    "Who won the 2024 presidential election?",
])
def test_off_topic_questions_still_do_not_trigger_pantries(question):
    assert not wants_pantries(question)


@pytest.mark.parametrize("question, spanish", [
    ("Which pantries offer Spanish support?", False),  # mentions Spanish, written in English
    ("despensas en Denton", True),                     # Spanish with no ¿ or accents
    ("¿Qué es WIC?", True),
    ("What food pantries are in Plano?", False),
])
def test_reply_language_is_decided_in_code(question, spanish):
    assert looks_spanish(question) is spanish


def test_reply_language_is_sent_to_the_ai():
    assert "Reply in: English\n" in build_user_message("Q?", [{"title": "A", "text": "a"}], MONDAY_10AM, "en")
    assert "Reply in: Spanish\n" in build_user_message("Q?", [{"title": "A", "text": "a"}], MONDAY_10AM, "es")


@pytest.mark.parametrize("question", [
    "Am I eligible for SNAP if I make $2,000 per month?",
    "Will I qualify for SNAP if I have two children?",
    "Can I get SNAP if I work 30 hours a week?",
    "Can I get food assistance if I am a college student?",
    "¿Califico para WIC si estoy embarazada?",
    "¿Puedo recibir cupones de comida?",
])
def test_eligibility_questions_are_detected(question):
    assert is_eligibility_question(question)


@pytest.mark.parametrize("question", [
    "How do I apply for SNAP in Texas?",
    "Can a pantry guarantee that I will receive food today?",
    "What is the capital of France?",
])
def test_other_questions_are_not_eligibility(question):
    assert not is_eligibility_question(question)


def test_eligibility_with_no_sources_gets_fixed_reply_not_the_ai(knowledge, monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ask, "generate_json", fake)
    # (The sample knowledge folder mentions SNAP, so these avoid that word to get zero sources.)
    en = answer_question("Am I eligible if I am unemployed?", knowledge_dir=knowledge, pantries=[])
    es = answer_question("¿Califico si gano poco?", knowledge_dir=knowledge, pantries=[])
    assert en["answer"] == ELIGIBILITY_REPLY["en"] and "Texas HHSC" in en["answer"] and "2-1-1" in en["answer"]
    assert es["answer"] == ELIGIBILITY_REPLY["es"]
    assert fake.calls == []


def test_eligibility_with_a_matching_source_still_gets_the_fixed_reply_plus_citation(knowledge, monkeypatch):
    # A matching official page must NOT turn an eligibility question into an AI answer.
    fake = FakeAI(used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("Am I eligible for SNAP if I am unemployed?", knowledge_dir=knowledge, pantries=[])
    assert result["answer"] == ELIGIBILITY_REPLY["en"]
    assert {"title": "SNAP Basics", "url": "https://example.gov/snap"} in result["sources"]
    assert fake.calls == []


def test_off_topic_still_gets_exact_not_sure(knowledge, monkeypatch):
    monkeypatch.setattr(ask, "generate_json", FakeAI())
    assert answer_question("How do I learn Python?", knowledge_dir=knowledge, pantries=[])["answer"] == NOT_SURE["en"]


def test_id_wording_leaves_nothing_to_invent():
    pantry = {**next(p for p in main.PANTRIES if p["id_required"] is True), "status": "open"}
    assert "ID required: yes (the data does not say which kind of ID)" in pantry_source(pantry)["text"]
    unknown = {**next(p for p in main.PANTRIES if p["id_required"] is None), "status": "open"}
    assert "ID required: not listed" in pantry_source(unknown)["text"]


def test_prompt_forbids_embellishing():
    assert 'do not say "photo ID"' in ask.SYSTEM_PROMPT
    assert "Reply in:" in ask.SYSTEM_PROMPT


def test_literal_backslash_n_becomes_a_line_break(knowledge, monkeypatch):
    monkeypatch.setattr(ask, "generate_json", FakeAI(answer="Line one.\\n- Line two", used=[1]))
    result = answer_question("What does WIC cover?", knowledge_dir=knowledge, pantries=[])
    assert result["answer"] == "Line one.\n- Line two"


def test_search_note_tells_ai_what_filter_was_used(knowledge, monkeypatch):
    fake = FakeAI(used=[])
    monkeypatch.setattr(ask, "generate_json", fake)
    answer_question("Which pantries offer Spanish support?", now=MONDAY_10AM, knowledge_dir=knowledge)
    assert "Search note: pantries marked 'Spanish spoken' in our data" in fake.calls[0][1]


# ---------- general food-help questions (live bug report, Oct 2) ----------

@pytest.mark.parametrize("question", [
    "how do i get food",
    "Where can I find free food?",
    "I'm hungry",
    "¿Dónde puedo conseguir comida?",
    "necesito comida para mis hijos",
])
def test_general_food_need_uses_the_pantry_data(question):
    assert wants_pantries(question)


@pytest.mark.parametrize("question", [
    "How do I get food stamps?",                            # SNAP, not pantries
    "Can I get food assistance if I am a college student?",  # keeps the fixed eligibility reply
    "What is the capital of France?",
    "What's the weather in Frisco today?",
])
def test_food_need_rule_does_not_catch_other_questions(question):
    assert not wants_pantries(question)


def test_how_do_i_get_food_reaches_the_ai_with_cited_pantries(knowledge, monkeypatch):
    fake = FakeAI(answer="Here are pantries open now.", used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("how do i get food", now=MONDAY_10AM, knowledge_dir=knowledge)
    assert fake.calls, "the question should reach the AI"
    assert "Status right now:" in fake.calls[0][1]        # grounded in the pantry list
    assert result["sources"]                              # and cited


def test_spanish_wic_question_reaches_the_ai_when_a_wic_source_exists(knowledge, monkeypatch):
    # The `knowledge` fixture includes a WIC source file.
    fake = FakeAI(answer="WIC ayuda a familias.", used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("¿Qué es WIC y quién puede recibirlo?", knowledge_dir=knowledge, pantries=[])
    assert "WIC helps pregnant women" in fake.calls[0][1]   # the trusted WIC text was retrieved
    assert "Reply in: Spanish" in fake.calls[0][1]
    assert strip_quotes(result["sources"]) == [{"title": "WIC Basics", "url": "https://example.gov/wic"}]


def test_spanish_wic_question_without_a_wic_source_still_falls_back(tmp_path, monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("¿Qué es WIC y quién puede recibirlo?", knowledge_dir=tmp_path, pantries=[])
    assert (result["answer"], result["sources"]) == (NOT_SURE["es"], [])
    assert fake.calls == []   # grounding rule: no trusted source -> the AI is never asked


def test_unrelated_question_still_gets_the_safe_fallback(knowledge, monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("What is the capital of France?", knowledge_dir=knowledge)
    assert (result["answer"], result["sources"]) == (NOT_SURE["en"], [])
    assert fake.calls == []


# ---------- the real official sources in knowledge/ (Oct 2) ----------

from backend.ask import KNOWLEDGE_DIR

WIC_SOURCE = {"title": "Apply for WIC - Texas WIC (Texas Health and Human Services)",
              "url": "https://www.texaswic.org/apply"}
SNAP_SOURCE = {"title": "SNAP Food Benefits - Texas Health and Human Services",
               "url": "https://www.hhs.texas.gov/services/food/snap-food-benefits"}


@pytest.mark.parametrize("name, url", [("wic.md", WIC_SOURCE["url"]), ("snap.md", SNAP_SOURCE["url"])])
def test_official_sources_use_the_example_format(name, url):
    title, parsed_url, body = parse_knowledge_file(KNOWLEDGE_DIR / name)
    assert parsed_url == url and title
    assert "Only Texas" in body          # the file itself says only the agency decides


def test_spanish_wic_question_retrieves_wic_source_and_reaches_ai(monkeypatch):
    fake = FakeAI(answer="WIC es para mujeres embarazadas y niños menores de 5 años.", used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("¿Qué es WIC y quién puede recibirlo?", now=MONDAY_10AM, pantries=[])
    prompt = fake.calls[0][1]
    assert "WIC is for pregnant, postpartum and breastfeeding women" in prompt   # official text sent
    assert "Reply in: Spanish" in prompt
    assert strip_quotes(result["sources"]) == [WIC_SOURCE]                       # cited


@pytest.mark.parametrize("question", ["How do I apply for SNAP in Texas?", "What is SNAP?", "How do I get food stamps?",
                                      "¿Cómo solicito SNAP en Texas?"])
def test_basic_snap_questions_retrieve_the_snap_source(question, monkeypatch):
    fake = FakeAI(answer="Apply at YourTexasBenefits.com.", used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    chunks, idf = ask.knowledge_index()
    assert SNAP_SOURCE["title"] in {c["title"] for c in top_chunks(question, chunks, idf)}
    result = answer_question(question, now=MONDAY_10AM, pantries=[])
    assert "Apply at YourTexasBenefits.com" in fake.calls[0][1]
    assert result["sources"] and result["sources"][0]["url"].startswith("https://")


@pytest.mark.parametrize("question", [
    "Who is the richest person in the world?",   # "person" appears in the SNAP page; must not count
    "What is the capital of France?",
    "How do I learn Python?",
    "What's the weather in Frisco today?",
])
def test_unsupported_questions_still_get_the_211_fallback(question, monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ask, "generate_json", fake)
    assert answer_question(question, now=MONDAY_10AM)["answer"] == NOT_SURE["en"]
    assert fake.calls == []


@pytest.mark.parametrize("question, lang", [
    ("Am I eligible for SNAP if I make $2,000 per month?", "en"),
    ("Can I get food assistance if I am a college student?", "en"),
    ("¿Califico para WIC si estoy embarazada?", "es"),
])
def test_eligibility_questions_get_the_fixed_reply_with_official_citation(question, lang, monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question(question, now=MONDAY_10AM)
    assert result["answer"] == ELIGIBILITY_REPLY[lang]
    assert result["sources"] and all(s in (WIC_SOURCE, SNAP_SOURCE) for s in result["sources"])
    assert fake.calls == []   # the AI never sees eligibility questions next to the income charts


def test_pantry_questions_are_not_padded_with_program_pages(monkeypatch):
    fake = FakeAI(used=[])
    monkeypatch.setattr(ask, "generate_json", fake)
    answer_question("How can I find a food pantry near me?", now=MONDAY_10AM)
    prompt = fake.calls[0][1]
    assert "Status right now:" in prompt and "SNAP Food Benefits" not in prompt


@pytest.mark.parametrize("question, expected", [
    ("Am I eligible for SNAP if I make $2,000 per month?", [SNAP_SOURCE]),
    ("¿Califico para WIC si estoy embarazada?", [WIC_SOURCE]),
])
def test_eligibility_cites_the_program_it_names(question, expected, monkeypatch):
    monkeypatch.setattr(ask, "generate_json", FakeAI())
    assert answer_question(question, now=MONDAY_10AM)["sources"] == expected


# ---------- Simplicity-style pipeline: greeting, planner, strict citations ----------

from backend.ask import best_quote, is_greeting, link_citations, plan_search


@pytest.mark.parametrize("question, expected", [
    ("hi", True), ("Hello!", True), ("hola", True), ("buenos días", True), ("hey there", True),
    ("hi, which pantries are open?", False), ("What is WIC?", False),
])
def test_is_greeting(question, expected):
    assert is_greeting(question) is expected


def test_greeting_gets_a_friendly_reply_without_the_ai(monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ask, "generate_json", fake)
    assert answer_question("hi")["answer"] == ask.GREETING_REPLY["en"]
    assert answer_question("hola")["answer"] == ask.GREETING_REPLY["es"]
    assert fake.calls == [] and fake.plans == []


def test_planner_finds_official_source_when_keywords_miss(monkeypatch):
    # No keyword hits, but the planner suggests a search; code retrieves the TRUSTED WIC page.
    plan = {"on_topic": True, "greeting": False, "eligibility": False, "wants_pantries": False,
            "city": "", "queries": ["WIC who can apply"]}
    fake = FakeAI(answer="WIC serves pregnant women and young children [1].", used=[1], plan=plan)
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("my baby needs formula, can anyone help?", now=MONDAY_10AM, pantries=[])
    assert fake.plans and fake.calls
    assert "WIC is for pregnant, postpartum and breastfeeding women" in fake.calls[0][1]
    assert strip_quotes(result["sources"]) == [WIC_SOURCE]
    assert result["details"]["used_planner"] and result["details"]["planned_queries"] == ["WIC who can apply"]


def test_planner_cannot_add_facts_only_search_words(monkeypatch):
    # Even a planner "query" that states a false fact only CHOOSES official text:
    # the planner's own words never appear among the sources the AI answers from.
    fake_fact = "everyone qualifies for free money"
    plan = {"on_topic": True, "greeting": False, "eligibility": False, "wants_pantries": False,
            "city": "", "queries": [fake_fact]}
    fake = FakeAI(used=[1], plan=plan)
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("tell me something nice", now=MONDAY_10AM, pantries=[])
    sources_section = fake.calls[0][1].split("SOURCES:")[1].split("QUESTION:")[0]
    assert fake_fact not in sources_section
    assert all(s in (WIC_SOURCE, SNAP_SOURCE) for s in strip_quotes(result["sources"]))


def test_planner_failure_falls_back_safely(monkeypatch):
    def broken(system, user, schema=None):
        raise LLMUnavailable("down")
    monkeypatch.setattr(ask, "generate_json", broken)
    assert answer_question("something unusual about food help", pantries=[])["answer"] == NOT_SURE["en"]


def test_planner_garbage_is_ignored(monkeypatch):
    monkeypatch.setattr(ask, "generate_json", lambda s, u, schema=None: {"on_topic": "yes please"})
    assert plan_search("anything") is None


def test_planner_eligibility_flag_keeps_the_fixed_reply(monkeypatch):
    plan = {"on_topic": True, "greeting": False, "eligibility": True, "wants_pantries": False,
            "city": "", "queries": ["SNAP income limits"]}
    fake = FakeAI(plan=plan)
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("would they help me with my paycheck situation", now=MONDAY_10AM, pantries=[])
    assert result["answer"] == ELIGIBILITY_REPLY["en"] and fake.calls == []


def test_planner_city_narrows_pantries(monkeypatch):
    plan = {"on_topic": True, "greeting": False, "eligibility": False, "wants_pantries": True,
            "city": "Denton", "queries": []}
    fake = FakeAI(used=[1], plan=plan)
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("my kids are starving tonight, I'm by the university", now=MONDAY_10AM)
    assert "Denton" in fake.calls[0][1] and result["details"]["pantries_checked"] > 0


def test_planner_is_not_used_when_keywords_already_found_something(monkeypatch):
    fake = FakeAI(used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    answer_question("How do I apply for SNAP in Texas?", now=MONDAY_10AM, pantries=[])
    assert fake.plans == []   # one AI call, not two


# ---------- strict citations (ported from Simplicity's citationParser) ----------

SRC = [{"title": "A", "url": "u1", "text": "Alpha fact here."},
       {"title": "B", "url": "u2", "text": "Beta fact here."},
       {"title": "A", "url": "u1", "text": "Another alpha chunk."}]


def test_citations_are_renumbered_to_the_returned_list():
    text, cited = link_citations("Beta [2]. Alpha [1].", [], SRC, "q")
    assert text == "Beta [1]. Alpha [2]."
    assert [c["title"] for c in cited] == ["B", "A"]


def test_invalid_citation_numbers_are_dropped_and_text_kept():
    text, cited = link_citations("Fact [9]. Also [2][7].", [], SRC, "q")
    assert text == "Fact . Also [1]."
    assert [c["title"] for c in cited] == ["B"]


def test_non_citation_brackets_are_never_touched():
    original = "Bring ID [Note] and $10,000-40,000 [3.14] [x]."
    text, _ = link_citations(original, [], SRC, "q")
    assert text == original


def test_two_chunks_of_the_same_page_become_one_citation():
    text, cited = link_citations("One [1]. Two [3].", [], SRC, "q")
    assert text == "One [1]. Two [1]." and len(cited) == 1


def test_used_sources_without_markers_are_still_cited():
    _, cited = link_citations("No markers here.", [2], SRC, "q")
    assert [c["title"] for c in cited] == ["B"]


def test_quote_is_word_for_word_from_the_source():
    text = "WIC is for pregnant women. Recipes and cooking demonstrations are also available."
    quote = best_quote(text, "what does WIC offer for cooking recipes")
    assert quote == "Recipes and cooking demonstrations are also available." and quote in text


def test_answer_quotes_come_from_the_official_text(monkeypatch):
    fake = FakeAI(answer="Apply online [1].", used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("How do I apply for SNAP in Texas?", now=MONDAY_10AM, pantries=[])
    official = (KNOWLEDGE_DIR / "snap.md").read_text()
    assert result["sources"][0]["quote"].rstrip("…") in official


TWO_ONE_ONE_SOURCE = {"title": "About 2-1-1 Texas - Texas Health and Human Services Commission",
                      "url": "https://www.211texas.org/about-2-1-1/"}


@pytest.mark.parametrize("question", ["What is 2-1-1 Texas used for?", "¿Qué es el 2-1-1 de Texas?", "what is 211"])
def test_211_questions_retrieve_the_official_211_source(question, monkeypatch):
    fake = FakeAI(answer="2-1-1 is a free hotline [1].", used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question(question, now=MONDAY_10AM, pantries=[])
    assert "free, anonymous social service hotline" in fake.calls[0][1]
    assert TWO_ONE_ONE_SOURCE in strip_quotes(result["sources"])
    assert fake.plans == []   # matched by keyword; no planning call needed


def test_quotes_skip_the_provenance_note_and_pantry_name_lines():
    doc = "Text below is copied word for word from the official Texas WIC website. WIC is for pregnant women and families with children up to age 5."
    assert best_quote(doc, "who can get WIC").startswith("WIC is for pregnant")
    pantry = "Name: Little Free Pantry\nAddress: 110 E Davis St, McKinney\nStatus right now: OPEN NOW\nHours: Open 24 hours, every day"
    assert not best_quote(pantry, "how do i get food").startswith(("Name:", "Address:"))


def test_provenance_note_is_never_searched_quoted_or_sent():
    chunks = load_chunks(KNOWLEDGE_DIR)
    assert chunks and not any("Text below is copied" in c["text"] for c in chunks)
    assert not any("Sections appear in a different order" in c["text"] for c in chunks)


@pytest.mark.parametrize("question, expected_start", [
    ("How do I apply for SNAP in Texas?", "Apply at YourTexasBenefits.com"),
    ("¿Qué es WIC y quién puede recibirlo?", "WIC"),
])
def test_live_style_quotes_are_useful_official_sentences(question, expected_start, monkeypatch):
    monkeypatch.setattr(ask, "generate_json", FakeAI(answer="x [1].", used=[1]))
    quote = answer_question(question, now=MONDAY_10AM, pantries=[])["sources"][0]["quote"]
    assert quote and quote.startswith(expected_start)


# ---------- follow-up questions and pantry action buttons ----------

def test_follow_up_uses_the_earlier_question_through_the_planner(monkeypatch):
    plan = {"on_topic": True, "greeting": False, "eligibility": False, "wants_pantries": True,
            "city": "Denton", "queries": []}
    fake = FakeAI(used=[1], plan=plan)
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question("what about the other city?", now=MONDAY_10AM,
                             previous="Which pantries are open today in Plano?")
    assert "EARLIER QUESTION:\nWhich pantries are open today in Plano?" in fake.plans[0]
    assert "EARLIER QUESTION (for context only)" in fake.calls[0][1]
    assert "Denton" in fake.calls[0][1] and result["details"]["pantries_checked"] > 0


def test_earlier_question_is_ignored_when_the_new_one_stands_alone(monkeypatch):
    fake = FakeAI(used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    answer_question("How do I apply for SNAP in Texas?", now=MONDAY_10AM, pantries=[], previous="hi")
    assert fake.plans == [] and "EARLIER QUESTION" not in fake.calls[0][1]


def test_pantry_cards_have_call_and_directions(monkeypatch):
    fake = FakeAI(answer="Go here [1].", used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    pantries = [p for p in main.PANTRIES if p["name"] == "Salvation Army Denton"]
    card = answer_question("Which pantries are in Denton?", now=MONDAY_10AM, pantries=pantries)["sources"][0]
    assert card["kind"] == "pantry" and card["phone"] == "(940) 566-3800"
    assert card["directions"].startswith("https://www.google.com/maps/dir/?api=1&destination=")
    assert "1508+E+McKinney+St" in card["directions"]


def test_official_cards_are_marked_official(monkeypatch):
    monkeypatch.setattr(ask, "generate_json", FakeAI(answer="x [1].", used=[1]))
    card = answer_question("How do I apply for SNAP in Texas?", now=MONDAY_10AM, pantries=[])["sources"][0]
    assert card["kind"] == "official" and "phone" not in card


def _suggested_questions():
    import re as _re
    source = (Path(__file__).resolve().parent.parent / "frontend" / "i18n.js").read_text()
    block = source[source.index("const SUGGESTED_QUESTIONS"):source.index("// ---------- saving choices")]
    return sorted(set(_re.findall(r'"([^"]+\?)"', block)))


@pytest.mark.parametrize("question", _suggested_questions())
def test_every_suggested_question_is_answerable(question, monkeypatch):
    # A suggestion must never lead to "not sure": it has to find an official source or pantries.
    fake = FakeAI(answer="ok [1].", used=[1])
    monkeypatch.setattr(ask, "generate_json", fake)
    result = answer_question(question, now=MONDAY_10AM)
    assert result["answer"] not in NOT_SURE.values(), question
    assert result["sources"], question
