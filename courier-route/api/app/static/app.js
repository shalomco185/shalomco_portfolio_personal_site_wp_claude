/* מסלול שליח - צד הלקוח (ללא שלב בנייה). */
"use strict";
const APP_VERSION = "13";
window.addEventListener("error", (ev) => {
  try { toast("שגיאה באפליקציה: " + (ev.message || ev), true); } catch (_) { /* */ }
});

const $ = (sel) => document.querySelector(sel);
const state = { windows: [], stops: [], route: null, view: "stops", map: null, mapLayers: null, pickMap: null, pickMarker: null, editing: null };

const VIEW_TITLES = { stops: "משלוחים", route: "מסלול", load: "סדר העמסה", customers: "לקוחות", settings: "הגדרות" };

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

// ---------- חלונות זמן: צבעים ותגים ----------
const NO_WINDOW_COLOR = "#9CA3AF"; // קוד שנמחק מההגדרות
function winOf(code) { return code ? state.windows.find((w) => w.code === code) || null : null; }
function winColor(code) { return code ? (winOf(code)?.color || NO_WINDOW_COLOR) : null; }
function inkFor(hex) {
  const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  return (0.299 * r + 0.587 * g + 0.114 * b) > 165 ? "#14112B" : "#FFFFFF";
}
function applyWinBorder(li, s) {
  const c = winColor(s.time_window_code);
  if (c) { li.classList.add("tw"); li.style.borderColor = c; }
}
function winTag(s) {
  if (!s.time_window_code) return "";
  const c = winColor(s.time_window_code);
  const time = s.time_window_start ? `${s.time_window_start}–${s.time_window_end}` : "";
  return `<div class="tw-tag" style="color:${c}"><span class="tw-dot" style="background:${c}"></span>חלון ${esc(s.time_window_code)} · <span dir="ltr">${esc(time)}</span></div>`;
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
  for (const v of ["stops", "route", "load", "customers", "settings"]) $(`#view-${v}`).hidden = v !== name;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $("#view-title").textContent = VIEW_TITLES[name];
  if (name === "route") renderRoute();
  if (name === "load") renderLoad();
  if (name === "settings") loadSettings();
  if (name === "customers") loadCustomers();
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
    li.className = "item stop-card";
    applyWinBorder(li, s);
    const seq = seqByStop[s.id];
    const sub = s.geocoded
      ? `<div class="sub">${esc(s.recipient || "")}${s.recipient && s.phone ? " · " : ""}${esc(s.phone || "")}</div>`
      : `<div class="sub warn">⚠ הכתובת לא אותרה במפה. לחץ ✏️ לתיקון</div>`;
    li.innerHTML = `
      <div class="card-head">
        <div class="num ${seq ? "" : "muted-num"}">${seq || (s.geocoded ? "✓" : "!")}</div>
        <div class="acts">
          <button class="icon-btn" data-act="edit" aria-label="עריכה">✏️</button>
          <button class="icon-btn" data-act="del" aria-label="מחיקה">🗑️</button>
        </div>
      </div>
      <div class="main"><div class="addr">${esc(s.address)}</div>${s.address_details ? `<div class="details">🏢 ${esc(s.address_details)}</div>` : ""}${winTag(s)}${sub}${s.tracking_number ? `<div class="tracking">📦 ${esc(s.tracking_number)}</div>` : ""}</div>`;
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
async function compressImage(file, maxSide = 2600) {
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * scale);
    canvas.height = Math.round(bmp.height * scale);
    canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve) => canvas.toBlob((b) => resolve(b || file), "image/jpeg", 0.9));
  } catch (_) {
    return file;
  }
}

$("#next-done").onclick = () => $("#next-dialog").close();
$("#next-scan").onclick = () => { $("#next-dialog").close(); openScanner(); };
$("#scan-btn").onclick = () => openScanner();
$("#camera-input").addEventListener("change", (e) => { closeScanner(); handleLabelInput(e); });
$("#gallery-input").addEventListener("change", (e) => handleLabelInput(e));

// ---------- סורק: מצלמה חיה, פנס, ברקוד ----------
const scan = { stream: null, track: null, detector: null, timer: null, code: null, torch: false };
const BARCODE_FORMATS = ["code_128", "code_39", "code_93", "codabar", "ean_13", "ean_8", "itf", "upc_a", "upc_e", "qr_code", "data_matrix", "pdf417"];

