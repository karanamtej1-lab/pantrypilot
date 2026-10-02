// Hours Coach: plain JavaScript. All data lives in this browser's localStorage.
// Nothing is ever sent to the server.

const STORAGE_KEY = "pantrypilot.hours.v1";
const MONTHLY_GOAL = 80;
const WEEKLY_PACE = 20; // 80 hours / ~4 weeks

const TYPE_LABELS = { work: "Work", volunteer: "Volunteer", training: "Job training" };

// ---------- dates ----------
// Dates are stored as "YYYY-MM-DD" strings. We never use new Date("2026-09-28"):
// JavaScript reads that as midnight UTC, which is the evening BEFORE in Texas.

function toDateString(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function fromDateString(text) {
  const [y, m, d] = text.split("-").map(Number);
  return new Date(y, m - 1, d); // local time
}

function addDays(date, days) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function shortDate(date) {
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ---------- saving and loading ----------

let storageWorks = true;
let entries = loadEntries();
let lastDeleted = null;

function loadEntries() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(saved) ? saved.filter(isValidEntry) : [];
  } catch (error) {
    storageWorks = false; // private browsing, blocked storage, or damaged data
    return [];
  }
}

function saveEntries() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch (error) {
    storageWorks = false;
  }
  document.querySelector("#storage-warning").hidden = storageWorks;
}

function isValidEntry(entry) {
  return entry && /^\d{4}-\d{2}-\d{2}$/.test(entry.date) &&
    typeof entry.hours === "number" && entry.hours > 0 && entry.hours <= 24 &&
    entry.type in TYPE_LABELS;
}

function newId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

// ---------- this month ----------

function monthInfo(today = new Date()) {
  const first = new Date(today.getFullYear(), today.getMonth(), 1);
  const last = new Date(today.getFullYear(), today.getMonth() + 1, 0); // day 0 of next month
  return {
    first,
    last,
    prefix: toDateString(first).slice(0, 7),          // "2026-09"
    name: today.toLocaleDateString("en-US", { month: "long" }),
    daysLeft: last.getDate() - today.getDate() + 1,   // counting today
  };
}

function thisMonthsEntries(month) {
  return entries.filter((e) => e.date.startsWith(month.prefix));
}

function formatHours(n) {
  return Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/0$/, "");
}

// Monday-to-Sunday weeks, cut off at the edges of the month.
function weeksOf(month) {
  const weeks = [];
  let start = month.first;
  while (start <= month.last) {
    const daysToSunday = (7 - start.getDay()) % 7; // getDay(): Sunday = 0
    let end = addDays(start, daysToSunday);
    if (end > month.last) end = month.last;
    weeks.push({ start, end, hours: 0 });
    start = addDays(end, 1);
  }
  return weeks;
}

// ---------- drawing ----------

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

function drawProgress(month, total) {
  const percent = Math.min(total / MONTHLY_GOAL, 1) * 100;
  const left = Math.max(MONTHLY_GOAL - total, 0);
  const dayWord = month.daysLeft === 1 ? "day" : "days";

  document.querySelector("#total").textContent = formatHours(total);
  document.querySelector("#progress-fill").style.width = `${percent}%`;
  const bar = document.querySelector("#progress");
  bar.setAttribute("aria-valuenow", String(Math.min(total, MONTHLY_GOAL)));
  bar.classList.toggle("done", left === 0);

  const detail = document.querySelector("#progress-detail");
  detail.replaceChildren();
  if (left === 0) {
    detail.append(el("strong", {}, `You've logged 80 hours for ${month.name}!`),
      ` ${month.daysLeft} ${dayWord} left in the month.`);
  } else {
    detail.append(el("strong", {}, `${formatHours(left)} hours to go`),
      ` · ${month.daysLeft} ${dayWord} left in ${month.name} (including today)`);
  }
}

