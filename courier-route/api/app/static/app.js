/* מסלול שליח - צד הלקוח (ללא שלב בנייה). */
"use strict";
const APP_VERSION = "4";
window.addEventListener("error", (ev) => {
  try { toast("שגיאה באפליקציה: " + (ev.message || ev), true); } catch (_) { /* */ }
});

const $ = (sel) => document.querySelector(sel);
const state = { stops: [], route: null, view: "stops", map: null, mapLayers: null, pickMap: null, pickMarker: null, editing: null };

const VIEW_TITLES = { stops: "משלוחים", route: "מסלול", load: "סדר העמסה", settings: "הגדרות" };

// ---------- עזרים ----------
async function api(path, opts = {}) {
  const init = { credentials: "same-origin", ...opts };
  if (opts.json !== undefined) {
    init.method = init.method || "POST";
    init.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    init.body = JSON.stringify(opts.json);
  }
  const res = await fetch(path, init);
  if (res.status === 401 && path !== "/api/login") {
    showLogin();
    throw new Error("נדרשת התחברות");
  }
  let data = null;
  try { data = await res.json(); } catch (_) { /* ריק */ }
  if (!res.ok) throw new Error((data && data.detail && (typeof data.detail === "string" ? data.detail : "קלט לא תקין")) || `שגיאה ${res.status}`);
  return data;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

let toastTimer;
function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.toggle("error", isError);
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), isError ? 5000 : 2500);
}

function busy(on, text = "רגע...") {
  $("#busy").hidden = !on;
  $("#busy-text").textContent = text;
}

const fmtKm = (m) => (m >= 1000 ? `${(m / 1000).toFixed(1)} ק"מ` : `${Math.round(m)} מ'`);
function fmtDur(s) {
  const m = Math.round(s / 60);
  if (m < 60) return `${m} דק'`;
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")} שע'`;
}
function fmtClock(base, offsetS) {
  const d = new Date(new Date(base).getTime() + offsetS * 1000);
  return d.toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" });
}

// ---------- ניווט בין מסכים ----------
function showView(name) {
  state.view = name;
  for (const v of ["stops", "route", "load", "settings"]) $(`#view-${v}`).hidden = v !== name;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $("#view-title").textContent = VIEW_TITLES[name];
  if (name === "route") renderRoute();
  if (name === "load") renderLoad();
  if (name === "settings") loadSettings();
  window.scrollTo(0, 0);
}

function showLogin() {
  $("#view-login").hidden = false;
  for (const id of ["#app", "#tabs", "#topbar"]) $(id).hidden = true;
  setTimeout(() => $("#password").focus(), 50);
}

function showApp() {
  $("#view-login").hidden = true;
  for (const id of ["#app", "#tabs", "#topbar"]) $(id).hidden = false;
}

// ---------- משלוחים ----------
async function loadStops() {
  state.stops = await api("/api/stops");
  renderStops();
}

function renderStops() {
  const list = $("#stops-list");
  list.innerHTML = "";
  $("#stops-count").textContent = state.stops.length;
  $("#stops-empty").hidden = state.stops.length > 0;
  const seqByStop = {};
  if (state.route) state.route.items.forEach((it) => (seqByStop[it.stop.id] = it.seq));
  for (const s of state.stops) {
    const li = document.createElement("li");
    li.className = "item";
    const seq = seqByStop[s.id];
    const sub = s.geocoded
      ? `<div class="sub">${esc(s.recipient || "")}${s.recipient && s.phone ? " · " : ""}${esc(s.phone || "")}</div>`
      : `<div class="sub warn">⚠ הכתובת לא אותרה במפה. לחץ ✏️ לתיקון</div>`;
    li.innerHTML = `
      <div class="num ${seq ? "" : "muted-num"}">${seq || (s.geocoded ? "✓" : "!")}</div>
      <div class="main"><div class="addr">${esc(s.address)}</div>${sub}</div>
      <div class="acts">
        <button class="icon-btn" data-act="edit" aria-label="עריכה">✏️</button>
        <button class="icon-btn" data-act="del" aria-label="מחיקה">🗑️</button>
      </div>`;
    li.querySelector('[data-act="edit"]').onclick = () => openStopDialog({ stop: s });
    li.querySelector('[data-act="del"]').onclick = () => deleteStop(s);
    list.appendChild(li);
  }
}

