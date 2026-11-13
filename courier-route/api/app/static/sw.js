/* Service worker: שומר את קבצי האפליקציה כדי שתיפתח מהר גם בקליטה חלשה.
   בקשות API לא נשמרות במטמון - תמיד מהשרת. */
const CACHE = "courier-shell-v15";
const SHELL = [
  "/", "/index.html", "/styles.css?v=15", "/app.js?v=15", "/manifest.webmanifest",
  "/vendor/leaflet.js", "/vendor/leaflet.css", "/vendor/fonts/rubik.css", "/icons/icon-192.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  // רשת קודם (כדי לקבל עדכונים), מטמון כגיבוי כשאין קליטה
  e.respondWith(
    fetch(e.request, { cache: "no-cache" })
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match("/index.html")))
  );
});
