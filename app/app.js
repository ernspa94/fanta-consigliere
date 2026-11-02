// Legge output/ direttamente dal repository: si aggiorna appena il workflow fa un commit,
// senza dover ripubblicare l'app.
// Con ?locale legge ../output/ (per provare l'app con dati di prova servendo la cartella del progetto).
const OUTPUT = new URLSearchParams(location.search).has("locale")
  ? "../output/" : "https://raw.githubusercontent.com/ernspa94/fanta-consigliere/main/output/";
const VAPID_PUBBLICA = "BKxnXkLdxzZeb3RJUsDxEcJpSKHgkDbZt0mHGXa6cjIw0y0nSHNisqKBPiWrnKlYXPVDwLXrG3E2ljxq_v0Hj5I";

let attuale = null; // consiglio della prossima giornata
let attivo = null;  // consiglio mostrato ora (prossima giornata o storico)

const $ = (id) => document.getElementById(id);
const sigla = (sq) => (sq || "").slice(0, 3).toUpperCase();
const nomeSquadra = (sq) => (sq || "").split("-").map((p) => p[0].toUpperCase() + p.slice(1)).join(" ");
const pct = (x) => `${Math.round(x * 100)}%`;
const num = (x, d = 1) => (x == null ? "–" : x.toFixed(d).replace(".", ","));

function partita(g) {
  if (!g.avversario) return "non gioca";
  return g.casa ? `vs ${sigla(g.avversario)}` : `@ ${sigla(g.avversario)}`;
}

function classeVoto(p) {
  return p >= 0.85 ? "ok" : p >= 0.6 ? "warn" : "bad";
}

function el(tag, attrs = {}, ...figli) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const f of figli) if (f != null) e.append(f);
  return e;
}

function apriDettaglio(g) {
  $("d-nome").textContent = g.nome;
  $("d-partita").textContent = g.avversario
    ? `${nomeSquadra(g.squadra)} ${g.casa ? "in casa contro" : "in trasferta contro"} ${nomeSquadra(g.avversario)}`
    : `${nomeSquadra(g.squadra)} non gioca questa giornata`;
  $("d-voto").textContent = pct(g.p_voto);
  $("d-fv").textContent = num(g.fantavoto_se_gioca);
  $("d-attesi").textContent = num(g.punti_attesi, 2);
  const righe = [];
  if (g.rigorista) righe.push(`Rigorista n°${g.rigorista} della squadra.`);
  if (g.nota) righe.push(`${g.stato[0].toUpperCase() + g.stato.slice(1)}: ${g.nota}`);
  const nota = righe.length ? righe.join(" ") : null;
  $("d-nota").hidden = !nota;
  $("d-nota").textContent = nota || "";
  $("dettaglio").showModal();
}

function chip(g) {
  return el("button", { class: "giocatore", onclick: () => apriDettaglio(g) },
    el("span", { class: "nome" }, g.nome),
    el("span", { class: "avv" }, partita(g)),
    el("span", { class: `badge ${classeVoto(g.p_voto)}` }, pct(g.p_voto)));
}

function riga(g) {
  return el("li", {},
    el("button", { onclick: () => apriDettaglio(g) },
      el("span", { class: `ruolo ${g.ruolo}` }, g.ruolo),
      el("span", { class: "info" },
        el("div", { class: "nome-riga" }, g.nome),
        el("div", { class: "sotto" }, `${nomeSquadra(g.squadra)} ${partita(g)} · voto ${pct(g.p_voto)} · se gioca ${num(g.fantavoto_se_gioca)}`)),
      el("span", { class: `badge ${classeVoto(g.p_voto)}` }, num(g.punti_attesi))));
}

const dataOra = (iso) => new Date(iso).toLocaleString("it-IT", {
  weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });

function mostraScadenza(c, storico) {
  const box = $("scadenza-box");
  box.hidden = !c.scadenza || storico;
  if (box.hidden) return;
  const ore = (new Date(c.scadenza) - Date.now()) / 36e5;
  $("scadenza").textContent = ore > 0
    ? `Consegna entro ${dataOra(c.scadenza)}${ore < 24 ? ` (tra ${ore < 1 ? Math.round(ore * 60) + " min" : Math.round(ore) + " ore"})` : ""}`
    : "Scadenza passata";
  $("scadenza").classList.toggle("vicina", ore > 0 && ore < 3);
}