async function openScanner() {
  const dlg = $("#scanner");
  scan.code = null;
  dlg.classList.remove("found");
  $("#scan-barcode").hidden = true;
  $("#scan-torch").hidden = true;
  $("#scan-hint").textContent = "כוון את התווית לתוך המסגרת, קרוב ככל האפשר. הברקוד ייקלט לבד.";
  dlg.showModal();
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    $("#scan-hint").textContent = "המצלמה החיה לא זמינה בדפדפן הזה. לחץ \"מצלמה רגילה\".";
    return;
  }
  try {
    scan.stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: { ideal: "environment" }, width: { ideal: 2560 }, height: { ideal: 1440 } },
    });
  } catch (err) {
    $("#scan-hint").textContent = err && err.name === "NotAllowedError"
      ? "אין הרשאה למצלמה. אשר מצלמה בהגדרות האתר ב-Chrome, או לחץ \"מצלמה רגילה\"."
      : "לא הצלחתי לפתוח את המצלמה. לחץ \"מצלמה רגילה\".";
    return;
  }
  if (!dlg.open) { stopStream(); return; } // נסגר בזמן ההמתנה להרשאה
  const video = $("#scan-video");
  video.srcObject = scan.stream;
  try { await video.play(); } catch (_) { /* */ }
  scan.track = scan.stream.getVideoTracks()[0];
  const caps = (scan.track.getCapabilities && scan.track.getCapabilities()) || {};
  if (caps.torch) $("#scan-torch").hidden = false;
  if (caps.focusMode && caps.focusMode.includes("continuous")) {
    scan.track.applyConstraints({ advanced: [{ focusMode: "continuous" }] }).catch(() => {});
  }
  startBarcodeLoop();
}

async function startBarcodeLoop() {
  if (!("BarcodeDetector" in window)) return; // אין זיהוי ברקוד בדפדפן: צילום הכתובת עדיין עובד
  try {
    const supported = await window.BarcodeDetector.getSupportedFormats();
    const formats = BARCODE_FORMATS.filter((f) => supported.includes(f));
    if (!formats.length) return;
    scan.detector = new window.BarcodeDetector({ formats });
  } catch (_) { return; }
  const video = $("#scan-video");
  scan.timer = setInterval(async () => {
    if (!scan.detector || video.readyState < 2) return;
    try {
      const codes = await scan.detector.detect(video);
      if (!codes.length) return;
      const value = codes.map((c) => c.rawValue).sort((a, b) => b.length - a.length)[0];
      if (value && value !== scan.code) {
        scan.code = value;
        $("#scanner").classList.add("found");
        $("#scan-barcode").textContent = `📦 ${value} ✓`;
        $("#scan-barcode").hidden = false;
        if (navigator.vibrate) navigator.vibrate(60);
      }
    } catch (_) { /* פריים לא תקין: ממשיכים */ }
  }, 300);
}

function stopStream() {
  clearInterval(scan.timer);
  scan.timer = null;
  scan.detector = null;
  if (scan.stream) scan.stream.getTracks().forEach((t) => t.stop());
  scan.stream = null;
  scan.track = null;
  scan.torch = false;
  $("#scan-torch").classList.remove("on");
  $("#scan-video").srcObject = null;
}

function closeScanner() {
  stopStream();
  if ($("#scanner").open) $("#scanner").close();
}

$("#scan-close").onclick = closeScanner;
$("#scanner").addEventListener("cancel", () => stopStream());
$("#scan-torch").onclick = async () => {
  if (!scan.track) return;
  scan.torch = !scan.torch;
  try {
    await scan.track.applyConstraints({ advanced: [{ torch: scan.torch }] });
    $("#scan-torch").classList.toggle("on", scan.torch);
  } catch (_) { scan.torch = false; }
};

