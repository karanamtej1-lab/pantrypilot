// PantryPilot map page: plain JavaScript, no frameworks.
// It asks our FastAPI backend (/pantries) for data and draws the map, card, and list.
// Every word on screen comes from i18n.js through t("key").

const FRISCO = [33.1507, -96.8236];
const REFRESH_MINUTES = 5; // re-check open/closed status this often

// When there's no location to sort by distance, show open pantries first.
const STATUS_ORDER = ["open", "later_today", "appointment", "closed", "unknown", "offline"];
const DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

// Everything the page knows, in one place.
const state = {
  filters: { open_now: false, no_id: false, drive_thru: false, spanish: false },
  origin: null,        // { zip } or { lat, lng }
  pantries: [],
  selectedId: null,
  offline: false,
  checkedAt: null,
  message: null,       // { key, vars } so it can be re-translated
};
let lastListButton = null; // where to put keyboard focus back when the card closes

// ---------- small helpers ----------

// Build an element safely. Text always goes in with textContent, never innerHTML,
// so a pantry name can never inject code into the page.
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

function $(selector) {
  return document.querySelector(selector);
}

// Messages are stored as keys, so switching language re-translates them.
function showMessage(...parts) {
  state.message = parts.length ? parts : null;
  drawMessage();
}

function drawMessage() {
  $("#message").textContent = state.message ? state.message.map(([key, vars]) => t(key, vars)).join(" ") : "";
}

// Colors come from the CSS, so high-contrast mode changes the pins too.
function cssColor(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
}

function statusColor(status) {
  return { open: cssColor("open"), later_today: cssColor("later"), appointment: cssColor("appointment"),
           closed: cssColor("closed") }[status] || "#ffffff";
}

// ---------- turning a schedule into readable text ----------

// "16:30" -> "4:30 PM" (or "4:30 p. m." in Spanish)
function formatTime(hhmm) {
  let [hours, minutes] = hhmm.split(":").map(Number);
  const suffix = t(hours >= 12 ? "time.pm" : "time.am");
  hours = hours % 12 || 12;
  return minutes ? `${hours}:${String(minutes).padStart(2, "0")} ${suffix}` : `${hours} ${suffix}`;
}

// ["mon"..."fri"] -> "Mon–Fri"; ["tue","thu"] -> "Tue & Thu" ("mar y jue" in Spanish)
function formatDays(days) {
  const sorted = [...days].sort((a, b) => DAY_ORDER.indexOf(a) - DAY_ORDER.indexOf(b));
  const indexes = sorted.map((d) => DAY_ORDER.indexOf(d));
  const consecutive = indexes.every((n, i) => i === 0 || n === indexes[i - 1] + 1);
  const label = (d) => t(`day.${d}`);
  if (sorted.length >= 3 && consecutive) return `${label(sorted[0])}–${label(sorted[sorted.length - 1])}`;
  const labels = sorted.map(label);
  return labels.length <= 2 ? labels.join(` ${t("and")} `) : labels.join(", ");
}

function formatWeeks(weeks) {
  return weeks.map((w) => t(`week.${w}`)).join(` ${t("and")} `);
}

function formatMonths(months) {
  const consecutive = months.every((m, i) => i === 0 || m === months[i - 1] + 1);
  if (months.length >= 3 && consecutive) return `${t(`month.${months[0]}`)}–${t(`month.${months[months.length - 1]}`)}`;
  return months.map((m) => t(`month.${m}`)).join(", ");
}

// One rule -> "1st & 3rd Sat: 9 AM–11 AM (appointment)"
function formatRule(rule) {
  let when = formatDays(rule.days);
  if (rule.weeks) when = `${formatWeeks(rule.weeks)} ${when}`;
  if (rule.months) when = `${formatMonths(rule.months)}: ${when}`;
  const times = rule.windows.map((w) => `${formatTime(w.start)}–${formatTime(w.end)}`).join(", ");
  return `${when}: ${times}${rule.appointment ? t("hours.apptTag") : ""}`;
}

function hoursLines(pantry) {
  const schedule = pantry.schedule;
  if (schedule.type === "always_open") return [t("hours.always")];
  if (schedule.type === "appointment_only") return [t("hours.apptOnly")];
  if (schedule.type === "unknown") return [t("hours.unknown")];
  const lines = schedule.rules.map(formatRule);
  if (schedule.appointment_available) lines.push(t("hours.alsoAppt"));
  return lines;
}