async function addStop(payload) {
  const res = await api("/api/stops", { json: payload });
  state.route = null;
  if (res.geocode_error) toast(res.geocode_error, true);
  return res;
}

async function deleteStop(s) {
  if (!confirm(`למחוק את "${s.address}"?`)) return;
  try {
    await api(`/api/stops/${s.id}`, { method: "DELETE" });
    state.route = null;
    await loadStops();
  } catch (e) { toast(e.message, true); }
}

$("#add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#add-address");
  const address = input.value.trim();
  if (!address) return;
  busy(true, "מאתר כתובת...");
  try {
    await addStop({ address, source: "manual" });
    input.value = "";
    await loadStops();
  } catch (err) { toast(err.message, true); }
  finally { busy(false); }
});

$("#bulk-toggle").onclick = () => { $("#bulk-form").hidden = !$("#bulk-form").hidden; };

$("#bulk-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const lines = $("#bulk-text").value.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length > 2);
  if (!lines.length) return;
  const progress = $("#bulk-progress");
  let failed = 0;
  for (let i = 0; i < lines.length; i++) {
    progress.textContent = `מוסיף ${i + 1} מתוך ${lines.length}...`;
    try {
      const r = await api("/api/stops", { json: { address: lines[i], source: "bulk" } });
      if (r.geocode_error) failed++;
    } catch (err) { failed++; }
  }
  state.route = null;
  progress.textContent = failed ? `נוספו ${lines.length} כתובות. ${failed} לא אותרו, יש לתקן אותן ברשימה.` : `נוספו ${lines.length} כתובות.`;
  $("#bulk-text").value = "";
  await loadStops();
});

$("#finish-day").onclick = async () => {
  if (!confirm("לסיים את היום? כל המשלוחים והמסלול יעברו לארכיון והרשימה תתרוקן.")) return;
  try {
    await api("/api/day/finish", { method: "POST" });
    state.route = null;
    localStorage.removeItem("loaded");
    await loadStops();
    toast("היום נסגר. בהצלחה מחר!");
  } catch (e) { toast(e.message, true); }
};

// ---------- צילום תווית + OCR ----------
async function compressImage(file, maxSide = 2000) {
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * scale);
    canvas.height = Math.round(bmp.height * scale);
    canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve) => canvas.toBlob((b) => resolve(b || file), "image/jpeg", 0.88));
  } catch (_) {
    return file;
  }
}

$("#next-done").onclick = () => $("#next-dialog").close();
$("#next-input").addEventListener("change", (e) => {
  $("#next-dialog").close();
  handleLabelInput(e);
});
$("#camera-input").addEventListener("change", (e) => handleLabelInput(e));

async function handleLabelInput(e) {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  if (!file) return;
  openStopDialog({ ocr: true });
  $("#ocr-preview").src = URL.createObjectURL(file);
  $("#ocr-preview").hidden = false;
  const status = $("#ocr-status");
  status.hidden = false;
  status.textContent = "קורא את התווית...";
  try {
    const blob = await compressImage(file);
    const fd = new FormData();
    fd.append("image", blob, "label.jpg");
    const res = await api("/api/ocr", { method: "POST", body: fd });
    state.editing.rawText = res.text;
    $("#ocr-text").textContent = res.text || "(לא זוהה טקסט)";
    $("#ocr-raw").hidden = false;
    if (res.phone && !$("#f-phone").value) $("#f-phone").value = res.phone;
    if (res.recipient && !$("#f-recipient").value) $("#f-recipient").value = res.recipient;
    const chips = $("#ocr-candidates");
    chips.innerHTML = "";
    if (res.candidates.length) {
      status.textContent = "בחר את הכתובת הנכונה ותקן אם צריך:";
      res.candidates.forEach((c, i) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "chip" + (i === 0 ? " selected" : "");
        b.textContent = c;
        b.onclick = () => {
          chips.querySelectorAll(".chip").forEach((x) => x.classList.remove("selected"));
          b.classList.add("selected");
          $("#f-address").value = c;
        };
        chips.appendChild(b);
      });
      chips.hidden = false;
      $("#f-address").value = res.candidates[0];
    } else {
      status.textContent = "לא זיהיתי כתובת בוודאות. הקלד אותה או נסה צילום חד וקרוב יותר.";
    }
    $("#f-address").focus();
  } catch (err) {
    status.textContent = "קריאת התמונה נכשלה: " + err.message;
  }
}

