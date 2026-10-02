"""Checks that every on-screen text key exists in English AND Spanish, and that every
page has the shared accessibility setup (settings buttons, translations, labeled main area)."""

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
PAGES = ["index.html", "hours.html", "ask.html"]
SCRIPTS = ["app.js", "hours.js", "ask.js", "settings.js"]


def dictionary(lang):
    """Keys of STRINGS.en or STRINGS.es in i18n.js."""
    source = (FRONTEND / "i18n.js").read_text()
    block = re.search(rf"\n  {lang}: \{{(.*?)\n  \}},", source, re.DOTALL).group(1)
    return set(re.findall(r'"([\w.]+)":', block))


EN, ES = dictionary("en"), dictionary("es")


def keys_used_in_html(page):
    html = (FRONTEND / page).read_text()
    keys = set(re.findall(r'data-i18n(?:-html)?="([\w.]+)"', html))
    for attrs in re.findall(r'data-i18n-attr="([^"]+)"', html):
        keys |= {pair.split(":")[1].strip() for pair in attrs.split(";") if ":" in pair}
    return keys


def keys_used_in_js(script):
    # Skip comment lines (they mention t("key") as an example).
    source = "\n".join(line for line in (FRONTEND / script).read_text().splitlines()
                       if not line.lstrip().startswith("//"))
    keys = set(re.findall(r'\bt\(\s*"([\w.]+)"', source))
    keys |= set(re.findall(r'textIn\(\s*\w+,\s*"([\w.]+)"', source))
    keys |= set(re.findall(r'showMessage\(\["([\w.]+)"', source))
    keys |= set(re.findall(r'\["(msg\.[\w.]+)"', source))
    return keys


def test_english_and_spanish_have_the_same_keys():
    assert EN - ES == set(), "missing in Spanish"
    assert ES - EN == set(), "missing in English"


@pytest.mark.parametrize("page", PAGES)
def test_every_key_in_html_exists(page):
    assert keys_used_in_html(page) - EN == set()


@pytest.mark.parametrize("script", SCRIPTS)
def test_every_key_in_javascript_exists(script):
    assert keys_used_in_js(script) - EN == set()


@pytest.mark.parametrize("page", PAGES)
def test_every_page_has_the_shared_accessibility_setup(page):
    html = (FRONTEND / page).read_text()
    assert '<script src="i18n.js"></script>' in html and '<script src="settings.js"></script>' in html
    assert html.index("i18n.js") < html.index("settings.js")   # settings.js needs t()
    assert 'id="prefs"' in html                                 # language / large text / contrast buttons
    assert re.search(r'<main[^>]*id="main"', html)              # target for the skip link
    assert 'data-i18n="nav.map"' in html and 'data-i18n="nav.ask"' in html and 'data-i18n="nav.hours"' in html


@pytest.mark.parametrize("page", PAGES)
def test_inputs_have_labels(page):
    html = (FRONTEND / page).read_text()
    for field_id in re.findall(r'<(?:input|textarea)[^>]*\bid="([^"]+)"', html):
        labelled = re.search(rf'<label[^>]*for="{field_id}"', html) or \
            re.search(rf'<label[^>]*>(?:(?!</label>).)*id="{field_id}"', html, re.DOTALL)
        assert labelled, f"{page}: #{field_id} has no label"


def test_icon_only_buttons_have_names():
    # Buttons with only an icon need an aria-label so screen readers can say what they do.
    html = (FRONTEND / "ask.html").read_text()
    send = re.search(r'<button[^>]*id="send"[^>]*>', html).group(0)
    assert 'aria-label=' in send


def test_starter_questions_exist_in_both_languages():
    source = (FRONTEND / "i18n.js").read_text()
    block = re.search(r"const STARTER_QUESTIONS = \{(.*?)\n\};", source, re.DOTALL).group(1)
    en = re.search(r"en: \[(.*?)\]", block, re.DOTALL).group(1)
    es = re.search(r"es: \[(.*?)\]", block, re.DOTALL).group(1)
    assert len(re.findall(r'"[^"]+\?"', en)) == 3
    assert len(re.findall(r'"¿[^"]+\?"', es)) == 3