function formatVerified(dateText) {
  if (!dateText) return t("details.notVerified");
  const [year, month, day] = dateText.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(locale(), { month: "short", day: "numeric", year: "numeric" });
}

// "(972) 335-9495" -> "tel:+19723359495"
function phoneLink(phone) {
  const digits = phone.replace(/\D/g, "");
  return digits.length === 10 ? `tel:+1${digits}` : `tel:${digits}`;
}

function directionsLink(pantry) {
  const destination = pantry.address
    ? `${pantry.address}, ${pantry.city}, TX ${pantry.zip || ""}`
    : `${pantry.lat},${pantry.lng}`;
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;
}

function statusBadge(status) {
  const dotClass = status === "offline" ? "unknown" : status;
  return el("span", { class: "status" },
    el("span", { class: `dot ${dotClass}`, "aria-hidden": "true" }),
    t(`status.${status}`));
}

// Straight-line miles (same formula as backend/geo.py), used only when offline.
function milesBetween(lat1, lng1, lat2, lng2) {
  const rad = (d) => (d * Math.PI) / 180;
  const a = Math.sin(rad(lat2 - lat1) / 2) ** 2 +
    Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lng2 - lng1) / 2) ** 2;
  return 2 * 3958.8 * Math.asin(Math.sqrt(a));
}

// ---------- the map ----------

const map = L.map("map", { zoomControl: false }).setView(FRISCO, 11);

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

let zoomControl = null;
function labelMap() {
  if (zoomControl) zoomControl.remove();
  zoomControl = L.control.zoom({ zoomInTitle: t("map.zoomIn"), zoomOutTitle: t("map.zoomOut") }).addTo(map);
  const container = map.getContainer();
  container.setAttribute("role", "region");                 // Leaflet makes the map focusable for arrow-key panning;
  container.setAttribute("aria-label", t("map.region"));    // this gives it a name screen readers can say.
}
labelMap();

const pinLayer = L.layerGroup().addTo(map);
let youAreHere = null;

function drawPins() {
  pinLayer.clearLayers();
  const highContrast = document.documentElement.classList.contains("high-contrast");
  for (const pantry of state.pantries) {
    if (pantry.lat == null || pantry.lng == null) continue;
    const selected = pantry.id === state.selectedId;
    const hollow = pantry.status === "unknown" || pantry.status === "offline";
    const pin = L.circleMarker([pantry.lat, pantry.lng], {
      radius: selected ? 14 : 10,
      color: hollow || highContrast ? "#000000" : "#ffffff",
      weight: selected ? 4 : 2.5,
      dashArray: hollow ? "3 3" : null,
      fillColor: statusColor(pantry.status),
      fillOpacity: 1,
    });
    pin.bindTooltip(`${pantry.name}: ${t(`status.${pantry.status}`)}`);
    pin.on("click", () => selectPantry(pantry.id, { scroll: true }));
    pin.addTo(pinLayer);
  }
}

function showYouAreHere(lat, lng) {
  if (youAreHere) youAreHere.remove();
  youAreHere = L.circleMarker([lat, lng], {
    radius: 8, color: "#1e2a2c", weight: 3, fillColor: "#ffffff", fillOpacity: 1,
  }).bindTooltip(t("map.youAreHere")).addTo(map);
  map.setView([lat, lng], 12);
}

// ---------- the details card ----------

