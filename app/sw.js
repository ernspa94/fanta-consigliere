// Tiene in cache i file dell'app, così si apre anche senza rete.
// Il consiglio non passa da qui: app.js lo scarica sempre fresco e ne tiene una copia in localStorage.
const VERSIONE = "v5";
const FILE = ["./", "index.html", "style.css", "config.js", "app.js", "manifest.webmanifest", "icons/icon-180.png", "icons/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSIONE).then((c) => c.addAll(FILE)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((chiavi) => Promise.all(chiavi.filter((k) => k !== VERSIONE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

// Notifiche mandate dal workflow (engine/fanta/notifiche.py): {titolo, testo, url}.
self.addEventListener("push", (e) => {
  let n = { titolo: "Fanta Consigliere", testo: "", url: "./" };
  try { n = { ...n, ...e.data.json() }; } catch {}
  e.waitUntil(self.registration.showNotification(n.titolo, {
    body: n.testo,
    icon: "icons/icon-192.png",
    badge: "icons/icon-192.png",
    data: { url: n.url },
  }));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((finestre) => {
    const url = e.notification.data.url || "./";
    // Porta l'app sulla squadra della notifica (l'url contiene ?squadra=<codice>).
    for (const f of finestre) if ("focus" in f) return f.navigate(url).then((w) => (w || f).focus());
    return self.clients.openWindow(url);
  }));
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