/** צילום הפריים הנוכחי, חתוך לאזור המסגרת (התמונה מוצגת ב-object-fit: cover). */
function captureFrame() {
  const video = $("#scan-video");
  const vw = video.videoWidth, vh = video.videoHeight;
  if (!vw || !vh) return null;
  const vr = video.getBoundingClientRect();
  const fr = $("#scan-frame").getBoundingClientRect();
  const scale = Math.max(vr.width / vw, vr.height / vh);
  const ox = (vr.width - vw * scale) / 2, oy = (vr.height - vh * scale) / 2;
  const m = 0.06; // מרווח קטן מסביב למסגרת
  let sx = (fr.left - vr.left - ox - fr.width * m) / scale;
  let sy = (fr.top - vr.top - oy - fr.height * m) / scale;
  let sw = (fr.width * (1 + 2 * m)) / scale;
  let sh = (fr.height * (1 + 2 * m)) / scale;
  sx = Math.max(0, sx); sy = Math.max(0, sy);
  sw = Math.min(vw - sx, sw); sh = Math.min(vh - sy, sh);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(sw); canvas.height = Math.round(sh);
  canvas.getContext("2d").drawImage(video, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
}

/** צילום ברזולוציה מלאה של המצלמה (כמו אפליקציית המצלמה). אם לא נתמך, null. */
async function takeFullPhoto() {
  if (!scan.track || !("ImageCapture" in window)) return null;
  try {
    const photo = await new window.ImageCapture(scan.track).takePhoto();
    return photo && photo.size > 50000 ? photo : null;
  } catch (_) { return null; }
}

$("#scan-shoot").onclick = async () => {
  const shoot = $("#scan-shoot");
  if (shoot.disabled) return;
  shoot.disabled = true;
  try {
    const code = scan.code;
    // עדיפות לתמונה מלאה (חדה יותר מפריים של הווידאו); השרת חותך לבד לאזור התווית
    const photo = await takeFullPhoto();
    const blob = photo ? await compressImage(photo) : await captureFrame();
    if (!blob) { toast("המצלמה עוד לא מוכנה, נסה שוב", true); return; }
    closeScanner();
    handleLabelFile(blob, { tracking: code });
  } finally {
    shoot.disabled = false;
  }
};

function handleLabelInput(e) {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  if (file) handleLabelFile(file, {});
}

async function handleLabelFile(file, { tracking = null } = {}) {
  openStopDialog({ ocr: true });
  if (tracking) $("#f-tracking").value = tracking;
  $("#ocr-preview").src = URL.createObjectURL(file);
  $("#ocr-preview").hidden = false;
  const status = $("#ocr-status");
  status.hidden = false;
  status.textContent = "קורא את התווית...";
  try {
    const blob = file.type === "image/jpeg" && file.size < 4e6 && !file.name ? file : await compressImage(file);
    const fd = new FormData();
    fd.append("image", blob, "label.jpg");
    const res = await api("/api/ocr", { method: "POST", body: fd });
    state.editing.rawText = res.text;
    $("#ocr-text").textContent = res.text || "(לא זוהה טקסט)";
    $("#ocr-raw").hidden = false;
    if (res.phone && !$("#f-phone").value) $("#f-phone").value = res.phone;
    if (res.recipient && !$("#f-recipient").value) $("#f-recipient").value = res.recipient;
    if (res.details && !$("#f-details").value) $("#f-details").value = res.details;
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
      if (!res.confident) status.textContent = "בדוק את הכתובת. אם היא לא נכונה, הקש על השורות הנכונות למטה.";
    } else {
      status.textContent = "לא זיהיתי כתובת בוודאות. הקש למטה על השורות של הכתובת, או הקלד אותה.";
    }
    renderOcrLines(res.lines || []);
    $("#f-address").focus();
  } catch (err) {
    status.textContent = "קריאת התמונה נכשלה: " + err.message;
  }
}

/** השורות שנקראו מהתווית, כצ'יפים: הקשה מוסיפה את השורה לשדה הכתובת. */
function renderOcrLines(lines) {
  const box = $("#ocr-lines");
  box.innerHTML = "";
  const useful = lines.filter((l) => l && l.replace(/[^\dא-תA-Za-z]/g, "").length >= 2);
  $("#ocr-lines-wrap").hidden = !useful.length;
  for (const line of useful) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = line;
    b.onclick = () => {
      const f = $("#f-address");
      const clean = line.replace(/^\s*(כתובת|כתובת למשלוח|מען)\s*[:：]?\s*/, "");
      f.value = state.editing.lineTapped && f.value.trim() ? `${f.value.trim()}, ${clean}` : clean;
      state.editing.lineTapped = true;
      $("#ocr-candidates").querySelectorAll(".chip").forEach((x) => x.classList.remove("selected"));
      f.dispatchEvent(new Event("input", { bubbles: true }));
    };
    box.appendChild(b);
  }
}