function drawDetails() {
  const card = $("#details");
  const pantry = state.pantries.find((p) => p.id === state.selectedId);
  if (!pantry) {
    card.hidden = true;
    card.replaceChildren();
    return;
  }

  const requirements = [];
  if (pantry.id_required === true) requirements.push(t("details.idYes"));
  if (pantry.id_required === false) requirements.push(t("details.idNo"));
  if (pantry.id_required == null) requirements.push(t("details.idUnknown"));
  if (pantry.serves) requirements.push(t("details.serves", { who: pantry.serves }));
  for (const note of pantry.notes) requirements.push(note);
  if (pantry.drive_thru) requirements.push(t("details.driveThru"));
  if (pantry.spanish) requirements.push(t("details.spanish"));

  const place = [pantry.address, pantry.city].filter(Boolean).join(", ");
  const showOriginalText = pantry.schedule.type === "unknown" && !/call( ahead)? for hours/i.test(pantry.hours_text);

  const actions = el("div", { class: "actions" },
    pantry.phone && el("a", { class: "btn", href: phoneLink(pantry.phone) }, t("details.call", { phone: pantry.phone })),
    (pantry.address || pantry.lat != null) && el("a", {
      class: "btn btn-primary", href: directionsLink(pantry), target: "_blank", rel: "noopener",
    }, t("details.directions")),
  );

  const headingId = `details-${pantry.id}`;
  card.setAttribute("aria-labelledby", headingId);
  card.replaceChildren(
    el("div", { class: "details-head" },
      el("div", {},
        el("h3", { id: headingId }, pantry.name),
        el("p", { class: "address" }, place || t("details.noAddress")),
      ),
      el("button", { class: "close", type: "button", "aria-label": t("details.close") }, "×"),
    ),
    el("div", {},
      statusBadge(pantry.status),
      pantry.distance_miles != null ? t("details.away", { n: pantry.distance_miles }) : null,
    ),
    el("section", {},
      el("h4", {}, t("details.hours")),
      el("ul", {}, ...hoursLines(pantry).map((line) => el("li", {}, line))),
      showOriginalText && el("p", { class: "listed-as" }, t("details.listedAs", { text: pantry.hours_text })),
    ),
    el("section", {},
      el("h4", {}, t("details.know")),
      el("ul", {}, ...requirements.map((line) => el("li", {}, line))),
    ),
    actions.childElementCount ? actions : null,
    el("p", { class: "verified" }, t("details.verified", { date: formatVerified(pantry.date_verified) })),
  );

  card.querySelector(".close").addEventListener("click", closeDetails);
  card.hidden = false;
}

function closeDetails() {
  selectPantry(null);
  // Send keyboard focus back to the list item that opened the card.
  if (lastListButton && document.body.contains(lastListButton)) lastListButton.focus();
}

// ---------- the list ----------

function sortForList(pantries) {
  if (state.origin) return pantries; // already sorted by distance
  return [...pantries].sort((a, b) =>
    STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status) || a.name.localeCompare(b.name));
}

function drawList() {
  const list = $("#list");
  const pantries = sortForList(state.pantries);

  $("#list-title").textContent = state.origin ? t("list.nearest") : t("list.title");
  $("#count").textContent = t("list.count", { n: pantries.length });

  if (!pantries.length) {
    list.replaceChildren(el("li", { class: "empty" }, t("list.empty")));
    return;
  }

  list.replaceChildren(...pantries.map((pantry) => {
    const onMap = pantry.lat != null && pantry.lng != null;
    const button = el("button", {
      type: "button",
      class: "list-item",
      "data-id": pantry.id,
      "aria-current": String(pantry.id === state.selectedId),
    },
      el("span", { class: "name" }, pantry.name),
      el("span", { class: "distance" }, pantry.distance_miles != null ? t("list.miles", { n: pantry.distance_miles }) : ""),
      statusBadge(pantry.status),
      el("span", { class: "sub" }, [pantry.city, onMap ? null : t("list.notOnMap")].filter(Boolean).join(" · ")),
    );
    button.addEventListener("click", () => {
      lastListButton = button;
      selectPantry(pantry.id, { scroll: true, pan: true });
    });
    return el("li", {}, button);
  }));
}

function drawAll() {
  drawPins();
  drawDetails();
  drawList();
  drawMessage();
}

// ---------- selecting a pantry ----------

function selectPantry(id, { scroll = false, pan = false } = {}) {
  state.selectedId = id;
  drawAll();
  if (lastListButton) lastListButton = document.querySelector(`.list-item[data-id="${CSS.escape(lastListButton.dataset.id)}"]`);

  const pantry = state.pantries.find((p) => p.id === id);
  if (pantry && pan && pantry.lat != null) {
    map.setView([pantry.lat, pantry.lng], Math.max(map.getZoom(), 13));
  }
  if (pantry && scroll) {
    const card = $("#details");
    card.scrollIntoView({ behavior: "smooth", block: "start" });
    card.focus({ preventScroll: true });
  }
}