function drawWeeks(month, monthEntries) {
  const weeks = weeksOf(month);
  for (const entry of monthEntries) {
    const day = fromDateString(entry.date);
    const week = weeks.find((w) => day >= w.start && day <= w.end);
    if (week) week.hours += entry.hours;
  }

  // Scale so the biggest bar (or the 20-hour pace line) fits.
  const scaleMax = Math.max(WEEKLY_PACE * 1.25, ...weeks.map((w) => w.hours));
  const today = new Date();

  document.querySelector("#weeks").replaceChildren(...weeks.map((week) => {
    const label = week.start.getDate() === week.end.getDate()
      ? shortDate(week.start)
      : `${shortDate(week.start)}–${week.end.getDate()}`;
    // `today` includes the current time, so compare against midnight AFTER the week's last day.
    const isCurrent = today >= week.start && today < addDays(week.end, 1);
    const width = (week.hours / scaleMax) * 100;

    return el("li", { class: `week${isCurrent ? " current" : ""}` },
      el("span", { class: "week-label" }, label),
      el("div", { class: "bar-track", "aria-hidden": "true" },
        el("div", { class: `bar${week.hours ? "" : " empty"}`, style: `width:${width}%` }),
        el("div", { class: "pace-line", style: `left:${(WEEKLY_PACE / scaleMax) * 100}%` }),
      ),
      el("span", { class: "week-value" }, `${formatHours(week.hours)} h`),
      el("span", { class: "visually-hidden" }, isCurrent ? " (this week)" : ""),
    );
  }));
}

function drawEntries(monthEntries) {
  const list = document.querySelector("#entries");
  if (!monthEntries.length) {
    list.replaceChildren(el("li", { class: "empty" }, "No hours yet this month. Add your first entry above."));
    return;
  }

  // Newest first
  const sorted = [...monthEntries].sort((a, b) => b.date.localeCompare(a.date) || b.id.localeCompare(a.id));
  list.replaceChildren(...sorted.map((entry) => {
    const day = fromDateString(entry.date).toLocaleDateString("en-US", {
      weekday: "short", month: "short", day: "numeric",
    });
    const button = el("button", {
      type: "button", class: "delete",
      "aria-label": `Delete ${formatHours(entry.hours)} hours of ${TYPE_LABELS[entry.type]} on ${day}`,
    });
    button.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>';
    button.addEventListener("click", () => deleteEntry(entry.id));

    return el("li", { class: "entry" },
      el("div", {},
        el("span", { class: "entry-date" }, day),
        el("span", { class: "entry-type" }, TYPE_LABELS[entry.type]),
      ),
      el("span", { class: "entry-hours" }, `${formatHours(entry.hours)} h`),
      button,
    );
  }));
}

function drawUndo() {
  const box = document.querySelector("#undo");
  box.replaceChildren();
  if (!lastDeleted) return;
  const button = el("button", { type: "button" }, "Undo");
  button.addEventListener("click", undoDelete);
  box.append(`Deleted ${formatHours(lastDeleted.hours)} h (${TYPE_LABELS[lastDeleted.type]}).`, button);
}

function draw() {
  const month = monthInfo();
  const monthEntries = thisMonthsEntries(month);
  const total = monthEntries.reduce((sum, e) => sum + e.hours, 0);
  drawProgress(month, total);
  drawWeeks(month, monthEntries);
  drawEntries(monthEntries);
  drawUndo();
  document.querySelector("#storage-warning").hidden = storageWorks;
  updateForecast(month, total);
}

// ---------- monthly summary PDF ----------
// Made entirely in the browser with jsPDF. The entries never leave the phone.

const JSPDF_URL = "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js";
const PDF_FOOTER = "Personal record created with PantryPilot. Not an official Texas HHSC document.";
const MAX_ROWS = 28; // more entries than this won't fit one page, so we switch to one row per day

let jsPdfLoading = null;

// Load jsPDF only when someone actually asks for a PDF.
function loadJsPdf() {
  if (window.jspdf) return Promise.resolve(window.jspdf.jsPDF);
  if (!jsPdfLoading) {
    jsPdfLoading = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = JSPDF_URL;
      script.onload = () => resolve(window.jspdf.jsPDF);
      script.onerror = () => { jsPdfLoading = null; reject(new Error("couldn't load jsPDF")); };
      document.head.append(script);
    });
  }
  return jsPdfLoading;
}

// Rows for the table: one per entry, or one per day if there are too many entries.
function summaryRows(monthEntries) {
  const sorted = [...monthEntries].sort((a, b) => a.date.localeCompare(b.date));
  if (sorted.length <= MAX_ROWS) {
    return { byDay: false, rows: sorted.map((e) => [e.date, TYPE_LABELS[e.type], e.hours]) };
  }
  const days = new Map();
  for (const e of sorted) {
    const day = days.get(e.date) || { hours: 0, types: new Set() };
    day.hours += e.hours;
    day.types.add(TYPE_LABELS[e.type]);
    days.set(e.date, day);
  }
  return {
    byDay: true,
    rows: [...days].map(([date, day]) => [date, [...day.types].join(", "), day.hours]),
  };
}