// ---------- חלון משלוח (חדש מצילום / עריכה) ----------
function openStopDialog({ stop = null, ocr = false }) {
  state.editing = { stop, ocr, rawText: null, lat: null, lon: null };
  $("#stop-dialog-title").textContent = stop ? "עריכת משלוח" : "משלוח מצילום";
  $("#f-address").value = stop ? stop.address : "";
  $("#f-details").value = stop?.address_details || "";
  $("#f-tracking").value = stop?.tracking_number || "";
  fillWindowSelect(stop?.time_window_code || "");
  $("#ocr-lines-wrap").hidden = true;
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
    address_details: $("#f-details").value.trim() || null,
    tracking_number: $("#f-tracking").value.trim() || null,
    time_window_code: $("#f-window").value || null,
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
      state.route = await api("/api/route/current");
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

function numIcon(label, extra = "", color = null) {
  const style = color ? ` style="background:${color};color:${inkFor(color)}"` : "";
  return L.divIcon({ className: "", html: `<div class="marker-num ${extra}"${style}>${label}</div>`, iconSize: [30, 30], iconAnchor: [15, 15] });
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
    li.className = "item route-item";
    applyWinBorder(li, s);
    const phone = (s.phone || "").replace(/[^\d+]/g, "");
    li.innerHTML = `
      <div class="num">${it.seq}</div>
      <div class="main">
        <div class="addr">${esc(s.address)}</div>
        ${s.address_details ? `<div class="details">🏢 ${esc(s.address_details)}</div>` : ""}
        ${winTag(s)}
        <div class="sub">${s.recipient ? esc(s.recipient) + " · " : ""}${s.phone ? esc(s.phone) + " · " : ""}${fmtKm(it.leg_distance_m)} · הגעה ~${fmtClock(r.created_at, it.eta_offset_s)}</div>
        ${s.notes ? `<div class="sub">📝 ${esc(s.notes)}</div>` : ""}
      </div>
      <div class="stop-acts">
        <a class="btn waze" href="${s.waze_url}" target="_blank" rel="noopener">Waze ➤</a>
        ${phone ? `<a class="btn call" href="tel:${esc(phone)}" aria-label="חיוג ל${esc(s.recipient || s.phone)}">📞 חיוג</a>` : ""}
        <button class="btn notes" type="button" data-act="notes">📝 הערות</button>
      </div>`;
    li.querySelector('[data-act="notes"]').onclick = () => openNotesDialog(s);
    list.appendChild(li);
  }
  drawMap(r);
}

/** מקרא צבעים על המפה: רק חלונות הזמן שיש במסלול הזה. */
function drawLegend(r) {
  if (state.legend) { state.legend.remove(); state.legend = null; }
  const codes = [...new Set(r.items.map((it) => it.stop.time_window_code).filter(Boolean))];
  if (!codes.length) return;
  const legend = L.control({ position: "bottomright" });
  legend.onAdd = () => {
    const div = L.DomUtil.create("div", "map-legend");
    div.innerHTML = codes.map((c) => {
      const w = winOf(c);
      return `<div><span class="tw-dot" style="background:${winColor(c)}"></span>${esc(c)}${w ? ` · <span dir="ltr">${w.start}–${w.end}</span>` : ""}</div>`;
    }).join("");
    return div;
  };
  legend.addTo(state.map);
  state.legend = legend;
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
    L.marker(ll, { icon: numIcon(it.seq, "", winColor(it.stop.time_window_code)) })
      .bindPopup(`<b>${it.seq}. ${esc(it.stop.address)}</b><br><a href="${it.stop.waze_url}" target="_blank" rel="noopener">נווט ב-Waze</a>`)
      .addTo(group);
  }
  drawLegend(r);
  if (r.geometry && r.geometry.coordinates) {
    L.geoJSON(r.geometry, { style: { color: "#5B2FF0", weight: 5, opacity: 0.8 } }).addTo(group);
  } else {
    L.polyline(pts, { color: "#5B2FF0", weight: 4, dashArray: "6 8" }).addTo(group);
  }
  setTimeout(() => {
    state.map.invalidateSize();
    state.map.fitBounds(L.latLngBounds(pts), { padding: [30, 30] });
  }, 50);
}

// ---------- עריכת הערות מתוך המסלול ----------
let notesStop = null;
function openNotesDialog(stop) {
  notesStop = stop;
  $("#notes-addr").textContent = stop.address + (stop.address_details ? ` · ${stop.address_details}` : "");
  $("#notes-text").value = stop.notes || "";
  $("#notes-error").textContent = "";
  $("#notes-dialog").showModal();
  setTimeout(() => $("#notes-text").focus(), 50);
}

$("#notes-form").addEventListener("submit", async (e) => {
  if (!e.submitter || e.submitter.value !== "save") return; // ביטול: נסגר
  e.preventDefault();
  const notes = $("#notes-text").value.trim() || null;
  try {
    const res = await api(`/api/stops/${notesStop.id}`, { method: "PATCH", json: { notes } });
    // עדכון מקומי, בלי לחשב מסלול מחדש
    if (state.route) state.route.items.forEach((it) => { if (it.stop.id === notesStop.id) it.stop.notes = res.stop.notes; });
    state.stops.forEach((st) => { if (st.id === notesStop.id) st.notes = res.stop.notes; });
    $("#notes-dialog").close();
    renderRoute();
    toast("ההערה נשמרה");
  } catch (err) {
    $("#notes-error").textContent = err.message;
  }
});