function mostra(c, storico = false) {
  attivo = { c, storico };
  $("squadra").textContent = c.squadra;
  $("sottotitolo").textContent = `Giornata ${c.giornata} · Fanta Lignano`;
  $("contenuto").hidden = false;
  $("errore").hidden = true;
  mostraScadenza(c, storico);

  const inAttesa = c.stato === "in_attesa";
  $("attesa").hidden = !inAttesa;
  $("formazione").hidden = inAttesa;
  $("storico-nota").hidden = !storico;
  $("storico-nota").textContent = storico
    ? `Consiglio dato prima della scadenza della giornata ${c.giornata}, con le probabili di quel momento.` : "";
  if (inAttesa) {
    $("attesa-titolo").textContent = `Giornata ${c.giornata}: in attesa delle probabili`;
    $("aggiornato").textContent = "";
    return;
  }

  mostraFormazione(c, c);
  $("aggiornato").textContent = `Consiglio cambiato l'ultima volta ${dataOra(c.aggiornato)}`;
}

// Mostra la migliore formazione di un altro modulo (le alternative contengono solo i nomi).
function mostraModulo(c, modulo) {
  const a = c.alternative.find((x) => x.modulo === modulo);
  if (!a || !a.titolari) return;
  const scheda = Object.fromEntries([...c.titolari, ...c.panchina].map((g) => [g.nome, g]));
  mostraFormazione(c, { ...a, titolari: a.titolari.map((n) => scheda[n]), panchina: a.panchina.map((n) => scheda[n]) });
  document.querySelector(".riepilogo").scrollIntoView({ behavior: "smooth", block: "start" });
}

function mostraFormazione(c, f) {
  const consigliato = f.modulo === c.modulo;
  $("modulo").textContent = f.modulo;
  $("modulo-nota").textContent = consigliato ? "consigliato" : `consigliato: ${c.modulo}`;
  $("punti").textContent = num(f.punti_attesi);
  $("intervallo").textContent = f.intervallo_80
    ? `8 volte su 10 tra ${num(f.intervallo_80[0])} e ${num(f.intervallo_80[1])}` : "";
  // Il resto della funzione usa `c` per i dati della formazione mostrata.
  c = { ...c, ...f };

  // Probabilità di 0, 1, …, 5+ gol.
  const prob = Object.values(c.prob_gol);
  prob[prob.length - 1] += Math.max(0, 1 - prob.reduce((a, b) => a + b, 0));
  const max = Math.max(...prob);
  $("gol").replaceChildren(...prob.map((p, i) =>
    el("div", { class: "colonna" },
      el("span", { class: "pct" }, pct(p)),
      el("div", { class: "barra", style: `height:${(p / max) * 70}%` }),
      el("span", { class: "n" }, i === prob.length - 1 ? `${i}+` : `${i}`))));
  $("extra").textContent = `Modificatore difesa atteso +${num(c.modificatore_atteso)} · cambi attesi ${num(c.cambi_attesi)}`;

  for (const linea of document.querySelectorAll(".linea")) {
    linea.replaceChildren(...c.titolari.filter((g) => g.ruolo === linea.dataset.ruolo).map(chip));
  }

  const disponibili = c.panchina.filter((g) => g.p_voto > 0);
  const fuori = c.panchina.filter((g) => g.p_voto === 0);
  $("panchina").replaceChildren(...disponibili.map(riga));
  $("box-avvisi").hidden = fuori.length === 0;
  $("avvisi").replaceChildren(...fuori.map((g) =>
    el("li", {},
      el("span", { class: `ruolo ${g.ruolo}` }, g.ruolo),
      el("span", { class: "info" },
        el("div", { class: "nome-riga" }, g.nome),
        el("div", { class: "sotto" }, g.nota || g.stato)))));

  $("alternative").replaceChildren(...c.alternative.map((a) =>
    el("li", { class: a.modulo === f.modulo ? "scelto" : "" },
      el("button", { onclick: () => (a.modulo === attivo.c.modulo ? mostra(attivo.c, attivo.storico) : mostraModulo(attivo.c, a.modulo)) },
        el("span", {}, a.modulo), el("span", {}, num(a.punti_attesi))))));
  $("moduli-aiuto").hidden = !c.alternative.some((a) => a.titolari);
}