// Escape closes the card, from anywhere on the page.
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.selectedId) closeDetails();
});

// ---------- offline: use the list the service worker saved ----------

function applyOfflineFilters(pantries) {
  let result = pantries.map((p) => ({ ...p, status: "offline", distance_miles: null }));
  if (state.filters.no_id) result = result.filter((p) => p.id_required !== true);
  if (state.filters.drive_thru) result = result.filter((p) => p.drive_thru === true);
  if (state.filters.spanish) result = result.filter((p) => p.spanish === true);
  if (state.origin?.lat != null) {
    for (const p of result) {
      if (p.lat != null) p.distance_miles = Math.round(milesBetween(state.origin.lat, state.origin.lng, p.lat, p.lng) * 10) / 10;
    }
    result.sort((a, b) => (a.distance_miles == null) - (b.distance_miles == null) || (a.distance_miles || 0) - (b.distance_miles || 0));
  }
  return result;
}

function offlineMessage(checkedAt) {
  const when = new Date(checkedAt).toLocaleString(locale(), { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  const parts = [["msg.offline", { when }]];
  if (state.filters.open_now) parts.push(["msg.openNowOffline"]);
  if (state.origin?.zip) parts.push(["msg.zipOffline"]);
  return parts;
}

// ---------- talking to the backend ----------

async function loadPantries() {
  const params = new URLSearchParams();
  for (const [name, on] of Object.entries(state.filters)) {
    if (on) params.set(name, "true");
  }
  if (state.origin?.zip) params.set("zip", state.origin.zip);
  if (state.origin?.lat != null) {
    params.set("lat", state.origin.lat);
    params.set("lng", state.origin.lng);
  }

  try {
    const query = params.toString();
    const response = await fetch(query ? `/pantries?${query}` : "/pantries");
    const body = await response.json();
    if (!response.ok) {
      if (response.status === 404 && state.origin?.zip) showMessage(["msg.zipNotFound", { zip: state.origin.zip }]);
      else showMessage(["msg.badInput"]);
      if (state.origin?.zip) state.origin = null;
      return;
    }

    // The service worker adds this header when it answers from the saved copy.
    state.offline = response.headers.get("X-PantryPilot-Saved") === "1";
    if (state.offline) {
      state.pantries = applyOfflineFilters(body.pantries);
      showMessage(...offlineMessage(body.checked_at));
    } else {
      state.pantries = body.pantries;
      showMessage();
      if (body.origin) showYouAreHere(body.origin.lat, body.origin.lng);
    }
    if (!state.pantries.some((p) => p.id === state.selectedId)) state.selectedId = null;
    drawAll();
  } catch (error) {
    showMessage(["msg.network"]);
  }
}

// ---------- wiring up the controls ----------

$("#zip-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const zip = $("#zip").value.trim();
  if (!/^\d{5}$/.test(zip)) {
    showMessage(["msg.zipInvalid"]);
    $("#zip").focus();
    return;
  }
  state.origin = { zip };
  loadPantries();
});

$("#locate").addEventListener("click", () => {
  if (!navigator.geolocation) {
    showMessage(["msg.noGeo"]);
    return;
  }
  showMessage(["msg.finding"]);
  navigator.geolocation.getCurrentPosition(
    (position) => {
      state.origin = { lat: position.coords.latitude, lng: position.coords.longitude };
      $("#zip").value = "";
      loadPantries();
    },
    () => showMessage(["msg.geoFailed"]),
    { timeout: 10000 },
  );
});

for (const chip of document.querySelectorAll(".chip")) {
  chip.addEventListener("click", () => {
    const name = chip.dataset.filter;
    state.filters[name] = !state.filters[name];
    chip.setAttribute("aria-pressed", String(state.filters[name]));
    loadPantries();
  });
}

// Redraw everything built in JavaScript when the language or display settings change.
document.addEventListener("pp:languagechange", () => {
  labelMap();
  if (youAreHere) youAreHere.setTooltipContent(t("map.youAreHere"));
  drawAll();
});
document.addEventListener("pp:displaychange", drawPins);

// Back online? Get fresh open/closed status right away.
window.addEventListener("online", loadPantries);

loadPantries();
setInterval(loadPantries, REFRESH_MINUTES * 60 * 1000);