function fillWindowSelect(current) {
  const sel = $("#f-window");
  const opts = [`<option value="">ללא חלון זמן</option>`].concat(
    state.windows.map((w) => `<option value="${esc(w.code)}">${esc(w.code)} · \u2066${w.start}–${w.end}\u2069</option>`)
  );
  if (current && !winOf(current)) opts.push(`<option value="${esc(current)}">${esc(current)} (לא מוגדר בהגדרות)</option>`);
  sel.innerHTML = opts.join("");
  sel.value = current || "";
}

// ---------- הגדרות: חלונות זמן ----------
async function loadWindows() {
  try { state.windows = await api("/api/time-windows"); } catch (_) { state.windows = []; }
  renderWindowsSettings();
}

function renderWindowsSettings() {
  const ul = $("#tw-list");
  ul.innerHTML = "";
  for (const w of state.windows) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="tw-dot" style="background:${w.color}"></span>
      <span class="tw-code">${esc(w.code)}</span>
      <span class="tw-time">${w.start}–${w.end}</span>
      <button type="button" aria-label="מחיקת חלון ${esc(w.code)}">🗑️</button>`;
    li.querySelector("button").onclick = async () => {
      if (!confirm(`למחוק את חלון הזמן ${w.code}? משלוחים שכבר שויכו אליו ישמרו את השעות.`)) return;
      try {
        await api(`/api/time-windows/${encodeURIComponent(w.code)}`, { method: "DELETE" });
        await loadWindows();
        renderStops();
      } catch (err) { toast(err.message, true); }
    };
    ul.appendChild(li);
  }
}

$("#tw-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#tw-error").textContent = "";
  try {
    const w = await api("/api/time-windows", { json: { code: $("#tw-code").value.trim(), time: $("#tw-time").value.trim() } });
    $("#tw-code").value = ""; $("#tw-time").value = "";
    await loadWindows();
    renderStops();
    toast(`חלון ${w.code} נשמר: \u2066${w.start}–${w.end}\u2069`);
  } catch (err) { $("#tw-error").textContent = err.message; }
});

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
          ${it.stop.address_details ? `<div class="details">🏢 ${esc(it.stop.address_details)}</div>` : ""}
          ${it.stop.tracking_number ? `<div class="tracking">📦 ${esc(it.stop.tracking_number)}</div>` : ""}
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

// ---------- הזנה קולית (Web Speech API, עברית) ----------
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
let activeRec = null;

const HEB_DIGITS = {
  "אפס": "0", "אחת": "1", "אחד": "1", "שתיים": "2", "שתים": "2", "שניים": "2", "שנים": "2",
  "שלוש": "3", "שלש": "3", "ארבע": "4", "ארבעה": "4", "חמש": "5", "חמישה": "5", "שש": "6", "שישה": "6",
  "שבע": "7", "שבעה": "7", "שמונה": "8", "תשע": "9", "תשעה": "9",
};

/** ממיר טלפון שהוכתב ("אפס חמש שתיים 123...") לספרות בלבד. */
function spokenToPhone(text) {
  return text.split(/\s+/).map((w) => {
    const word = w.replace(/[^\dא-ת+]/g, "");
    if (/^[\d+]+$/.test(word)) return word;
    const bare = word.startsWith("ו") && HEB_DIGITS[word.slice(1)] ? word.slice(1) : word;
    return HEB_DIGITS[bare] || "";
  }).join("");
}

function stopListening() {
  if (activeRec) { try { activeRec.stop(); } catch (_) { /* */ } }
}

function startListening(btn) {
  const field = document.getElementById(btn.dataset.mic);
  if (!field) return;
  if (activeRec) { const same = activeRec._btn === btn; stopListening(); if (same) return; }
  const mode = btn.dataset.micMode || "replace";
  const base = field.value.trim();
  const rec = new SpeechRec();
  rec.lang = "he-IL";
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  rec._btn = btn;
  activeRec = rec;
  btn.classList.add("listening");

  rec.onresult = (ev) => {
    let text = "";
    for (let i = 0; i < ev.results.length; i++) text += ev.results[i][0].transcript;
    text = text.trim();
    if (mode === "phone") field.value = spokenToPhone(text) || field.value;
    else if (mode === "append" && base) field.value = `${base} ${text}`;
    else field.value = text;
    field.dispatchEvent(new Event("input", { bubbles: true }));
  };
  rec.onerror = (ev) => {
    const msg = {
      "not-allowed": "אין הרשאה למיקרופון. אשר גישה למיקרופון בהגדרות האתר בדפדפן.",
      "service-not-allowed": "אין הרשאה למיקרופון. אשר גישה למיקרופון בהגדרות האתר בדפדפן.",
      "no-speech": "לא שמעתי דיבור. נסה שוב ודבר קרוב לטלפון.",
      "audio-capture": "לא נמצא מיקרופון פעיל בטלפון.",
      "network": "זיהוי דיבור דורש חיבור לאינטרנט.",
    }[ev.error];
    if (msg) toast(msg, true);
  };
  rec.onend = () => {
    btn.classList.remove("listening");
    if (activeRec === rec) activeRec = null;
    field.focus();
  };
  try { rec.start(); }
  catch (_) { btn.classList.remove("listening"); activeRec = null; }
}

if (SpeechRec) {
  document.querySelectorAll(".mic-btn").forEach((b) => (b.onclick = () => startListening(b)));
  document.querySelectorAll("dialog").forEach((d) => d.addEventListener("close", stopListening));
} else {
  document.body.classList.add("no-voice"); // הדפדפן לא תומך: מסתירים את המיקרופונים
}

// ---------- מראה (בהיר / כהה / אוטומטי) ----------
const THEME_COLORS = { light: "#5B2FF0", dark: "#19162F" };
function currentTheme() {
  try { return localStorage.getItem("theme") || "light"; } catch (_) { return "light"; }
}
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const dark = theme === "dark" || (theme === "auto" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", dark ? THEME_COLORS.dark : THEME_COLORS.light);
}
document.querySelectorAll('input[name="theme"]').forEach((r) => {
  r.checked = r.value === currentTheme();
  r.addEventListener("change", () => {
    try { localStorage.setItem("theme", r.value); } catch (_) { /* בלי שמירה: רק לביקור הזה */ }
    applyTheme(r.value);
  });
});
window.matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => applyTheme(currentTheme()));
applyTheme(currentTheme());

// ---------- הצעות לקוחות בזמן הקלדה (שדה הכתובת במסך המשלוחים) ----------
const sug = { timer: null, seq: 0, items: [], active: -1 };

function hideSuggest() {
  $("#suggest").hidden = true;
  $("#add-address").setAttribute("aria-expanded", "false");
  sug.items = [];
  sug.active = -1;
}

function renderSuggest(query) {
  const ul = $("#suggest");
  ul.innerHTML = "";
  sug.items.forEach((c, i) => {
    const li = document.createElement("li");
    li.setAttribute("role", "option");
    li.className = (c.in_today ? "in-today" : "") + (i === sug.active ? " active" : "");
    li.innerHTML = `
      <span class="s-name">👤 ${esc(c.recipient || "ללא שם")}</span>
      <span class="s-addr">${esc(c.address)}${c.address_details ? " · " + esc(c.address_details) : ""}</span>
      <span class="s-meta" dir="ltr">${esc(c.phone || "")}</span>`;
    li.addEventListener("pointerdown", (e) => e.preventDefault()); // לא לאבד פוקוס לפני הבחירה
    li.addEventListener("click", () => pickCustomer(c));
    ul.appendChild(li);
  });
  const add = document.createElement("li");
  add.className = "new-addr" + (sug.active === sug.items.length ? " active" : "");
  add.textContent = `➕ הוסף ככתובת חדשה: "${query}"`;
  add.addEventListener("pointerdown", (e) => e.preventDefault());
  add.addEventListener("click", () => { hideSuggest(); $("#add-form").requestSubmit(); });
  ul.appendChild(add);
  ul.hidden = false;
  $("#add-address").setAttribute("aria-expanded", "true");
}

async function pickCustomer(c) {
  if (c.in_today) { toast(`${c.recipient || c.address} כבר ברשימת המשלוחים של היום`); return; }
  hideSuggest();
  busy(true, "מוסיף משלוח...");
  try {
    const res = await api(`/api/customers/${c.id}/add-stop`, { method: "POST" });
    if (res.geocode_error) toast(res.geocode_error, true);
    else toast(`נוסף: ${c.recipient || c.address}`);
    $("#add-address").value = "";
    state.route = null;
    await loadStops();
  } catch (err) { toast(err.message, true); }
  finally { busy(false); }
}

$("#add-address").addEventListener("input", () => {
  clearTimeout(sug.timer);
  const q = $("#add-address").value.trim();
  if (q.length < 2) { hideSuggest(); return; }
  sug.timer = setTimeout(async () => {
    const my = ++sug.seq;
    try {
      const rows = await api(`/api/customers/search?q=${encodeURIComponent(q)}`);
      if (my !== sug.seq) return; // תשובה ישנה
      sug.items = rows;
      sug.active = -1;
      if (rows.length) renderSuggest(q); else hideSuggest();
    } catch (_) { hideSuggest(); }
  }, 200);
});

$("#add-address").addEventListener("keydown", (e) => {
  if ($("#suggest").hidden) return;
  const n = sug.items.length + 1; // כולל "כתובת חדשה"
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    sug.active = (sug.active + (e.key === "ArrowDown" ? 1 : -1) + n) % n;
    renderSuggest($("#add-address").value.trim());
  } else if (e.key === "Enter" && sug.active >= 0 && sug.active < sug.items.length) {
    e.preventDefault();
    pickCustomer(sug.items[sug.active]);
  } else if (e.key === "Escape") {
    hideSuggest();
  }
});
$("#add-address").addEventListener("blur", () => setTimeout(hideSuggest, 150));
$("#add-form").addEventListener("submit", () => hideSuggest(), true);

// ---------- דף לקוחות (DataTables) ----------
const cust = { table: null, loading: null, editing: null, pickMap: null, pickMarker: null };

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = src; el.onload = resolve; el.onerror = () => reject(new Error("טעינת " + src + " נכשלה"));
    document.head.appendChild(el);
  });
}
function loadCss(href) {
  const el = document.createElement("link");
  el.rel = "stylesheet"; el.href = href;
  document.head.insertBefore(el, document.querySelector('link[href^="/styles.css"]'));
}

/** DataTables נטען רק כשנכנסים לדף הלקוחות, כדי שהאפליקציה תיפתח מהר. */
function ensureDataTables() {
  if (!cust.loading) {
    loadCss("/vendor/datatables/dataTables.dataTables.min.css");
    cust.loading = loadScript("/vendor/datatables/jquery.min.js")
      .then(() => loadScript("/vendor/datatables/dataTables.min.js"));
  }
  return cust.loading;
}

const DT_HEBREW = {
  search: "חיפוש:", searchPlaceholder: "שם, כתובת או טלפון", lengthMenu: "הצג _MENU_",
  info: "_START_–_END_ מתוך _TOTAL_ לקוחות", infoEmpty: "אין לקוחות", infoFiltered: "(מסונן מתוך _MAX_)",
  zeroRecords: "לא נמצאו לקוחות מתאימים", emptyTable: "עדיין אין לקוחות. הם נוספים אוטומטית מכל משלוח עם טלפון.",
  loadingRecords: "טוען...", paginate: { first: "«", last: "»", next: "›", previous: "‹" },
};

async function loadCustomers() {
  try {
    await ensureDataTables();
    const rows = await api("/api/customers");
    $("#customers-loading").hidden = true;
    if (!cust.table) {
      cust.table = new window.DataTable("#customers-table", {
        data: rows,
        language: DT_HEBREW,
        order: [[1, "asc"]],
        pageLength: 25,
        autoWidth: false,
        layout: { topStart: "search", topEnd: null, bottomStart: "info", bottomEnd: "paging" },
        columns: [
          { data: "id", title: "ID", className: "col-id" },
          { data: "recipient", title: "שם", className: "col-name", render: (d) => esc(d || "") },
          { data: null, title: "פעולות", orderable: false, searchable: false,
            render: (_d, _t, row) => `<span class="c-acts">
              <button type="button" data-act="add" data-id="${row.id}" title="הוסף כמשלוח היום" aria-label="הוסף כמשלוח היום">➕</button>
              <button type="button" data-act="edit" data-id="${row.id}" title="עריכה" aria-label="עריכה">✏️</button>
              <button type="button" data-act="del" data-id="${row.id}" title="מחיקה" aria-label="מחיקה">🗑️</button></span>` },
          { data: "phone", title: "טלפון",
            render: (d, type) => type === "display" ? `<a href="tel:${esc((d || "").replace(/[^\d+]/g, ""))}" dir="ltr">${esc(d || "")}</a>` : (d || "") },
          { data: "address", title: "כתובת ראשית",
            render: (d, type, row) => type === "display" ? esc(d || "") + (row.geocoded ? "" : ' <span class="geo-warn">⚠ לא אותרה</span>') : (d || "") },
          { data: "address_details", title: "כתובת מפורטת", className: "wrap", render: (d) => esc(d || "") },
          { data: "notes", title: "הערות", className: "wrap", render: (d) => esc(d || "") },
        ],
      });
      // גלילה אופקית לטבלה בלבד (לא לכל הדף)
      const tableEl = document.querySelector("#customers-table");
      const wrap = document.createElement("div");
      wrap.className = "cust-scroll";
      tableEl.parentNode.insertBefore(wrap, tableEl);
      wrap.appendChild(tableEl);
      const hint = document.createElement("p");
      hint.className = "scroll-hint";
      hint.textContent = "⇠ גלול הצידה לעמודות נוספות";
      wrap.parentNode.insertBefore(hint, wrap);
    } else {
      cust.table.clear().rows.add(rows).draw(false);
    }
  } catch (e) { toast(e.message, true); }
}

function customerById(id) {
  return cust.table ? cust.table.rows().data().toArray().find((r) => r.id === id) : null;
}

$("#customers-table").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  const c = customerById(Number(btn.dataset.id));
  if (!c) return;
  if (btn.dataset.act === "edit") openCustomerDialog(c);
  else if (btn.dataset.act === "add") {
    try {
      const res = await api(`/api/customers/${c.id}/add-stop`, { method: "POST" });
      toast(res.geocode_error || `נוסף למשלוחי היום: ${c.recipient || c.address}`, !!res.geocode_error);
      state.route = null;
      await loadStops();
    } catch (err) { toast(err.message, true); }
  } else if (btn.dataset.act === "del") {
    if (!confirm(`למחוק את הלקוח "${c.recipient || c.address}"?\nהלקוח יוסתר מהרשימה. משלוחים קודמים לא יימחקו.`)) return;
    try {
      await api(`/api/customers/${c.id}`, { method: "DELETE" });
      toast("הלקוח נמחק");
      await loadCustomers();
    } catch (err) { toast(err.message, true); }
  }
});

$("#customer-new").onclick = () => openCustomerDialog(null);

function openCustomerDialog(c) {
  cust.editing = { c, lat: null, lon: null };
  $("#customer-dialog-title").textContent = c ? "עריכת לקוח" : "לקוח חדש";
  $("#c-id").hidden = !c;
  $("#c-id").textContent = c ? `ID ${c.id} · ${c.delivery_count || 0} משלוחים` : "";
  $("#c-recipient").value = c?.recipient || "";
  $("#c-phone").value = c?.phone || "";
  $("#c-address").value = c?.address || "";
  $("#c-details").value = c?.address_details || "";
  $("#c-notes").value = c?.notes || "";
  $("#c-geo").textContent = c?.geocode_label ? `📍 ${c.geocode_label}` : (c ? "⚠ הכתובת לא אותרה במפה" : "");
  $("#c-pick-map").hidden = true;
  $("#customer-error").textContent = "";
  $("#customer-dialog").showModal();
}

$("#c-pick-on-map").onclick = () => {
  const el = $("#c-pick-map");
  el.hidden = false;
  const c = cust.editing.c;
  const center = c && c.geocoded ? [c.lat, c.lon] : [32.0853, 34.7818];
  const zoom = c && c.geocoded ? 17 : 12;
  if (!cust.pickMap) {
    cust.pickMap = L.map(el).setView(center, zoom);
    addTiles(cust.pickMap);
    cust.pickMap.on("click", (ev) => {
      cust.editing.lat = ev.latlng.lat;
      cust.editing.lon = ev.latlng.lng;
      if (cust.pickMarker) cust.pickMarker.setLatLng(ev.latlng);
      else cust.pickMarker = L.marker(ev.latlng).addTo(cust.pickMap);
      $("#c-geo").textContent = "📍 נבחר מיקום ידני על המפה";
    });
  } else {
    cust.pickMap.setView(center, zoom);
    if (cust.pickMarker) { cust.pickMarker.remove(); cust.pickMarker = null; }
  }
  setTimeout(() => cust.pickMap.invalidateSize(), 50);
  toast("הקש על המפה במקום המסירה");
};

$("#customer-form").addEventListener("submit", async (e) => {
  if (!e.submitter || e.submitter.value !== "save") return; // ביטול
  e.preventDefault();
  const ed = cust.editing;
  const payload = {
    recipient: $("#c-recipient").value.trim() || null,
    phone: $("#c-phone").value.trim(),
    address: $("#c-address").value.trim(),
    address_details: $("#c-details").value.trim() || null,
    notes: $("#c-notes").value.trim() || null,
  };
  if (ed.lat != null) { payload.lat = ed.lat; payload.lon = ed.lon; }
  busy(true, "שומר...");
  try {
    const res = ed.c
      ? await api(`/api/customers/${ed.c.id}`, { method: "PATCH", json: payload })
      : await api("/api/customers", { json: payload });
    $("#customer-dialog").close();
    toast(res.geocode_error || "הלקוח נשמר", !!res.geocode_error);
    await loadCustomers();
  } catch (err) {
    $("#customer-error").textContent = err.message;
  } finally { busy(false); }
});

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
    await loadWindows();
    state.route = await api("/api/route/current");
    await loadStops();
  } catch (e) { toast(e.message, true); }
  showView(state.view);
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

boot();