function buildSummaryPdf(jsPDF, month, monthEntries) {
  const doc = new jsPDF({ unit: "mm", format: "letter" });
  const width = doc.internal.pageSize.getWidth();
  const height = doc.internal.pageSize.getHeight();
  const left = 20;
  const right = width - 20;
  const total = monthEntries.reduce((sum, e) => sum + e.hours, 0);
  const year = month.first.getFullYear();
  const longDate = (text) => fromDateString(text).toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric",
  });

  // Title
  let y = 24;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.text(`Monthly Hours Summary: ${month.name} ${year}`, left, y);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(90);
  y += 7;
  doc.text(`Created ${new Date().toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}`, left, y);
  // Blank line to write a name by hand; the app never asks for one.
  doc.text("Name: ______________________________", right, y, { align: "right" });

  // Totals box
  y += 8;
  doc.setFillColor(227, 239, 236);
  doc.roundedRect(left, y, right - left, 34, 3, 3, "F");
  doc.setTextColor(30, 42, 44);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(14);
  doc.text(`Total: ${formatHours(total)} of 80 hours`, left + 6, y + 10);
  doc.setFontSize(10);
  let typeY = y + 18;
  for (const [type, label] of Object.entries(TYPE_LABELS)) {
    const ofType = monthEntries.filter((e) => e.type === type);
    const hours = ofType.reduce((sum, e) => sum + e.hours, 0);
    const count = `${ofType.length} ${ofType.length === 1 ? "entry" : "entries"}`;
    doc.setFont("helvetica", "normal");
    doc.text(label, left + 6, typeY);
    doc.text(count, left + 70, typeY);
    doc.setFont("helvetica", "bold");
    doc.text(`${formatHours(hours)} h`, right - 6, typeY, { align: "right" });
    typeY += 6;
  }

  // Entries table
  const { byDay, rows } = summaryRows(monthEntries);
  y += 44;
  doc.setFontSize(12);
  doc.text(byDay ? "Hours by day" : "Entries", left, y);
  y += 6;
  const cols = { date: left + 2, type: left + 55, hours: right - 2 };
  const footerY = height - 18;

  // Fit every row on ONE page: share the space between the table header and the
  // footer line (minus room for the Total row), up to a comfortable 6.5 mm per row.
  const tableTop = y + 6.5;
  const available = (footerY - 6) - tableTop - 10;
  const rowHeight = Math.min(6.5, available / Math.max(rows.length, 1));
  const rowFont = rowHeight < 5 ? 8.5 : 9.5;

  doc.setFontSize(9.5);
  doc.setTextColor(90);
  doc.text("Date", cols.date, y);
  doc.text("Type", cols.type, y);
  doc.text("Hours", cols.hours, y, { align: "right" });
  y += 2;
  doc.setDrawColor(180);
  doc.line(left, y, right, y);
  y += 4.5;

  doc.setTextColor(30, 42, 44);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(rowFont);
  if (!rows.length) {
    doc.text("No hours logged this month.", cols.date, y);
    y += rowHeight;
  }
  rows.forEach(([date, type, hours], i) => {
    if (i % 2 === 1) {  // light stripe on every other row for easy reading
      doc.setFillColor(245, 246, 243);
      doc.rect(left, y - rowHeight * 0.7, right - left, rowHeight, "F");
    }
    doc.text(longDate(date), cols.date, y);
    doc.text(type, cols.type, y);
    doc.text(`${formatHours(hours)}`, cols.hours, y, { align: "right" });
    y += rowHeight;
  });
  doc.setFontSize(9.5);
  doc.setDrawColor(180);
  doc.line(left, y - 3, right, y - 3);
  doc.setFont("helvetica", "bold");
  doc.text("Total", cols.date, y + 2);
  doc.text(formatHours(total), cols.hours, y + 2, { align: "right" });

  // Footer: always at the bottom of the page
  doc.setDrawColor(44, 110, 99);
  doc.setLineWidth(0.6);
  doc.line(left, footerY - 6, right, footerY - 6);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.setTextColor(30, 42, 44);
  doc.text(PDF_FOOTER, width / 2, footerY, { align: "center" });
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8.5);
  doc.setTextColor(90);
  doc.text("Hours are entered by the user. Keep your own proof, such as pay stubs or sign-in sheets.",
    width / 2, footerY + 5, { align: "center" });

  return doc;
}

