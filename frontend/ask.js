// Ask page: sends a question to POST /ask and shows the answer with its sources.
// Plain JavaScript. Nothing is saved; refreshing the page clears the chat.

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

// Show **bold** as real bold text. Built from text nodes, never innerHTML,
// so an answer can't inject code into the page.
function withBold(text) {
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 ? el("strong", {}, part) : part));
}

function addMessage(role, ...content) {
  const item = el("li", { class: `msg ${role}` }, el("div", { class: "bubble" }, ...content));
  messages.append(item);
  item.scrollIntoView({ behavior: "smooth", block: "end" });
  return item;
}

function sourcesList(sources, spanish) {
  if (!sources.length) return null;
  return el("ul", { class: "sources", "aria-label": spanish ? "Fuentes" : "Sources" },
    el("li", { class: "sources-label" }, spanish ? "Fuentes" : "Sources"),
    ...sources.map((source, i) => {
      const number = el("span", { class: "num", "aria-hidden": "true" }, String(i + 1));
      // Every answer shows where it came from; a source without a link is shown as text.
      return el("li", {}, source.url
        ? el("a", { href: source.url, target: "_blank", rel: "noopener" }, number, source.title)
        : el("span", {}, number, source.title));
    }),
  );
}

async function ask(question) {
  const spanish = isSpanish(question);
  document.querySelector("#intro").hidden = true;
  addMessage("user", question);
  const waiting = addMessage("assistant",
    el("span", { class: "visually-hidden" }, spanish ? "Buscando en fuentes confiables…" : "Looking through trusted sources…"),
    el("span", { class: "thinking", "aria-hidden": "true" }, el("span"), el("span"), el("span")),
  );

  sendButton.disabled = true;
  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const body = await response.json().catch(() => ({}));
    waiting.remove();

    if (!response.ok) {
      const fallback = spanish
        ? "Algo salió mal. Intente de nuevo o llame al 2-1-1."
        : "Something went wrong. Please try again, or dial 2-1-1.";
      addMessage("assistant error", typeof body.detail === "string" ? body.detail : fallback);
      return;
    }
    addMessage("assistant", ...withBold(body.answer), sourcesList(body.sources || [], spanish));
  } catch (error) {
    waiting.remove();
    addMessage("assistant error", spanish
      ? "No hay conexión. Revise su internet o llame al 2-1-1."
      : "Couldn't connect. Check your internet, or dial 2-1-1.");
  } finally {
    sendButton.disabled = false;
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

for (const button of document.querySelectorAll(".starter")) {
  button.addEventListener("click", () => ask(button.textContent.trim()));
}
