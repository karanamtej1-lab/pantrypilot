// Shared by every page: display settings (language, larger text, high contrast),
// the "skip to main content" link, and the offline service worker.
// Needs i18n.js to be loaded first.

const LARGE_KEY = "pantrypilot.largeText";
const CONTRAST_KEY = "pantrypilot.highContrast";
const html = document.documentElement;

// Apply saved choices right away (this file loads in <head>) so the page never
// flashes in the wrong size or colors first.
html.classList.toggle("large-text", storageGet(LARGE_KEY) === "1");
const savedContrast = storageGet(CONTRAST_KEY);
html.classList.toggle(
  "high-contrast",
  // No choice saved yet? Follow the phone's "increase contrast" setting.
  savedContrast === "1" || (savedContrast === null && window.matchMedia("(prefers-contrast: more)").matches),
);

const ICONS = {
  large: '<svg viewBox="0 0 24 24" aria-hidden="true"><text x="1" y="18" font-size="13" font-weight="700" fill="currentColor" font-family="system-ui, sans-serif">A</text><text x="11" y="18" font-size="19" font-weight="700" fill="currentColor" font-family="system-ui, sans-serif">A</text></svg>',
  contrast: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/></svg>',
};

function makeToggle(className, iconSvg, isOn, onToggle) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `pref ${className}`;
  button.innerHTML = iconSvg;
  button.setAttribute("aria-pressed", String(isOn()));
  button.addEventListener("click", () => {
    onToggle();
    button.setAttribute("aria-pressed", String(isOn()));
    document.dispatchEvent(new CustomEvent("pp:displaychange")); // e.g. the map redraws pin colors
  });
  return button;
}

function buildPreferences() {
  const slot = document.querySelector("#prefs");
  if (!slot) return;
  slot.setAttribute("role", "group");

  const langButton = document.createElement("button");
  langButton.type = "button";
  langButton.className = "pref pref-lang";
  langButton.addEventListener("click", () => setLang(getLang() === "en" ? "es" : "en"));

  const largeButton = makeToggle("pref-icon", ICONS.large,
    () => html.classList.contains("large-text"),
    () => storageSet(LARGE_KEY, html.classList.toggle("large-text") ? "1" : "0"));

  const contrastButton = makeToggle("pref-icon", ICONS.contrast,
    () => html.classList.contains("high-contrast"),
    () => storageSet(CONTRAST_KEY, html.classList.toggle("high-contrast") ? "1" : "0"));

  function label() {
    slot.setAttribute("aria-label", t("settings.group"));
    // The button shows the OTHER language, written in that language, so people can find it.
    langButton.textContent = t("settings.lang");
    langButton.lang = getLang() === "en" ? "es" : "en";
    langButton.setAttribute("aria-label", t("settings.langLabel"));
    for (const [button, key] of [[largeButton, "settings.large"], [contrastButton, "settings.contrast"]]) {
      button.setAttribute("aria-label", t(key));
      button.title = t(key);  // tooltip for mouse users
    }
  }
  label();
  document.addEventListener("pp:languagechange", label);
  slot.replaceChildren(langButton, largeButton, contrastButton);
}

function addSkipLink() {
  const main = document.querySelector("main");
  if (!main) return;
  main.id ||= "main";
  main.tabIndex = -1; // lets the skip link move focus into <main>
  const link = document.createElement("a");
  link.className = "skip-link";
  link.href = `#${main.id}`;
  link.dataset.i18n = "skip";
  document.body.prepend(link);
}

document.addEventListener("DOMContentLoaded", () => {
  addSkipLink();
  buildPreferences();
  applyTranslations();
});

// Offline support. Service workers only run on https:// or localhost.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => console.warn("Offline mode unavailable:", error));
  });
}