async function downloadSummary() {
  const button = document.querySelector("#download-pdf");
  const message = document.querySelector("#pdf-message");
  const month = monthInfo();
  const monthEntries = thisMonthsEntries(month);

  button.disabled = true;
  message.textContent = "Making your PDF…";
  try {
    const jsPDF = await loadJsPdf();
    const doc = buildSummaryPdf(jsPDF, month, monthEntries);
    doc.save(`pantrypilot-hours-${month.prefix}.pdf`);
    message.textContent = "Your summary was downloaded.";
  } catch (error) {
    message.textContent = "Couldn't make the PDF. Check your internet connection and try again.";
  } finally {
    button.disabled = false;
  }
}

document.querySelector("#download-pdf").addEventListener("click", downloadSummary);

// ---------- forecast ----------

const WHAT_IF_HOURS = 4;
const SHOW_WAYS_BELOW = 0.7; // show "Ways to add hours" when the chance is under 7 in 10
const MAX_HISTORY_WEEKS = 12;

function mondayOf(date) {
  const monday = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7)); // Monday = start of week
  return monday;
}

// Totals for each FINISHED week (Mon–Sun), starting from the week of the first entry.
// Weeks with no entries in that span count as 0: that's real history.
function pastWeeklyTotals() {
  if (!entries.length) return [];
  const thisMonday = mondayOf(new Date());
  const firstDate = entries.map((e) => e.date).sort()[0];
  const totals = [];
  for (let start = mondayOf(fromDateString(firstDate)); start < thisMonday; start = addDays(start, 7)) {
    const startText = toDateString(start);
    const endText = toDateString(addDays(start, 6));
    const hours = entries
      .filter((e) => e.date >= startText && e.date <= endText)
      .reduce((sum, e) => sum + e.hours, 0);
    totals.push(Math.round(hours * 100) / 100);
  }
  return totals.slice(-MAX_HISTORY_WEEKS);
}

// 0.43 -> "About 4 in 10". Plain words instead of percentages.
function chanceInTen(probability) {
  const tenths = Math.round(probability * 10);
  if (tenths >= 10) return { words: "More than 9 in 10", dots: 10 };
  if (tenths <= 0) return { words: "Less than 1 in 10", dots: 0 };
  return { words: `About ${tenths} in 10`, dots: tenths };
}

function basisText(weeks) {
  if (weeks >= 3) return `Based on your last ${weeks} weeks of hours.`;
  if (weeks === 0) return "Based on a typical week, since you haven't logged a full week yet. It gets more personal as you log more.";
  const weekWord = weeks === 1 ? "week" : "weeks";
  return `Based on your ${weeks} ${weekWord} of hours mixed with a typical week, until you've logged 3 weeks.`;
}

let forecastRequest = 0;  // ignore answers to old requests if the user keeps typing
let volunteerList = null; // loaded once