// ---------- חלון משלוח (חדש מצילום / עריכה) ----------
function openStopDialog({ stop = null, ocr = false }) {
  state.editing = { stop, ocr, rawText: null, lat: null, lon: null };
  $("#stop-dialog-title").textContent = stop ? "עריכת משלוח" : "משלוח מצילום";
  $("#f-address").value = stop ? stop.address : "";
  $("#f-recipient").value = stop?.recipient || "";
  $("#f-phone").value = stop?.phone || "";
  $("#f-notes").value = stop?.notes || "";
  $("#f-geo").textContent = stop?.geocode_label ? `📍 ${stop.geocode_label}` : "";
  $("#stop-error").textContent = "";
  $("#ocr-preview").hidden = true;
  $("#ocr-status").hidden = true;
  $("#ocr-candidates").hidden = true;
  $("#ocr-raw").hidden = true;
  $("#pick-map").hidden = true;
  $("#stop-save-next").hidden = !ocr;
  $("#stop-dialog").showModal();
}

$("#pick-on-map").onclick = () => {
  const el = $("#pick-map");
  el.hidden = false;
  const s = state.editing.stop;
  const center = s && s.geocoded ? [s.lat, s.lon] : [32.0853, 34.7818];
  if (!state.pickMap) {
    state.pickMap = L.map(el).setView(center, s && s.geocoded ? 17 : 12);
    addTiles(state.pickMap);
    state.pickMap.on("click", (ev) => {
      state.editing.lat = ev.latlng.lat;
      state.editing.lon = ev.latlng.lng;
      if (state.pickMarker) state.pickMarker.setLatLng(ev.latlng);
      else state.pickMarker = L.marker(ev.latlng).addTo(state.pickMap);
      $("#f-geo").textContent = "📍 נבחר מיקום ידני על המפה";
    });
  } else {
    state.pickMap.setView(center, s && s.geocoded ? 17 : 12);
    if (state.pickMarker) { state.pickMarker.remove(); state.pickMarker = null; }
  }
  setTimeout(() => state.pickMap.invalidateSize(), 50);
  toast("הקש על המפה במקום המסירה");
};

$("#stop-form").addEventListener("submit", async (e) => {
  const action = e.submitter && e.submitter.value;
  if (action === "cancel") return; // נסגר אוטומטית
  e.preventDefault();
  const ed = state.editing;
  const payload = {
    address: $("#f-address").value.trim(),
    recipient: $("#f-recipient").value.trim() || null,
    phone: $("#f-phone").value.trim() || null,
    notes: $("#f-notes").value.trim() || null,
  };
  if (ed.lat != null) { payload.lat = ed.lat; payload.lon = ed.lon; }
  if (payload.address.length < 2) { $("#stop-error").textContent = "חסרה כתובת"; return; }
  busy(true, "מאתר כתובת...");
  try {
    let res;
    if (ed.stop) {
      res = await api(`/api/stops/${ed.stop.id}`, { method: "PATCH", json: payload });
      state.route = null;
    } else {
      res = await addStop({ ...payload, source: ed.ocr ? "ocr" : "manual", raw_text: ed.rawText });
    }
    if (res.geocode_error && ed.stop) { $("#stop-error").textContent = res.geocode_error; return; }
    $("#stop-dialog").close();
    await loadStops();
    toast("נשמר");
    if (action === "next") $("#next-dialog").showModal();
  } catch (err) {
    $("#stop-error").textContent = err.message;
  } finally { busy(false); }
});

// ---------- חישוב מסלול ----------
function getPosition() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude, label: "המיקום שלי" }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  });
}