async function scarica(percorso) {
  const r = await fetch(`${OUTPUT}${percorso}?t=${Date.now()}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// Menu giornate: la prossima (consiglio attuale) e quelle passate salvate nello storico.
function riempiGiornate(indice) {
  const sel = $("giornata");
  const passate = (indice.giornate || [])
    .filter((g) => !(attuale.stato === "pronto" && g === attuale.giornata))
    .sort((a, b) => b - a);
  sel.replaceChildren(
    el("option", { value: "attuale" }, `${attuale.giornata} · prossima`),
    ...passate.map((g) => el("option", { value: String(g) }, `${g} · giocata`)));
  $("box-giornata").hidden = passate.length === 0;
}

$("giornata").addEventListener("change", async (e) => {
  const v = e.target.value;
  if (v === "attuale") return mostra(attuale);
  try {
    mostra(await scarica(`storico/giornata-${v.padStart(2, "0")}.json`), true);
  } catch (err) {
    $("errore").textContent = `Non riesco a caricare la giornata ${v} (${err.message}).`;
    $("errore").hidden = false;
  }
});

async function carica() {
  $("ricarica").disabled = true;
  try {
    attuale = await scarica("consiglio.json");
    try { localStorage.setItem("consiglio", JSON.stringify(attuale)); } catch {}
    mostra(attuale);
    riempiGiornate(await scarica("storico/indice.json").catch(() => ({})));
  } catch (e) {
    let salvato = null;
    try { salvato = JSON.parse(localStorage.getItem("consiglio")); } catch {}
    if (salvato) {
      attuale = salvato;
      mostra(salvato);
      $("sottotitolo").textContent += " · offline";
    } else {
      $("errore").textContent = `Non riesco a scaricare il consiglio (${e.message}). Riprova tra poco.`;
      $("errore").hidden = false;
    }
  } finally {
    $("ricarica").disabled = false;
  }
}

$("ricarica").addEventListener("click", () => { $("giornata").value = "attuale"; carica(); });
document.addEventListener("visibilitychange", () => {
  // Ricarica tornando sull'app, ma non se si sta guardando una giornata passata.
  if (!document.hidden && ($("giornata").value || "attuale") === "attuale") carica();
});
carica();

// --- Notifiche push ---------------------------------------------------------------
// Su iPhone funzionano solo con l'app aggiunta alla schermata Home (iOS 16.4+).
// Il "codice" è l'iscrizione push di questo dispositivo: va salvato nei segreti del repository,
// da cui il workflow lo legge per mandare gli avvisi.

const installata = () => navigator.standalone === true || matchMedia("(display-mode: standalone)").matches;

function chiaveVapid() {
  const b64 = (VAPID_PUBBLICA + "=".repeat((4 - (VAPID_PUBBLICA.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

function mostraCodice(iscrizione) {
  let nome = "";
  try { nome = localStorage.getItem("nome") || ""; } catch {}
  $("codice").value = JSON.stringify({ nome, iscrizione: iscrizione.toJSON() });
  $("codice-dialog").showModal();
}

async function preparaNotifiche() {
  const testo = $("notifiche-testo");
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !installata()) {
    testo.textContent = "Per ricevere gli avvisi (formazione cambiata, promemoria prima della consegna) " +
      "apri questa pagina con Safari, tocca Condividi → Aggiungi alla schermata Home e apri l'app da lì.";
    return;
  }
  const reg = await navigator.serviceWorker.ready;
  const iscrizione = await reg.pushManager.getSubscription();
  if (iscrizione) {
    testo.textContent = "Notifiche attive su questo iPhone. Se non arrivano, controlla che il codice sia stato aggiunto.";
    $("notifiche-codice").hidden = false;
    $("notifiche-codice").onclick = () => mostraCodice(iscrizione);
  } else {
    testo.textContent = "Ricevi un avviso quando esce il consiglio, quando cambia la formazione e prima della consegna.";
    $("notifiche-azioni").hidden = false;
  }
}

$("notifiche-attiva").addEventListener("click", async () => {
  const nome = $("notifiche-nome").value.trim();
  if (!nome) return $("notifiche-nome").focus();
  try { localStorage.setItem("nome", nome); } catch {}
  if ((await Notification.requestPermission()) !== "granted") {
    $("notifiche-testo").textContent = "Permesso negato. Puoi riattivarlo da Impostazioni → Notifiche → Consigliere.";
    return;
  }
  const reg = await navigator.serviceWorker.ready;
  const iscrizione = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: chiaveVapid() });
  $("notifiche-azioni").hidden = true;
  await preparaNotifiche();
  mostraCodice(iscrizione);
});

$("copia").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("codice").value);
    $("copia").textContent = "Copiato ✓";
  } catch {
    $("codice").select();
  }
});

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
preparaNotifiche();