async function updateForecast(month, total) {
  const requestNumber = ++forecastRequest;
  const body = {
    logged_hours_this_month: Math.round(total * 100) / 100,
    past_weekly_totals: pastWeeklyTotals(),
    days_left: month.daysLeft,
    target: MONTHLY_GOAL,
    what_if_extra_hours: WHAT_IF_HOURS, // asked up front so both answers come from the same simulations
  };

  try {
    const response = await fetch("/forecast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`forecast failed: ${response.status}`);
    const result = await response.json();
    if (requestNumber !== forecastRequest) return; // a newer request is on its way
    drawForecast(result, total);
  } catch (error) {
    if (requestNumber !== forecastRequest) return;
    document.querySelector("#forecast-body").hidden = true;
    const note = document.querySelector("#forecast-loading");
    note.hidden = false;
    note.textContent = "Couldn't work out your chances right now. Your hours are still saved.";
  }
}

function drawForecast(result, total) {
  document.querySelector("#forecast-loading").hidden = true;
  document.querySelector("#forecast-body").hidden = false;

  const chance = document.querySelector("#chance");
  const dots = document.querySelector("#chance-dots");
  const whatIfButton = document.querySelector("#what-if-button");
  const whatIfResult = document.querySelector("#what-if-result");
  const reached = total >= MONTHLY_GOAL;

  if (reached) {
    chance.replaceChildren("You've already reached 80 hours this month!");
  } else {
    const { words } = chanceInTen(result.probability);
    chance.replaceChildren(words, el("small", {}, "chance you'll reach 80 hours this month"));
  }
  const filled = reached ? 10 : chanceInTen(result.probability).dots;
  dots.replaceChildren(...Array.from({ length: 10 }, (_, i) => el("span", { class: i < filled ? "filled" : "" })));

  const low = Math.round(result.percentiles.p10);
  const high = Math.round(result.percentiles.p90);
  document.querySelector("#range").textContent = low === high
    ? `You'll likely end with about ${low} hours.`
    : `You'll likely end between ${low} and ${high} hours.`;
  document.querySelector("#basis").textContent = basisText(result.weeks_of_history);

  // What-if: already calculated; the button just reveals it.
  whatIfButton.hidden = reached;
  if (reached) whatIfResult.hidden = true;
  whatIfButton.setAttribute("aria-expanded", String(!whatIfResult.hidden)); // keep button and answer in sync
  if (result.what_if) {
    const before = chanceInTen(result.probability).words.toLowerCase();
    const after = chanceInTen(result.what_if.probability).words;
    whatIfResult.textContent = after.toLowerCase() === before
      ? `With one more ${WHAT_IF_HOURS}-hour shift: still ${before}. Every hour still counts toward 80.`
      : `With one more ${WHAT_IF_HOURS}-hour shift: ${after.toLowerCase()} (up from ${before}).`;
  }

  const showWays = !reached && result.probability < SHOW_WAYS_BELOW;
  document.querySelector("#ways").hidden = !showWays;
  if (showWays) drawWays();
}

async function drawWays() {
  if (volunteerList === null) {
    try {
      const response = await fetch("/volunteer");
      volunteerList = response.ok ? await response.json() : [];
    } catch (error) {
      volunteerList = [];
    }
  }

  const items = volunteerList.map((o) => {
    const details = [o.city, o.hours_per_shift ? `${o.hours_per_shift}-hour shifts` : null]
      .filter(Boolean).join(" · ");
    return el("li", {},
      el("a", { href: o.url || "#", target: "_blank", rel: "noopener" },
        el("strong", {}, o.name),
        o.description && el("span", {}, o.description),
        details && el("span", {}, details),
      ));
  });

  // Always offer something real, even before volunteer.json is filled in.
  items.push(el("li", {},
    el("a", { href: "/" },
      el("strong", {}, "Ask at a food pantry near you"),
      el("span", {}, "Many pantries on the map need volunteers. Call and ask about shifts."),
    )));

  document.querySelector("#ways-list").replaceChildren(...items);
}

document.querySelector("#what-if-button").addEventListener("click", (event) => {
  const result = document.querySelector("#what-if-result");
  result.hidden = !result.hidden;
  event.currentTarget.setAttribute("aria-expanded", String(!result.hidden));
});

// ---------- actions ----------

function deleteEntry(id) {
  lastDeleted = entries.find((e) => e.id === id) || null;
  entries = entries.filter((e) => e.id !== id);
  saveEntries();
  draw();
}

function undoDelete() {
  if (lastDeleted) entries.push(lastDeleted);
  lastDeleted = null;
  saveEntries();
  draw();
}

const form = document.querySelector("#entry-form");
const dateInput = document.querySelector("#date");
const hoursInput = document.querySelector("#hours");
const errorBox = document.querySelector("#form-error");

// Default the date to today, and don't allow future dates.
dateInput.value = toDateString(new Date());
dateInput.max = toDateString(new Date());

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const date = dateInput.value;
  const hours = Number(hoursInput.value);
  const type = form.elements.type.value;

  if (!date) return showError("Pick a date.");
  if (date > toDateString(new Date())) return showError("You can't log hours for a future date.");
  if (!hoursInput.value || !(hours > 0)) return showError("Enter how many hours, like 4 or 2.5.");
  if (hours > 24) return showError("A day only has 24 hours. Please check the number.");

  entries.push({ id: newId(), date, hours: Math.round(hours * 100) / 100, type });
  lastDeleted = null;
  saveEntries();

  errorBox.textContent = "";
  hoursInput.value = "";
  if (!date.startsWith(monthInfo().prefix)) {
    showError(`Saved. That date isn't in this month, so it won't count toward this month's 80.`);
  }
  draw();
});

function showError(text) {
  errorBox.textContent = text;
}

draw();