$("#plan-btn").onclick = async () => {
  if (!state.stops.length) { toast("אין משלוחים", true); return; }
  busy(true, "מאתר את המיקום שלך...");
  try {
    const start = await getPosition();
    busy(true, "מחשב את המסלול הקצר ביותר...");
    const route = await api("/api/route/plan", { json: { start } });
    state.route = route;
    localStorage.removeItem("loaded");
    if (route.skipped && route.skipped.length) toast(`${route.skipped.length} משלוחים בלי כתובת מאותרת לא נכללו במסלול`, true);
    renderStops();
    showView("route");
  } catch (e) { toast(e.message, true); }
  finally { busy(false); }
};

function addTiles(map) {
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);
}

function numIcon(label, extra = "") {
  return L.divIcon({ className: "", html: `<div class="marker-num ${extra}">${label}</div>`, iconSize: [30, 30], iconAnchor: [15, 15] });
}

function renderRoute() {
  const r = state.route;
  $("#route-empty").hidden = !!r;
  $("#map").hidden = !r;
  $("#route-summary").innerHTML = "";
  $("#route-list").innerHTML = "";
  $("#engine-badge").hidden = !(r && r.engine !== "osrm");
  $("#engine-badge").textContent = "מפת כבישים לא זמינה: הערכה לפי מרחק אווירי";
  if (!r) return;

  $("#route-summary").innerHTML = `
    <span class="pill">📦 ${r.items.length} עצירות</span>
    <span class="pill">🛣️ ${fmtKm(r.total_distance_m)}</span>
    <span class="pill">⏱️ ${fmtDur(r.total_duration_s)} נסיעה</span>`;

  const list = $("#route-list");
  const startLi = document.createElement("li");
  startLi.className = "item start";
  startLi.innerHTML = `<div class="num">🏁</div><div class="main"><div class="addr">יציאה: ${esc(r.start.label || "")}</div>
    <div class="sub">חושב ב-${fmtClock(r.created_at, 0)}</div></div>`;
  list.appendChild(startLi);
  for (const it of r.items) {
    const s = it.stop;
    const li = document.createElement("li");
    li.className = "item";
    li.innerHTML = `
      <div class="num">${it.seq}</div>
      <div class="main">
        <div class="addr">${esc(s.address)}</div>
        <div class="sub">${s.recipient ? esc(s.recipient) + " · " : ""}${s.phone ? `<a href="tel:${esc(s.phone)}">${esc(s.phone)}</a> · ` : ""}${fmtKm(it.leg_distance_m)} · הגעה ~${fmtClock(r.created_at, it.eta_offset_s)}</div>
        ${s.notes ? `<div class="sub">📝 ${esc(s.notes)}</div>` : ""}
      </div>
      <a class="btn waze" href="${s.waze_url}" target="_blank" rel="noopener">Waze ➤</a>`;
    list.appendChild(li);
  }
  drawMap(r);
}

function drawMap(r) {
  if (!state.map) {
    state.map = L.map("map", { zoomControl: true });
    addTiles(state.map);
  }
  if (state.mapLayers) state.mapLayers.remove();
  const group = L.layerGroup().addTo(state.map);
  state.mapLayers = group;
  const pts = [[r.start.lat, r.start.lon]];
  L.marker([r.start.lat, r.start.lon], { icon: numIcon("🏁", "marker-start") }).addTo(group);
  for (const it of r.items) {
    const ll = [it.stop.lat, it.stop.lon];
    pts.push(ll);
    L.marker(ll, { icon: numIcon(it.seq) })
      .bindPopup(`<b>${it.seq}. ${esc(it.stop.address)}</b><br><a href="${it.stop.waze_url}" target="_blank" rel="noopener">נווט ב-Waze</a>`)
      .addTo(group);
  }
  if (r.geometry && r.geometry.coordinates) {
    L.geoJSON(r.geometry, { style: { color: "#0f6fff", weight: 5, opacity: 0.8 } }).addTo(group);
  } else {
    L.polyline(pts, { color: "#0f6fff", weight: 4, dashArray: "6 8" }).addTo(group);
  }
  setTimeout(() => {
    state.map.invalidateSize();
    state.map.fitBounds(L.latLngBounds(pts), { padding: [30, 30] });
  }, 50);
}

