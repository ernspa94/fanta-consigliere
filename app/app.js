// Legge output/consiglio.json direttamente dal repository: si aggiorna appena il workflow fa un commit,
// senza dover ripubblicare l'app.
const FONTE = "https://raw.githubusercontent.com/ernspa94/fanta-consigliere/main/output/consiglio.json";

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
  const nota = g.nota ? `${g.stato[0].toUpperCase() + g.stato.slice(1)}: ${g.nota}` : null;
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

function mostra(c) {
  $("squadra").textContent = c.squadra;
  $("sottotitolo").textContent = `Giornata ${c.giornata} · Fanta Lignano`;
  $("modulo").textContent = c.modulo;
  $("punti").textContent = num(c.punti_attesi);
  $("intervallo").textContent = `8 volte su 10 tra ${num(c.intervallo_80[0])} e ${num(c.intervallo_80[1])}`;

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
    el("li", { class: a.modulo === c.modulo ? "scelto" : "" }, el("span", {}, a.modulo), el("span", {}, num(a.punti_attesi)))));

  const quando = new Date(c.aggiornato);
  $("aggiornato").textContent = `Consiglio cambiato l'ultima volta ${quando.toLocaleString("it-IT", {
    weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}`;

  $("contenuto").hidden = false;
  $("errore").hidden = true;
}

async function carica() {
  $("ricarica").disabled = true;
  try {
    const r = await fetch(`${FONTE}?t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const c = await r.json();
    try { localStorage.setItem("consiglio", JSON.stringify(c)); } catch {}
    mostra(c);
  } catch (e) {
    let salvato = null;
    try { salvato = JSON.parse(localStorage.getItem("consiglio")); } catch {}
    if (salvato) {
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

$("ricarica").addEventListener("click", carica);
document.addEventListener("visibilitychange", () => { if (!document.hidden) carica(); });
carica();

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
