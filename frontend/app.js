// PantryPilot frontend: plain JavaScript, no frameworks.
// It asks our FastAPI backend (/pantries) for data and draws the map, card, and list.

const FRISCO = [33.1507, -96.8236];
const REFRESH_MINUTES = 5; // re-check open/closed status this often

const STATUS_LABELS = {
  open: "Open now",
  later_today: "Opens later today",
  appointment: "Appointment needed",
  closed: "Closed now",
  unknown: "Call for hours",
};

// Same colors as style.css. "unknown" gets a hollow pin.
const STATUS_COLORS = {
  open: "#2e9b5f",
  later_today: "#e2a524",
  appointment: "#3a76c4",
  closed: "#8b9398",
  unknown: "#ffffff",
};

// When there's no location to sort by distance, show open pantries first.
const STATUS_ORDER = ["open", "later_today", "appointment", "closed", "unknown"];

const DAY_LABELS = { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" };
const DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEK_LABELS = { 1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", last: "Last" };

// Everything the page knows, in one place.
const state = {
  filters: { open_now: false, no_id: false, drive_thru: false, spanish: false },
  origin: null,        // { zip } or { lat, lng }
  pantries: [],
  selectedId: null,
};

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

function showMessage(text) {
  $("#message").textContent = text || "";
}

// ---------- turning a schedule into readable text ----------

// "16:30" -> "4:30 PM", "12:00" -> "12 PM"
function formatTime(hhmm) {
  let [hours, minutes] = hhmm.split(":").map(Number);
  const suffix = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;
  return minutes ? `${hours}:${String(minutes).padStart(2, "0")} ${suffix}` : `${hours} ${suffix}`;
}

// Turns ["mon","tue","wed","thu","fri"] into "Mon–Fri" and ["tue","thu"] into "Tue & Thu"
function formatDays(days) {
  const sorted = [...days].sort((a, b) => DAY_ORDER.indexOf(a) - DAY_ORDER.indexOf(b));
  const indexes = sorted.map((d) => DAY_ORDER.indexOf(d));
  const consecutive = indexes.every((n, i) => i === 0 || n === indexes[i - 1] + 1);
  if (sorted.length >= 3 && consecutive) {
    return `${DAY_LABELS[sorted[0]]}–${DAY_LABELS[sorted[sorted.length - 1]]}`;
  }
  const labels = sorted.map((d) => DAY_LABELS[d]);
  return labels.length <= 2 ? labels.join(" & ") : labels.join(", ");
}

// [1, 3] -> "1st & 3rd"
function formatWeeks(weeks) {
  return weeks.map((w) => WEEK_LABELS[w]).join(" & ");
}

// [1..10] -> "Jan–Oct"
function formatMonths(months) {
  const consecutive = months.every((m, i) => i === 0 || m === months[i - 1] + 1);
  if (months.length >= 3 && consecutive) {
    return `${MONTH_LABELS[months[0] - 1]}–${MONTH_LABELS[months[months.length - 1] - 1]}`;
  }
  return months.map((m) => MONTH_LABELS[m - 1]).join(", ");
}

// One rule -> "1st & 3rd Sat: 9 AM–11 AM (appointment)"
function formatRule(rule) {
  let when = formatDays(rule.days);
  if (rule.weeks) when = `${formatWeeks(rule.weeks)} ${when}`;
  if (rule.months) when = `${formatMonths(rule.months)}: ${when}`;
  const times = rule.windows.map((w) => `${formatTime(w.start)}–${formatTime(w.end)}`).join(", ");
  return `${when}: ${times}${rule.appointment ? " (appointment)" : ""}`;
}

// A whole schedule -> list of lines to show
function hoursLines(pantry) {
  const schedule = pantry.schedule;
  if (schedule.type === "always_open") return ["Open 24 hours, every day"];
  if (schedule.type === "appointment_only") return ["By appointment only. Call to schedule."];
  if (schedule.type === "unknown") return ["Hours not confirmed. Please call first."];

  const lines = schedule.rules.map(formatRule);
  if (schedule.appointment_available) lines.push("Other times by appointment");
  return lines;
}

function formatVerified(dateText) {
  if (!dateText) return "Not yet verified";
  const [year, month, day] = dateText.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
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

function canGetDirections(pantry) {
  return Boolean(pantry.address || (pantry.lat != null && pantry.lng != null));
}

function statusBadge(status) {
  return el("span", { class: "status" },
    el("span", { class: `dot ${status}`, "aria-hidden": "true" }),
    STATUS_LABELS[status]);
}

// ---------- the map ----------

const map = L.map("map", { zoomControl: true }).setView(FRISCO, 11);

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

const pinLayer = L.layerGroup().addTo(map);
const pinsById = {};
let youAreHere = null;

function drawPins() {
  pinLayer.clearLayers();
  for (const pantry of state.pantries) {
    if (pantry.lat == null || pantry.lng == null) continue;
    const selected = pantry.id === state.selectedId;
    const pin = L.circleMarker([pantry.lat, pantry.lng], {
      radius: selected ? 14 : 10,
      color: pantry.status === "unknown" ? "#8b9398" : "#ffffff",
      weight: selected ? 4 : 2.5,
      dashArray: pantry.status === "unknown" ? "3 3" : null,
      fillColor: STATUS_COLORS[pantry.status],
      fillOpacity: 1,
    });
    pin.bindTooltip(`${pantry.name}: ${STATUS_LABELS[pantry.status]}`);
    pin.on("click", () => selectPantry(pantry.id, { scroll: true }));
    pin.addTo(pinLayer);
    pinsById[pantry.id] = pin;
  }
}

function showYouAreHere(lat, lng) {
  if (youAreHere) youAreHere.remove();
  youAreHere = L.circleMarker([lat, lng], {
    radius: 8, color: "#1e2a2c", weight: 3, fillColor: "#ffffff", fillOpacity: 1,
  }).bindTooltip("You are here").addTo(map);
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
  if (pantry.id_required === true) requirements.push("Photo ID required");
  if (pantry.id_required === false) requirements.push("No ID needed");
  if (pantry.id_required == null) requirements.push("ID: not sure, so bring one if you can");
  if (pantry.serves) requirements.push(`Serves: ${pantry.serves}`);
  for (const note of pantry.notes) requirements.push(note);
  if (pantry.drive_thru) requirements.push("Drive-thru available");
  if (pantry.spanish) requirements.push("Se habla español");

  const place = [pantry.address, pantry.city].filter(Boolean).join(", ");
  const showOriginalText = pantry.schedule.type === "unknown" && !/call( ahead)? for hours/i.test(pantry.hours_text);

  const actions = el("div", { class: "actions" },
    pantry.phone && el("a", { class: "btn", href: phoneLink(pantry.phone) }, `Call ${pantry.phone}`),
    canGetDirections(pantry) && el("a", {
      class: "btn btn-primary", href: directionsLink(pantry), target: "_blank", rel: "noopener",
    }, "Get directions"),
  );

  card.replaceChildren(
    el("div", { class: "details-head" },
      el("div", {},
        el("h3", {}, pantry.name),
        el("p", { class: "address" }, place || "Address not listed"),
      ),
      el("button", { class: "close", type: "button", "aria-label": "Close details" }, "×"),
    ),
    el("div", {},
      statusBadge(pantry.status),
      pantry.distance_miles != null ? ` · ${pantry.distance_miles} mi away` : null,
    ),
    el("section", {},
      el("h4", {}, "Hours"),
      el("ul", {}, ...hoursLines(pantry).map((line) => el("li", {}, line))),
      showOriginalText && el("p", { class: "listed-as" }, `Listed as: "${pantry.hours_text}"`),
    ),
    el("section", {},
      el("h4", {}, "What to know"),
      el("ul", {}, ...requirements.map((line) => el("li", {}, line))),
    ),
    actions.childElementCount ? actions : null,
    el("p", { class: "verified" }, `Last verified: ${formatVerified(pantry.date_verified)}`),
  );

  card.querySelector(".close").addEventListener("click", () => selectPantry(null));
  card.hidden = false;
}

// ---------- the list ----------

function sortForList(pantries) {
  if (state.origin) return pantries; // the server already sorted by distance
  return [...pantries].sort((a, b) =>
    STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status) || a.name.localeCompare(b.name));
}

function drawList() {
  const list = $("#list");
  const pantries = sortForList(state.pantries);

  $("#list-title").textContent = state.origin ? "Nearest pantries" : "Pantries";
  $("#count").textContent = `(${pantries.length})`;

  if (!pantries.length) {
    list.replaceChildren(el("li", { class: "empty" }, "No pantries match these filters. Try turning one off."));
    return;
  }

  list.replaceChildren(...pantries.map((pantry) => {
    const onMap = pantry.lat != null && pantry.lng != null;
    const button = el("button", {
      type: "button",
      class: "list-item",
      "aria-current": String(pantry.id === state.selectedId),
    },
      el("span", { class: "name" }, pantry.name),
      el("span", { class: "distance" }, pantry.distance_miles != null ? `${pantry.distance_miles} mi` : ""),
      statusBadge(pantry.status),
      el("span", { class: "sub" }, [pantry.city, onMap ? null : "not on map"].filter(Boolean).join(" · ")),
    );
    button.addEventListener("click", () => selectPantry(pantry.id, { scroll: true, pan: true }));
    return el("li", {}, button);
  }));
}

// ---------- selecting a pantry ----------

function selectPantry(id, { scroll = false, pan = false } = {}) {
  state.selectedId = id;
  drawPins();
  drawDetails();
  drawList();

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
    const response = await fetch(`/pantries?${params}`);
    const body = await response.json();
    if (!response.ok) {
      // e.g. a ZIP outside our area: show the server's explanation
      showMessage(typeof body.detail === "string" ? body.detail : "Please check what you typed.");
      if (state.origin?.zip) state.origin = null;
      return;
    }
    showMessage("");
    state.pantries = body.pantries;
    if (body.origin) showYouAreHere(body.origin.lat, body.origin.lng);
    if (!state.pantries.some((p) => p.id === state.selectedId)) state.selectedId = null;
    drawPins();
    drawDetails();
    drawList();
  } catch (error) {
    showMessage("Couldn't reach PantryPilot. Check your internet connection and try again.");
  }
}

// ---------- wiring up the controls ----------

$("#zip-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const zip = $("#zip").value.trim();
  if (!/^\d{5}$/.test(zip)) {
    showMessage("Please enter a 5-digit ZIP code, like 75034.");
    return;
  }
  state.origin = { zip };
  loadPantries();
});

$("#locate").addEventListener("click", () => {
  if (!navigator.geolocation) {
    showMessage("Your browser can't share your location. Try a ZIP code instead.");
    return;
  }
  showMessage("Finding your location…");
  navigator.geolocation.getCurrentPosition(
    (position) => {
      state.origin = { lat: position.coords.latitude, lng: position.coords.longitude };
      $("#zip").value = "";
      loadPantries();
    },
    () => showMessage("Couldn't get your location. Try a ZIP code instead."),
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

loadPantries();
setInterval(loadPantries, REFRESH_MINUTES * 60 * 1000);
