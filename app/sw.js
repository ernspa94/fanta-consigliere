// Tiene in cache i file dell'app, così si apre anche senza rete.
// Il consiglio non passa da qui: app.js lo scarica sempre fresco e ne tiene una copia in localStorage.
const VERSIONE = "v1";
const FILE = ["./", "index.html", "style.css", "app.js", "manifest.webmanifest", "icons/icon-180.png", "icons/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSIONE).then((c) => c.addAll(FILE)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((chiavi) => Promise.all(chiavi.filter((k) => k !== VERSIONE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;
  // Prima la rete (per avere sempre l'ultima versione dell'app), la cache se offline.
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        const copia = r.clone();
        caches.open(VERSIONE).then((c) => c.put(e.request, copia));
        return r;
      })
      .catch(() => caches.match(e.request))
  );
});