// ---------- סדר העמסה ----------
function loadedSet() {
  try {
    const raw = JSON.parse(localStorage.getItem("loaded") || "{}");
    return raw.route === state.route?.id ? new Set(raw.ids) : new Set();
  } catch (_) { return new Set(); }
}
function saveLoaded(set) {
  try { localStorage.setItem("loaded", JSON.stringify({ route: state.route.id, ids: [...set] })); } catch (_) { /* לא קריטי */ }
}

function renderLoad() {
  const r = state.route;
  const list = $("#load-list");
  list.innerHTML = "";
  $("#load-empty").hidden = !!r;
  if (!r) return;
  const loaded = loadedSet();
  for (const it of r.loading_order) {
    const li = document.createElement("li");
    li.className = "item" + (loaded.has(it.stop.id) ? " done" : "");
    li.innerHTML = `
      <label>
        <input type="checkbox" ${loaded.has(it.stop.id) ? "checked" : ""}>
        <div class="num big">${it.seq}</div>
        <div class="main">
          <div class="load-pos">${it.load_position === 1 ? "להעמיס ראשון (הכי עמוק)" : it.load_position === r.loading_order.length ? "להעמיס אחרון (ליד הדלת)" : `העמסה ${it.load_position}`}</div>
          <div class="addr">${esc(it.stop.address)}</div>
          ${it.stop.recipient ? `<div class="sub">${esc(it.stop.recipient)}</div>` : ""}
        </div>
      </label>`;
    li.querySelector("input").onchange = (e) => {
      if (e.target.checked) loaded.add(it.stop.id); else loaded.delete(it.stop.id);
      li.classList.toggle("done", e.target.checked);
      saveLoaded(loaded);
    };
    list.appendChild(li);
  }
}

// ---------- הגדרות ----------
async function loadSettings() {
  try {
    const [s, h] = await Promise.all([api("/api/settings"), api("/api/health")]);
    $("#start-address").value = s.start ? s.start.address : "";
    $("#start-label").textContent = s.start ? `📍 ${s.start.label}` : "לא הוגדרה כתובת יציאה";
    const row = (ok, text) => `<li>${ok ? "✅" : "⚠️"} ${text}</li>`;
    $("#health").innerHTML =
      row(h.osrm, h.osrm ? "מפת הכבישים (OSRM) פעילה" : "מפת הכבישים לא זמינה. החישוב לפי מרחק אווירי") +
      row(h.ocr, h.ocr ? "זיהוי טקסט מתמונה (OCR) פעיל" : "OCR לא מותקן") +
      row(true, `איתור כתובות: ${h.geocoder === "google" ? "Google" : "OpenStreetMap (חינם)"}`);
  } catch (e) { toast(e.message, true); }
}

$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  busy(true, "שומר...");
  try {
    const res = await api("/api/settings", { method: "PUT", json: { start_address: $("#start-address").value.trim() || null } });
    $("#start-label").textContent = res.start ? `📍 ${res.start.label}` : "לא הוגדרה כתובת יציאה";
    toast("נשמר");
  } catch (err) { toast(err.message, true); }
  finally { busy(false); }
});

$("#logout").onclick = async () => {
  await api("/api/logout", { method: "POST" }).catch(() => {});
  showLogin();
};

// ---------- התחברות ואתחול ----------
$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#login-error").textContent = "";
  try {
    await api("/api/login", { json: { password: $("#password").value } });
    $("#password").value = "";
    await boot();
  } catch (err) { $("#login-error").textContent = err.message; }
});

document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => showView(b.dataset.view)));

async function boot() {
  const v = $("#app-version");
  if (v) v.textContent = APP_VERSION;
  try {
    await api("/api/me");
  } catch (_) { showLogin(); return; }
  showApp();
  try {
    state.route = await api("/api/route/current");
    await loadStops();
  } catch (e) { toast(e.message, true); }
  showView(state.view);
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

boot();
