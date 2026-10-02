// Ask page: sends a question to POST /ask and shows the answer with its sources.
// Plain JavaScript. Nothing is saved; refreshing the page clears the chat.
// Page text comes from i18n.js. Labels inside a conversation (Sources/Fuentes, "thinking",
// errors) follow the QUESTION's language, so they always match the answer next to them.

const messages = document.querySelector("#messages");
const form = document.querySelector("#composer");
const input = document.querySelector("#question");
const sendButton = document.querySelector("#send");

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

// Is this Spanish? Used only for the labels we add ("Sources" / "Fuentes").
function isSpanish(text) {
  return /[¿¡ñ]/i.test(text) || /\b(qué|cómo|dónde|cuándo|puedo|necesito|despensas?)\b/i.test(text);
}

// Text in a specific language (not the page language), for labels that match a question.
function textIn(lang, key) {
  return STRINGS[lang][key] ?? STRINGS.en[key];
}

// Show **bold** as real bold text. Built from text nodes, never innerHTML,
// so an answer can't inject code into the page.
function withBold(text) {
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 ? el("strong", {}, part) : part));
}

// `lang` on each bubble lets screen readers read Spanish answers with a Spanish voice.
function addMessage(role, lang, ...content) {
  const item = el("li", { class: `msg ${role}`, lang }, el("div", { class: "bubble" }, ...content));
  messages.append(item);
  item.scrollIntoView({ behavior: "smooth", block: "end" });
  return item;
}

function sourcesList(sources, lang) {
  if (!sources.length) return null;
  const label = textIn(lang, "ask.sources");
  return el("ul", { class: "sources", "aria-label": label },
    el("li", { class: "sources-label" }, label),
    ...sources.map((source, i) => {
      const number = el("span", { class: "num", "aria-hidden": "true" }, String(i + 1));
      // Every answer shows where it came from; a source without a link is shown as text.
      return el("li", {}, source.url
        ? el("a", { href: source.url, target: "_blank", rel: "noopener" }, number, source.title)
        : el("span", {}, number, source.title));
    }),
  );
}

// Same messages as before, now in the question's language for the common cases.
function errorText(status, body, lang) {
  if (status === 429) return textIn(lang, "ask.errTooMany");
  if (status === 503) return textIn(lang, "ask.errUnavailable");
  return typeof body.detail === "string" ? body.detail : textIn(lang, "ask.errGeneric");
}

async function ask(question) {
  const lang = isSpanish(question) ? "es" : "en";
  document.querySelector("#intro").hidden = true;
  addMessage("user", lang, question);
  const waiting = addMessage("assistant", lang,
    el("span", { class: "visually-hidden" }, textIn(lang, "ask.thinking")),
    el("span", { class: "thinking", "aria-hidden": "true" }, el("span"), el("span"), el("span")),
  );

  sendButton.disabled = true;
  messages.setAttribute("aria-busy", "true");
  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const body = await response.json().catch(() => ({}));
    waiting.remove();

    if (!response.ok) {
      addMessage("assistant error", lang, errorText(response.status, body, lang));
      return;
    }
    addMessage("assistant", lang, ...withBold(body.answer), sourcesList(body.sources || [], lang));
  } catch (error) {
    waiting.remove();
    addMessage("assistant error", lang, textIn(lang, "ask.errNetwork"));
  } finally {
    sendButton.disabled = false;
    messages.removeAttribute("aria-busy");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (question.length < 2 || sendButton.disabled) return;
  input.value = "";
  resize();
  ask(question);
});

// Enter sends; Shift+Enter makes a new line.
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

// The text box grows as you type (up to a limit set in CSS).
function resize() {
  input.style.height = "auto";
  input.style.height = `${input.scrollHeight}px`;
  input.style.overflowY = input.scrollHeight > 140 ? "auto" : "hidden";
}
input.addEventListener("input", resize);

// Starter questions: the page language's questions first, then the other language's.
function drawStarters() {
  const first = getLang();
  const second = first === "en" ? "es" : "en";
  const buttons = [first, second].flatMap((lang) => STARTER_QUESTIONS[lang].map((question) => {
    const button = el("button", { type: "button", class: "starter", lang }, question);
    button.addEventListener("click", () => {
      // The intro (and this button) disappears, so put keyboard focus somewhere useful.
      input.focus();
      ask(question);
    });
    return button;
  }));
  document.querySelector("#starters").replaceChildren(...buttons);
}

drawStarters();
document.addEventListener("pp:languagechange", drawStarters);
