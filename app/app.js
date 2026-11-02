// Fanta Consigliere: più squadre, ognuna con un codice segreto (niente registrazione).
// Squadre, rose, regolamenti e consigli stanno su Supabase: l'app chiama solo le funzioni
// di supabase/schema.sql, che vogliono sempre il codice della squadra.

const C = window.CONFIG;
const $ = (id) => document.getElementById(id);
const sigla = (sq) => (sq || "").slice(0, 3).toUpperCase();
const nomeSquadra = (sq) => (sq || "").split("-").map((p) => p[0].toUpperCase() + p.slice(1)).join(" ");
const pct = (x) => `${Math.round(x * 100)}%`;
const num = (x, d = 1) => (x == null ? "–" : x.toFixed(d).replace(".", ","));
const clona = (x) => JSON.parse(JSON.stringify(x));
const normalizza = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const dataOra = (iso) => new Date(iso).toLocaleString("it-IT", {
  weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });

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

function mostraErrore(messaggio) {
  $("errore").textContent = messaggio;
  $("errore").hidden = !messaggio;
  if (messaggio) window.scrollTo({ top: 0, behavior: "smooth" });
}

// --- Memoria del telefono: le squadre che segue (solo comodità, la verità è sul server) ---------------

function leggiLocale(chiave, predefinito) {
  try { return JSON.parse(localStorage.getItem(chiave)) ?? predefinito; } catch { return predefinito; }
}
function scriviLocale(chiave, valore) {
  try { valore == null ? localStorage.removeItem(chiave) : localStorage.setItem(chiave, JSON.stringify(valore)); } catch {}
}
const mieSquadre = () => leggiLocale("squadre", []);
function ricordaSquadra(s) {
  scriviLocale("squadre", [{ codice: s.codice, nome: s.nome, lega: s.lega || "" },
    ...mieSquadre().filter((x) => x.codice !== s.codice)]);
}
function dimenticaSquadra(codice) {
  scriviLocale("squadre", mieSquadre().filter((x) => x.codice !== codice));
  scriviLocale(`consiglio:${codice}`, null);
  scriviLocale(`notifiche:${codice}`, null);
}

// --- Server ----------------------------------------------------------------------------------------

async function rpc(funzione, parametri) {
  if (!C.SUPABASE_URL) throw new Error("L'app non è ancora collegata al database.");
  const r = await fetch(`${C.SUPABASE_URL}/rest/v1/rpc/${funzione}`, {
    method: "POST",
    headers: { apikey: C.SUPABASE_ANON_KEY, Authorization: `Bearer ${C.SUPABASE_ANON_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify(parametri),
  });
  const testo = await r.text();
  const dati = testo ? JSON.parse(testo) : null;
  if (!r.ok) throw new Error(dati?.message || `Errore ${r.status}`);
  return dati;
}

async function pubblico(percorso) {
  const r = await fetch(`${C.RAW}${percorso}?t=${Date.now()}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

let listone = null;
const caricaListone = async () => (listone ??= await pubblico("output/listone.json"));

const MODELLI = [
  { id: "standard", nome: "Standard Leghe Fantacalcio" },
  { id: "fanta-lignano", nome: "Fanta Lignano" },
];
const caricaModello = (id) => pubblico(`config/regole/${id}.json`);

for (const sel of [document.querySelector("#form-crea select[name=modello]"), $("regole-modello")]) {
  sel.replaceChildren(...MODELLI.map((m) => el("option", { value: m.id }, m.nome)));
}

// --- Stato ------------------------------------------------------------------------------------------

let squadra = null; // come sul server
let bozza = null;   // copia che si modifica nelle schede Rosa, Regolamento, Condividi
let attuale = null; // consiglio più recente
let attivo = null;  // consiglio mostrato ora (più recente o di una giornata passata)

const modificabili = (s) => JSON.stringify([s.nome, s.lega || "", s.rosa, s.regole]);
const modificata = () => squadra && bozza && modificabili(squadra) !== modificabili(bozza);
const aggiornaBarra = () => { $("barra-salva").hidden = !modificata(); };

// --- Navigazione: #/  oppure  #/s/<codice>/<scheda> ------------------------------------------------

const vai = (hash) => { location.hash = hash; };

async function instrada() {
  mostraErrore("");
  const m = location.hash.match(/^#\/s\/([0-9a-z]+)(?:\/(\w+))?/i);
  try {
    if (m) await apriSquadra(m[1].toLowerCase(), m[2] || "consiglio");
    else mostraHome(location.hash === "#/asta" ? "asta" : "squadre");
  } catch (e) {
    mostraHome();
    mostraErrore(e.message);
  }
}

window.addEventListener("hashchange", instrada);

$("indietro").addEventListener("click", () => {
  if (modificata() && !confirm("Ci sono modifiche non salvate. Uscire lo stesso?")) return;
  squadra = bozza = null;
  vai("#/");
});

// --- Home -------------------------------------------------------------------------------------------

for (const b of document.querySelectorAll("#schede-home button")) {
  b.addEventListener("click", () => vai(b.dataset.home === "asta" ? "#/asta" : "#/"));
}

function mostraHome(scheda = "squadre") {
  squadra = bozza = null;
  $("home").hidden = false;
  for (const b of document.querySelectorAll("#schede-home button")) b.classList.toggle("attiva", b.dataset.home === scheda);
  $("home-squadre").hidden = scheda !== "squadre";
  $("home-asta").hidden = scheda !== "asta";
  if (scheda === "asta") disegnaAsta();
  $("squadra").hidden = true;
  $("indietro").hidden = $("ricarica").hidden = true;
  $("titolo").textContent = "Fanta Consigliere";
  $("sottotitolo").textContent = "Le formazioni consigliate per le tue squadre";
  const lista = mieSquadre();
  $("nessuna-squadra").hidden = lista.length > 0;
  $("mie-squadre").replaceChildren(...lista.map((s) =>
    el("li", {},
      el("button", { onclick: () => vai(`#/s/${s.codice}`) },
        el("span", { class: "info" }, el("div", { class: "nome-riga" }, s.nome), el("div", { class: "sotto" }, s.lega)),
        el("span", { class: "freccia" }, "›")))));
  if (!C.SUPABASE_URL) mostraErrore("App in aggiornamento: il database non è ancora collegato.");
}

$("form-crea").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  f.querySelector("button").disabled = true;
  try {
    const regole = await caricaModello(f.modello.value);
    const codice = await rpc("crea_squadra", { p_nome: f.nome.value, p_lega: f.lega.value, p_regole: regole });
    ricordaSquadra({ codice, nome: f.nome.value.trim(), lega: f.lega.value.trim() });
    f.reset();
    vai(`#/s/${codice}/rosa`);
  } catch (err) {
    mostraErrore(`Non riesco a creare la squadra: ${err.message}`);
  } finally {
    f.querySelector("button").disabled = false;
  }
});

$("form-entra").addEventListener("submit", async (e) => {
  e.preventDefault();
  const codice = e.target.codice.value.trim().toLowerCase();
  try {
    await rpc("leggi_squadra", { p_codice: codice });
    e.target.reset();
    vai(`#/s/${codice}`);
  } catch {
    mostraErrore("Codice non valido: controlla di averlo copiato tutto.");
  }
});

// --- Squadra ----------------------------------------------------------------------------------------

async function apriSquadra(codice, scheda) {
  $("home").hidden = true;
  $("squadra").hidden = false;
  $("indietro").hidden = $("ricarica").hidden = false;
  if (!squadra || squadra.codice !== codice) {
    squadra = await rpc("leggi_squadra", { p_codice: codice });
    bozza = clona(squadra);
    ricordaSquadra(squadra);
    attuale = attivo = null;
    disegnaRosa();
    disegnaRegole();
    disegnaCondividi();
    aggiornaBarra();
    caricaConsiglio();
    preparaNotifiche();
  }
  $("titolo").textContent = bozza.nome;
  $("sottotitolo").textContent = bozza.lega || "";
  mostraScheda(scheda);
}

function mostraScheda(nome) {
  if (!$(`scheda-${nome}`)) nome = "consiglio";
  for (const b of document.querySelectorAll(".schede button")) b.classList.toggle("attiva", b.dataset.scheda === nome);
  for (const s of document.querySelectorAll(".scheda")) s.hidden = s.id !== `scheda-${nome}`;
  if (nome === "rosa") caricaListone().catch(() => mostraErrore("Non riesco a scaricare il listone."));
}

for (const b of document.querySelectorAll(".schede button")) {
  b.addEventListener("click", () => {
    history.replaceState(null, "", `#/s/${squadra.codice}/${b.dataset.scheda}`);
    mostraScheda(b.dataset.scheda);
  });
}

$("salva").addEventListener("click", async () => {
  $("salva").disabled = true;
  try {
    await rpc("salva_squadra", { p_codice: squadra.codice, p_nome: bozza.nome, p_lega: bozza.lega || "",
                                 p_rosa: bozza.rosa, p_regole: bozza.regole });
    squadra = { ...squadra, ...clona(bozza) };
    ricordaSquadra(squadra);
    aggiornaBarra();
    $("titolo").textContent = squadra.nome;
    $("sottotitolo").textContent = squadra.lega || "";
    await ricalcola();
  } catch (e) {
    mostraErrore(`Salvataggio non riuscito: ${e.message}`);
  } finally {
    $("salva").disabled = false;
  }
});

$("ricarica").addEventListener("click", async () => {
  if (modificata() && !confirm("Ricaricando perdi le modifiche non salvate. Continuare?")) return;
  const codice = squadra.codice;
  squadra = null;
  await apriSquadra(codice, document.querySelector(".schede .attiva")?.dataset.scheda || "consiglio");
});

window.addEventListener("beforeunload", (e) => { if (modificata()) e.preventDefault(); });

// --- Scheda Rosa ------------------------------------------------------------------------------------

const ORDINE_RUOLI = "PDCA";
const badgeRuolo = (r) => el("span", { class: `ruolo ${r}` }, r);
const infoRiga = (titolo, sotto) =>
  el("span", { class: "info" }, el("div", { class: "nome-riga" }, titolo), el("div", { class: "sotto" }, sotto));

function disegnaRosa() {
  const rosa = bozza.rosa;
  const n = Object.fromEntries([...ORDINE_RUOLI].map((r) => [r, rosa.filter((g) => g.ruolo === r).length]));
  $("rosa-conta").textContent = `${rosa.length} giocatori · P ${n.P} · D ${n.D} · C ${n.C} · A ${n.A}`;
  $("rosa-vuota").hidden = rosa.length > 0;
  const ordinata = [...rosa].sort((a, b) =>
    ORDINE_RUOLI.indexOf(a.ruolo) - ORDINE_RUOLI.indexOf(b.ruolo) || a.nome.localeCompare(b.nome));
  $("rosa-lista").replaceChildren(...ordinata.map((g) =>
    el("li", {},
      badgeRuolo(g.ruolo),
      infoRiga(g.nome, nomeSquadra(g.squadra)),
      el("button", { class: "togli", "aria-label": `Togli ${g.nome}`, onclick: () => {
        bozza.rosa = bozza.rosa.filter((x) => x.fc_id !== g.fc_id);
        disegnaRosa(); cerca(); aggiornaBarra();
      } }, "×"))));
}

async function cerca() {
  const q = normalizza($("cerca").value.trim());
  if (q.length < 2) return $("risultati").replaceChildren();
  const tutti = await caricaListone();
  const presi = new Set(bozza.rosa.map((g) => g.fc_id));
  const trovati = tutti.filter((g) => !presi.has(g.id) && (normalizza(g.nome).includes(q) || g.squadra.startsWith(q)))
    .slice(0, 15);
  $("risultati").replaceChildren(...(trovati.length ? trovati.map((g) =>
    el("li", {},
      el("button", { onclick: () => {
        bozza.rosa.push({ fc_id: g.id, nome: g.nome, ruolo: g.ruolo, squadra: g.squadra });
        $("cerca").value = "";
        $("cerca").focus();
        disegnaRosa(); cerca(); aggiornaBarra();
      } },
        badgeRuolo(g.ruolo),
        infoRiga(g.nome, `${nomeSquadra(g.squadra)} · quotazione ${g.q}`),
        el("span", { class: "aggiungi" }, "+")))) : [el("li", { class: "muted small" }, "Nessun giocatore trovato")]));
}
$("cerca").addEventListener("input", cerca);

// --- Asta (scheda della home) ---------------------------------------------------------------------
// Due tipi: "da zero" (si costruisce una rosa nuova, con il regolamento scelto; alla fine si può salvare
// come squadra) oppure "riparazione" di una delle mie squadre (rosa e regolamento dal server; ciò che
// compro va subito nella sua rosa). Lo stato dell'asta sta solo su questo telefono.

let valori = null;
let statoAsta = null;   // vedi leggiStatoAsta()
let ctxAsta = null;     // calcoli correnti
let filtroAsta = "";
const caricaValori = async () => (valori ??= await pubblico("output/valori.json"));
const regoleModello = {};
const modelloAsta = async (id) => (regoleModello[id] ??= await caricaModello(id));
const segno = (x, d = 2) => `${x >= 0 ? "+" : "−"}${num(Math.abs(x), d)}`;
const somma = (lista) => lista.reduce((a, x) => a + (x.prezzo || 0), 0);

function leggiStatoAsta() {
  const s = leggiLocale("asta", null) || {};
  return {
    tipo: s.tipo || "zero",
    zero: { modello: "standard", squadre: 8, budget: 500, miei: [], presi: [], ...(s.zero || {}) },
    rip: s.rip || {},
  };
}
const salvaStatoAsta = () => scriviLocale("asta", statoAsta);
const ripDi = (codice) => (statoAsta.rip[codice] ??= { crediti: 0, acquisti: null, presi: [] });

$("asta-regole").replaceChildren(...MODELLI.map((m) => el("option", { value: m.id }, m.nome)));
$("asta-filtri").replaceChildren(...[["", "Tutti"], ...[...ORDINE_RUOLI].map((r) => [r, r])].map(([r, testo]) =>
  el("button", { class: r === "" ? "attiva" : "", onclick: (e) => {
    filtroAsta = r;
    for (const b of $("asta-filtri").children) b.classList.toggle("attiva", b === e.currentTarget);
    disegnaAsta();
  } }, testo)));

// Numeri di un giocatore nel contesto corrente (dipendono dal tipo di asta).
function numeriAsta(g) {
  const { s, modo } = ctxAsta;
  const guad = Asta.guadagno(s, g);
  if (modo === "zero") {
    const m = ctxAsta.mercato;
    return { guad, max: Asta.offertaDaZero(s, m, ctxAsta.crediti, g), probabile: m.probabile(g),
             valore: m.valore(g), giudizio: Asta.giudizio(m, g) };
  }
  return { guad, max: ctxAsta.crediti ? Asta.offertaMassima(s, ctxAsta.piano, ctxAsta.crediti, guad.punti) : null,
           mercato: g.fvm == null ? null : Math.round(g.fvm * (ctxAsta.regole?.crediti_asta || 500) / 1000) };
}

function rigaAsta(g) {
  const n = numeriAsta(g);
  const avviso = g.stato ? ` · ⚠ ${g.stato}` : "";
  const dettagli = ctxAsta.modo === "zero"
    ? (ctxAsta.s.liberi[g.ruolo] > 0 ? `max ${n.max} · probabile ${n.probabile} · ${n.giudizio}` : `ruolo completo · probabile ${n.probabile}`)
    : `${n.max ? `max ${n.max} · ` : ""}mercato ${n.mercato ?? "–"}`;
  return el("li", {},
    el("button", { onclick: () => apriGiocatoreAsta(g) },
      badgeRuolo(g.ruolo),
      infoRiga(g.nome, `${nomeSquadra(g.squadra)} · ${dettagli}${avviso}`),
      el("span", { class: "guadagno" }, segno(n.guad.punti), el("small", {}, "a giornata"))));
}

async function disegnaAsta() {
  statoAsta ??= leggiStatoAsta();
  const mie = mieSquadre();
  if (statoAsta.tipo !== "zero" && !mie.some((x) => x.codice === statoAsta.tipo)) statoAsta.tipo = "zero";
  $("asta-tipo").replaceChildren(el("option", { value: "zero" }, "Asta da zero (rosa nuova)"),
    ...mie.map((x) => el("option", { value: x.codice }, `Riparazione: ${x.nome}`)));
  $("asta-tipo").value = statoAsta.tipo;

  let v;
  try { v = await caricaValori(); } catch (e) { return mostraErrore(`Non riesco a scaricare i valori: ${e.message}`); }
  const zero = statoAsta.tipo === "zero";
  $("asta-zero-impostazioni").hidden = !zero;
  $("asta-rip-impostazioni").hidden = zero;
  $("asta-mia-box").hidden = !zero;
  $("asta-svincoli-box").hidden = zero;

  if (zero) {
    const z = statoAsta.zero;
    const regole = await modelloAsta(z.modello);
    const s = Asta.prepara(v, z.miei.map((x) => ({ fc_id: x.id })), regole, z.presi.map((x) => x.id));
    const mercato = Asta.mercatoLega(s, z.squadre, z.budget, somma(z.miei) + somma(z.presi));
    ctxAsta = { modo: "zero", s, mercato, regole, crediti: z.budget - somma(z.miei) };
    $("asta-regole").value = z.modello;
    $("asta-squadre").value = z.squadre;
    $("asta-budget").value = z.budget;
    const liberi = [...ORDINE_RUOLI].map((r) => `${r} ${s.liberi[r]}`).join(" · ");
    $("asta-riepilogo").textContent = `Ti restano ${ctxAsta.crediti} crediti per ${Asta.postiLiberi(s)} posti (${liberi}). ` +
      `In tutta la lega restano ${mercato.soldi} crediti per ${mercato.posti} posti.`;
    $("asta-obiettivi-titolo").textContent = z.miei.length ? "I più utili per te" : "I migliori da prendere";
    const miei = z.miei.map((x) => ({ ...x, g: s.perId.get(x.id) })).filter((x) => x.g);
    $("asta-mia-n").textContent = `(${miei.length} · spesi ${somma(z.miei)})`;
    $("asta-mia").replaceChildren(...[...miei].sort((a, b) => ORDINE_RUOLI.indexOf(a.g.ruolo) - ORDINE_RUOLI.indexOf(b.g.ruolo))
      .map((x) => el("li", {}, badgeRuolo(x.g.ruolo), infoRiga(x.g.nome, `${nomeSquadra(x.g.squadra)} · pagato ${x.prezzo}`),
        el("button", { class: "togli", "aria-label": `Annulla ${x.g.nome}`, onclick: () => {
          z.miei = z.miei.filter((y) => y.id !== x.id); salvaStatoAsta(); disegnaAsta();
        } }, "↺"))));
    $("asta-salva-squadra").hidden = miei.length === 0;
  } else {
    const codice = statoAsta.tipo;
    if (ctxAsta?.squadraRip?.codice !== codice) {
      try { ctxAsta = { squadraRip: await rpc("leggi_squadra", { p_codice: codice }) }; } catch (e) { return mostraErrore(e.message); }
    }
    const sq = ctxAsta.squadraRip, r = ripDi(codice);
    const s = Asta.prepara(v, sq.rosa, sq.regole, r.presi);
    const acquisti = r.acquisti || Math.max(Asta.postiLiberi(s), 3);
    ctxAsta = { modo: "rip", squadraRip: sq, s, regole: sq.regole, crediti: r.crediti, piano: Asta.piano(s, acquisti) };
    $("asta-crediti").value = r.crediti;
    $("asta-acquisti").value = acquisti;
    const liberi = [...ORDINE_RUOLI].map((x) => `${x} ${s.liberi[x]}`).join(" · ");
    $("asta-riepilogo").textContent = `${sq.nome} fa circa ${num(s.base)} punti a giornata. Posti liberi: ${liberi}. ` +
      `Restano ${s.rimanenti} giornate.` + (r.crediti ? "" : " Inserisci i crediti per vedere le offerte massime.");
    $("asta-obiettivi-titolo").textContent = "I più utili per te";
    $("asta-svincoli").replaceChildren(...Asta.menoUtili(s).map(({ g, perdita }) => el("li", {},
      badgeRuolo(g.ruolo), infoRiga(g.nome, `${nomeSquadra(g.squadra)}${g.stato ? ` · ⚠ ${g.stato}` : ""}`),
      el("span", { class: "guadagno" }, segno(-perdita), el("small", {}, "a giornata")))));
  }

  const s = ctxAsta.s;
  const candidati = s.disponibili.filter((g) => !filtroAsta || g.ruolo === filtroAsta)
    .filter((g) => !zero || s.liberi[g.ruolo] > 0)
    .map((g) => ({ g, punti: Asta.guadagno(s, g).punti })).sort((a, b) => b.punti - a.punti).slice(0, 20);
  $("asta-obiettivi").replaceChildren(...candidati.map(({ g }) => rigaAsta(g)));

  const presiIds = zero ? statoAsta.zero.presi.map((x) => x.id) : ripDi(statoAsta.tipo).presi;
  const presi = presiIds.map((id) => s.perId.get(id)).filter(Boolean).reverse();
  $("asta-presi-box").hidden = presi.length === 0;
  $("asta-presi-n").textContent = `(${presi.length})`;
  $("asta-presi").replaceChildren(...presi.map((g) => el("li", {},
    badgeRuolo(g.ruolo), infoRiga(g.nome, nomeSquadra(g.squadra)),
    el("button", { class: "togli", "aria-label": `Annulla ${g.nome}`, onclick: () => {
      if (zero) statoAsta.zero.presi = statoAsta.zero.presi.filter((x) => x.id !== g.id);
      else ripDi(statoAsta.tipo).presi = ripDi(statoAsta.tipo).presi.filter((x) => x !== g.id);
      salvaStatoAsta(); disegnaAsta();
    } }, "↺"))));

  $("asta-nota").textContent = (zero
    ? "\"Probabile\" è quanto si paga di solito (valore di mercato di Fantacalcio.it, adattato ai crediti che restano in lega). " +
      "\"Max\" è la tua offerta massima: media tra quanto rende secondo le statistiche e il prezzo probabile, " +
      "ridotta se per te sarebbe una riserva. "
    : "\"Per te\" è quanto salgono i punti a giornata della tua formazione migliore se lo prendi (se il ruolo è pieno, " +
      "al posto del peggiore). ") + `Stime sui dati fino alla giornata ${v.giornata - 1}. È una guida: all'asta decidi tu.`;
  cercaAsta();
}

function cercaAsta() {
  const q = normalizza($("asta-cerca").value.trim());
  if (q.length < 2 || !ctxAsta?.s) return $("asta-risultati").replaceChildren();
  const s = ctxAsta.s;
  const disponibili = new Set(s.disponibili.map((g) => g.id)), miei = new Set(s.miei.map((g) => g.id));
  // Anche per nome completo ("lautaro"), dove Sky lo conosce: all'asta si chiamano così.
  const trovati = s.tutti.filter((g) => normalizza(`${g.nome} ${g.alias || ""}`).includes(q)).slice(0, 8);
  $("asta-risultati").replaceChildren(...(trovati.length ? trovati.map((g) => disponibili.has(g.id)
    ? rigaAsta(g)
    : el("li", { class: "muted small" }, `${g.nome}: ${miei.has(g.id) ? "è già tuo" : "già preso da altri"}`))
    : [el("li", { class: "muted small" }, "Nessun giocatore trovato")]));
}
$("asta-cerca").addEventListener("input", cercaAsta);

$("asta-tipo").addEventListener("change", (e) => { statoAsta.tipo = e.target.value; salvaStatoAsta(); disegnaAsta(); });
$("asta-regole").addEventListener("change", (e) => { statoAsta.zero.modello = e.target.value; salvaStatoAsta(); disegnaAsta(); });
$("asta-squadre").addEventListener("change", (e) => {
  statoAsta.zero.squadre = Math.min(20, Math.max(2, Number(e.target.value) || 8)); salvaStatoAsta(); disegnaAsta();
});
$("asta-budget").addEventListener("change", (e) => {
  statoAsta.zero.budget = Math.max(25, Number(e.target.value) || 500); salvaStatoAsta(); disegnaAsta();
});
$("asta-crediti").addEventListener("change", (e) => {
  ripDi(statoAsta.tipo).crediti = Math.max(0, Number(e.target.value) || 0); salvaStatoAsta(); disegnaAsta();
});
$("asta-acquisti").addEventListener("change", (e) => {
  ripDi(statoAsta.tipo).acquisti = Math.min(25, Math.max(1, Number(e.target.value) || 1)); salvaStatoAsta(); disegnaAsta();
});

$("asta-ricomincia").addEventListener("click", () => {
  if (!confirm("Ricominciare l'asta da capo? Si cancellano la tua rosa e i presi da altri di questa asta.")) return;
  statoAsta.zero.miei = []; statoAsta.zero.presi = []; salvaStatoAsta(); disegnaAsta();
});

$("asta-salva-squadra").addEventListener("click", async () => {
  const nome = prompt("Nome della nuova squadra:");
  if (!nome?.trim()) return;
  const lega = prompt("Nome della lega (facoltativo):") || "";
  try {
    const z = statoAsta.zero, s = ctxAsta.s;
    const rosa = z.miei.map((x) => s.perId.get(x.id)).filter(Boolean)
      .map((g) => ({ fc_id: g.id, nome: g.nome, ruolo: g.ruolo, squadra: g.squadra }));
    const codice = await rpc("crea_squadra", { p_nome: nome, p_lega: lega, p_regole: ctxAsta.regole });
    await rpc("salva_squadra", { p_codice: codice, p_nome: nome, p_lega: lega, p_rosa: rosa, p_regole: ctxAsta.regole });
    ricordaSquadra({ codice, nome, lega });
    rpc("richiedi_ricalcolo", { p_codice: codice }).catch(() => {});
    vai(`#/s/${codice}`);
  } catch (e) {
    mostraErrore(`Non riesco a salvare la squadra: ${e.message}`);
  }
});

let giocatoreAsta = null;
function apriGiocatoreAsta(g) {
  giocatoreAsta = g;
  const n = numeriAsta(g), s = ctxAsta.s;
  $("a-nome").textContent = g.nome;
  $("a-sotto").textContent = `${nomeSquadra(g.squadra)} · prende voto nel ${pct(g.p)} delle giornate · fantavoto medio ${num(g.fv)}`;
  const note = [];
  if (ctxAsta.modo === "zero") {
    [["Offerta massima", s.liberi[g.ruolo] > 0 ? n.max : "–"], ["Prezzo probabile", n.probabile], ["Valore statistiche", n.valore]]
      .forEach(([l, v], i) => { $(`a-l${i + 1}`).textContent = l; $(`a-v${i + 1}`).textContent = v; });
    note.push(s.liberi[g.ruolo] > 0 ? `Per te: ${segno(n.guad.punti)} punti a giornata. Giudizio: ${n.giudizio}.`
                                    : "Hai già completato questo ruolo.");
  } else {
    [["Per te, a giornata", segno(n.guad.punti)], ["Offerta massima", n.max ?? "–"], ["Prezzo di mercato", n.mercato ?? "–"]]
      .forEach(([l, v], i) => { $(`a-l${i + 1}`).textContent = l; $(`a-v${i + 1}`).textContent = v; });
    if (n.guad.fuori) note.push(`Ruolo pieno: prenderebbe il posto di ${n.guad.fuori.nome}.`);
    note.push(`Da qui a fine stagione: circa ${segno(n.guad.punti * s.rimanenti, 0)} punti.`);
    if (!ctxAsta.crediti) note.push("Inserisci i crediti disponibili per l'offerta massima.");
  }
  if (g.stato) note.push(`${g.stato[0].toUpperCase() + g.stato.slice(1)}${g.nota ? `: ${g.nota}` : ""}.`);
  note.push("Il prezzo serve per \"Preso da me\"; per \"Preso da altri\" è facoltativo ma aiuta a stimare i prezzi.");
  $("a-nota").hidden = false;
  $("a-nota").textContent = note.join(" ");
  $("a-prezzo").value = "";
  $("asta-dialog").showModal();
}

function chiudiGiocatoreAsta() {
  $("asta-dialog").close();
  $("asta-cerca").value = "";
  disegnaAsta();
}

$("a-altri").addEventListener("click", () => {
  const g = giocatoreAsta, prezzo = Number($("a-prezzo").value) || null;
  if (ctxAsta.modo === "zero") {
    const z = statoAsta.zero;
    // Senza prezzo si usa quello probabile, per tenere il conto dei crediti rimasti in lega.
    z.presi = [...z.presi.filter((x) => x.id !== g.id), { id: g.id, prezzo: prezzo || ctxAsta.mercato.probabile(g) }];
  } else {
    const r = ripDi(statoAsta.tipo);
    r.presi = [...r.presi.filter((x) => x !== g.id), g.id];
  }
  salvaStatoAsta();
  chiudiGiocatoreAsta();
});

$("a-mio").addEventListener("click", async () => {
  const g = giocatoreAsta, prezzo = Number($("a-prezzo").value);
  if (!prezzo || prezzo < 1) return $("a-prezzo").focus();
  if (ctxAsta.modo === "zero") {
    if (ctxAsta.s.liberi[g.ruolo] <= 0) return mostraErrore(`Hai già completato il ruolo ${g.ruolo}.`);
    statoAsta.zero.miei.push({ id: g.id, prezzo });
    salvaStatoAsta();
    return chiudiGiocatoreAsta();
  }
  // Riparazione: va subito nella rosa della squadra (se il ruolo è pieno, svincola il meno utile).
  const sq = ctxAsta.squadraRip, guad = Asta.guadagno(ctxAsta.s, g);
  if (guad.fuori && !confirm(`Ruolo pieno: svincoli ${guad.fuori.nome} per fare posto a ${g.nome}?`)) return;
  const rosa = sq.rosa.filter((x) => !guad.fuori || x.fc_id !== guad.fuori.id)
    .concat({ fc_id: g.id, nome: g.nome, ruolo: g.ruolo, squadra: g.squadra });
  try {
    await rpc("salva_squadra", { p_codice: sq.codice, p_nome: sq.nome, p_lega: sq.lega || "", p_rosa: rosa, p_regole: sq.regole });
    sq.rosa = rosa;
    const r = ripDi(sq.codice);
    r.crediti = Math.max(0, r.crediti - prezzo);
    r.acquisti = Math.max(1, (r.acquisti || Number($("asta-acquisti").value) || 3) - 1);
    salvaStatoAsta();
    chiudiGiocatoreAsta();
  } catch (e) {
    mostraErrore(`Non riesco a salvare l'acquisto: ${e.message}`);
  }
});

// --- Scheda Regolamento -----------------------------------------------------------------------------

const VOCI_BONUS = [
  ["gol", "Gol"], ["assist", "Assist"], ["rigore_sbagliato", "Rigore sbagliato"], ["rigore_parato", "Rigore parato"],
  ["gol_subito", "Gol subito"], ["porta_imbattuta", "Porta imbattuta"], ["autogol", "Autogol"],
  ["ammonizione", "Ammonizione"], ["espulsione", "Espulsione"], ["mvp_panini", "Migliore in campo"],
];
const MODULI = ["3-4-3", "3-5-2", "4-5-1", "4-4-2", "4-3-3", "5-3-2", "5-4-1"];

const numero = (input) => (input.value === "" ? 0 : Number(input.value));
const campoNumero = (valore, alCambio, attrs = {}) => {
  const i = el("input", { type: "number", step: "0.5", inputmode: "decimal", ...attrs });
  i.value = valore ?? 0;
  i.addEventListener("input", () => { alCambio(numero(i)); aggiornaBarra(); });
  return i;
};

function disegnaRegole() {
  const r = bozza.regole;
  r.bonus_malus ??= {};

  $("regole-bonus").replaceChildren(...VOCI_BONUS.map(([chiave, etichetta]) =>
    el("tr", {}, el("th", {}, etichetta), ...[...ORDINE_RUOLI].map((ruolo) =>
      el("td", {}, campoNumero(r.bonus_malus[chiave]?.[ruolo], (v) => {
        r.bonus_malus[chiave] ??= {};
        r.bonus_malus[chiave][ruolo] = v;
        // Il motore conta i rigori segnati come gol: tiene allineata anche la voce "gol su rigore".
        if (chiave === "gol") (r.bonus_malus.gol_rigore ??= {})[ruolo] = v;
      }, { "aria-label": `${etichetta} ${ruolo}` }))))));

  r.moduli ??= [...MODULI];
  $("regole-moduli").replaceChildren(...MODULI.map((m) => {
    const c = el("input", { type: "checkbox" });
    c.checked = r.moduli.includes(m);
    c.addEventListener("change", () => {
      r.moduli = MODULI.filter((x) => (x === m ? c.checked : r.moduli.includes(x)));
      aggiornaBarra();
    });
    return el("label", { class: "spunta" }, c, ` ${m}`);
  }));

  const md = (r.modificatore_difesa ??= { attivo: false, minimo_difensori_schierati: 4, fasce: [] });
  $("md-attivo").checked = !!md.attivo;
  $("md-attivo").onchange = () => { md.attivo = $("md-attivo").checked; aggiornaBarra(); };
  $("md-minimo").value = md.minimo_difensori_schierati ?? 4;
  $("md-minimo").oninput = () => { md.minimo_difensori_schierati = numero($("md-minimo")); aggiornaBarra(); };
  md.fasce = [...(md.fasce || [])].sort((a, b) => b.media_min - a.media_min);
  while (md.fasce.length < 3) md.fasce.push({ media_min: 0, bonus: 0 });
  $("md-fasce").replaceChildren(...md.fasce.map((f) =>
    el("div", { class: "fascia" },
      el("span", {}, "media ≥"), campoNumero(f.media_min, (v) => { f.media_min = v; }, { step: "0.25" }),
      el("span", {}, "bonus +"), campoNumero(f.bonus, (v) => { f.bonus = v; }))));

  const sost = (r.sostituzioni ??= {});
  $("r-cambi").value = sost.max ?? 5;
  $("r-cambi").oninput = () => { sost.max = numero($("r-cambi")); aggiornaBarra(); };

  const sd = (r.scontri_diretti ??= {});
  const soglie = sd.soglie_gol?.length ? sd.soglie_gol : [66, 70];
  $("r-soglia").value = soglie[0];
  $("r-passo").value = soglie.length > 1 ? soglie[1] - soglie[0] : 4;
  const aggiornaSoglie = () => {
    const prima = numero($("r-soglia")), passo = Math.max(1, numero($("r-passo")));
    sd.soglie_gol = Array.from({ length: 8 }, (_, i) => prima + i * passo);
    aggiornaBarra();
  };
  $("r-soglia").oninput = $("r-passo").oninput = aggiornaSoglie;
}

$("regole-applica").addEventListener("click", async () => {
  if (!confirm("Sostituire tutto il regolamento con il modello scelto?")) return;
  try {
    bozza.regole = await caricaModello($("regole-modello").value);
    disegnaRegole();
    aggiornaBarra();
  } catch (e) {
    mostraErrore(`Non riesco a caricare il modello: ${e.message}`);
  }
});

// --- Scheda Condividi -------------------------------------------------------------------------------

const linkSquadra = () => `${location.origin}${location.pathname}?squadra=${squadra.codice}`;

function disegnaCondividi() {
  $("s-nome").value = bozza.nome;
  $("s-lega").value = bozza.lega || "";
  $("codice").textContent = squadra.codice;
}
$("s-nome").addEventListener("input", (e) => { bozza.nome = e.target.value; aggiornaBarra(); });
$("s-lega").addEventListener("input", (e) => { bozza.lega = e.target.value; aggiornaBarra(); });

$("copia-link").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(linkSquadra());
    $("copia-link").textContent = "Link copiato ✓";
  } catch {
    prompt("Copia questo link:", linkSquadra());
  }
});

$("esci").addEventListener("click", () => {
  if (!confirm(`Togliere "${squadra.nome}" da questo telefono?`)) return;
  dimenticaSquadra(squadra.codice);
  squadra = bozza = null;
  vai("#/");
});

// --- Scheda Consiglio -------------------------------------------------------------------------------

function partita(g) {
  if (!g.avversario) return "non gioca";
  return g.casa ? `vs ${sigla(g.avversario)}` : `@ ${sigla(g.avversario)}`;
}
const classeVoto = (p) => (p >= 0.85 ? "ok" : p >= 0.6 ? "warn" : "bad");

function apriDettaglio(g) {
  $("d-nome").textContent = g.nome;
  $("d-partita").textContent = g.avversario
    ? `${nomeSquadra(g.squadra)} ${g.casa ? "in casa contro" : "in trasferta contro"} ${nomeSquadra(g.avversario)}`
    : `${nomeSquadra(g.squadra)} non gioca questa giornata`;
  $("d-voto").textContent = pct(g.p_voto);
  $("d-fv").textContent = num(g.fantavoto_se_gioca);
  $("d-attesi").textContent = num(g.punti_attesi, 2);
  const righe = [];
  const f = g.fonti;
  if (f?.ufficiale) {
    righe.push(f.sky === "titolare" || f.sky === "dubbio" ? "Titolare nella formazione ufficiale." : "Non titolare nella formazione ufficiale.");
  } else if (f) {
    const fc = typeof f.fantacalcio === "number" ? pct(f.fantacalcio) : f.fantacalcio || "non lo cita";
    const sky = { titolare: "titolare", dubbio: "in dubbio", riserva: "in panchina", squalificato: "squalificato",
                  indisponibile: "indisponibile" }[f.sky] || "non lo cita";
    righe.push(`Probabili: Fantacalcio.it ${fc} · Sky ${sky}.`);
  }
  if (g.rigorista) righe.push(`Rigorista n°${g.rigorista} della squadra.`);
  if (g.nota && !(f?.ufficiale && g.stato === "ok")) {
    const nota = `${g.nota[0].toUpperCase()}${g.nota.slice(1)}`;
    righe.push(g.stato === "ok" ? `${nota}.` : `${g.stato[0].toUpperCase() + g.stato.slice(1)}: ${g.nota}`);
  }
  $("d-nota").hidden = righe.length === 0;
  $("d-nota").textContent = righe.join(" ");
  $("dettaglio").showModal();
}

const chip = (g) => el("button", { class: "giocatore", onclick: () => apriDettaglio(g) },
  el("span", { class: "nome" }, g.nome),
  el("span", { class: "avv" }, partita(g)),
  el("span", { class: `badge ${classeVoto(g.p_voto)}` }, pct(g.p_voto)));

const riga = (g) => el("li", {},
  el("button", { onclick: () => apriDettaglio(g) },
    badgeRuolo(g.ruolo),
    infoRiga(g.nome, `${nomeSquadra(g.squadra)} ${partita(g)} · voto ${pct(g.p_voto)} · se gioca ${num(g.fantavoto_se_gioca)}`),
    el("span", { class: `badge ${classeVoto(g.p_voto)}` }, num(g.punti_attesi))));

function mostraScadenza(c, storico) {
  const box = $("scadenza-box");
  box.hidden = !c?.scadenza || storico;
  if (box.hidden) return;
  const ore = (new Date(c.scadenza) - Date.now()) / 36e5;
  $("scadenza").textContent = ore > 0
    ? `Consegna entro ${dataOra(c.scadenza)}${ore < 24 ? ` (tra ${ore < 1 ? Math.round(ore * 60) + " min" : Math.round(ore) + " ore"})` : ""}`
    : "Scadenza passata";
  $("scadenza").classList.toggle("vicina", ore > 0 && ore < 3);
}

function mostraStato(titolo, testo) {
  $("stato-box").hidden = false;
  $("stato-titolo").textContent = titolo;
  $("stato-testo").textContent = testo;
}

function mostra(c, storico = false) {
  attivo = { c, storico };
  mostraScadenza(c, storico);
  $("stato-box").hidden = true;
  $("formazione").hidden = true;
  $("aggiornato").textContent = "";
  if (!c) {
    return mostraStato("Nessun consiglio ancora",
      "Completa la rosa e salva: il primo consiglio arriva in 1–2 minuti. Oppure tocca Ricalcola adesso.");
  }
  if (c.stato === "in_attesa") {
    return mostraStato(`Giornata ${c.giornata}: in attesa delle probabili`,
      "Fantacalcio.it non ha ancora pubblicato le probabili formazioni di questa giornata. " +
      "Il consiglio arriva appena escono (di solito tra martedì e mercoledì).");
  }
  if (c.stato === "rosa_incompleta") {
    return mostraStato("Rosa da completare", `${c.messaggio}. Aggiungi i giocatori nella scheda Rosa e salva.`);
  }
  $("formazione").hidden = false;
  $("storico-nota").hidden = !storico;
  $("storico-nota").textContent = storico
    ? c.nota_storico || `Consiglio dato prima della scadenza della giornata ${c.giornata}, con le probabili di quel momento.` : "";
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
  $("modulo").textContent = f.modulo;
  $("modulo-nota").textContent = f.modulo === c.modulo ? "consigliato" : `consigliato: ${c.modulo}`;
  $("punti").textContent = num(f.punti_attesi);
  $("intervallo").textContent = f.intervallo_80
    ? `8 volte su 10 tra ${num(f.intervallo_80[0])} e ${num(f.intervallo_80[1])}` : "";

  // Probabilità di 0, 1, …, 5+ gol.
  const prob = Object.values(f.prob_gol);
  prob[prob.length - 1] += Math.max(0, 1 - prob.reduce((a, b) => a + b, 0));
  const max = Math.max(...prob);
  $("gol").replaceChildren(...prob.map((p, i) =>
    el("div", { class: "colonna" },
      el("span", { class: "pct" }, pct(p)),
      el("div", { class: "barra", style: `height:${(p / max) * 70}%` }),
      el("span", { class: "n" }, i === prob.length - 1 ? `${i}+` : `${i}`))));
  $("extra").textContent = `Modificatore difesa atteso +${num(f.modificatore_atteso)} · cambi attesi ${num(f.cambi_attesi)}`;

  for (const linea of document.querySelectorAll(".linea")) {
    linea.replaceChildren(...f.titolari.filter((g) => g.ruolo === linea.dataset.ruolo).map(chip));
  }

  $("panchina").replaceChildren(...f.panchina.filter((g) => g.p_voto > 0).map(riga));
  const fuori = f.panchina.filter((g) => g.p_voto === 0);
  $("box-avvisi").hidden = fuori.length === 0;
  $("avvisi").replaceChildren(...fuori.map((g) => el("li", {}, badgeRuolo(g.ruolo), infoRiga(g.nome, g.nota || g.stato))));

  $("alternative").replaceChildren(...c.alternative.map((a) =>
    el("li", { class: a.modulo === f.modulo ? "scelto" : "" },
      el("button", { onclick: () => (a.modulo === c.modulo ? mostra(attivo.c, attivo.storico) : mostraModulo(c, a.modulo)) },
        el("span", {}, a.modulo), el("span", {}, num(a.punti_attesi))))));
  $("moduli-aiuto").hidden = !c.alternative.some((a) => a.titolari);
}

function riempiGiornate(giornate) {
  const passate = giornate.filter((g) => !attuale || g !== attuale.giornata);
  $("giornata").replaceChildren(
    el("option", { value: "attuale" }, `${attuale?.giornata ?? "–"} · prossima`),
    ...passate.map((g) => el("option", { value: String(g) }, `${g} · giocata`)));
  $("box-giornata").hidden = passate.length === 0;
}

async function caricaConsiglio() {
  const codice = squadra.codice;
  try {
    const r = await rpc("leggi_consiglio", { p_codice: codice, p_giornata: null });
    if (squadra?.codice !== codice) return;
    attuale = r.consiglio;
    scriviLocale(`consiglio:${codice}`, attuale);
    riempiGiornate(r.giornate);
    mostra(attuale);
  } catch (e) {
    const salvato = leggiLocale(`consiglio:${codice}`, null);
    if (salvato) {
      attuale = salvato;
      mostra(salvato);
      $("aggiornato").textContent += " · offline";
    } else {
      mostraErrore(`Non riesco a scaricare il consiglio: ${e.message}`);
    }
  }
}

$("giornata").addEventListener("change", async (e) => {
  const v = e.target.value;
  if (v === "attuale") return mostra(attuale);
  try {
    const r = await rpc("leggi_consiglio", { p_codice: squadra.codice, p_giornata: Number(v) });
    mostra(r.consiglio, true);
  } catch (err) {
    mostraErrore(`Non riesco a caricare la giornata ${v}: ${err.message}`);
  }
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && squadra && ($("giornata").value || "attuale") === "attuale") caricaConsiglio();
});

// --- Ricalcolo ------------------------------------------------------------------------------------

async function ricalcola() {
  if (modificata()) {
    $("ricalcolo-stato").textContent = "Prima salva le modifiche.";
    return;
  }
  $("ricalcola").disabled = true;
  setTimeout(() => { $("ricalcola").disabled = false; }, 30000);
  try {
    const esito = await rpc("richiedi_ricalcolo", { p_codice: squadra.codice });
    $("ricalcolo-stato").textContent = {
      avviato: "Ricalcolo avviato: il consiglio si aggiorna tra 1–2 minuti.",
      gia_richiesto: "Ricalcolo già in corso…",
      in_coda: "Ricalcolo in coda: il consiglio si aggiorna entro 15 minuti.",
    }[esito] || esito;
    attendiRicalcolo(squadra.codice);
  } catch (e) {
    $("ricalcolo-stato").textContent = `Non riuscito: ${e.message}`;
  }
}
$("ricalcola").addEventListener("click", ricalcola);

async function attendiRicalcolo(codice, tentativi = 30) {
  for (let i = 0; i < tentativi; i++) {
    await new Promise((r) => setTimeout(r, 20000));
    if (squadra?.codice !== codice) return;
    try {
      const s = await rpc("leggi_squadra", { p_codice: codice });
      if (!s.ricalcolo_richiesto) {
        await caricaConsiglio();
        $("ricalcolo-stato").textContent = "Consiglio aggiornato ✓";
        return;
      }
    } catch {}
  }
}

// --- Notifiche push -------------------------------------------------------------------------------
// Su iPhone funzionano solo con l'app aggiunta alla schermata Home (iOS 16.4+).
// L'iscrizione del telefono si salva sul server per la squadra aperta: un telefono può seguirne più d'una.

const installata = () => navigator.standalone === true || matchMedia("(display-mode: standalone)").matches;

function chiaveVapid() {
  const k = C.VAPID_PUBBLICA;
  const b64 = (k + "=".repeat((4 - (k.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

async function preparaNotifiche() {
  const testo = $("notifiche-testo");
  $("notifiche-azioni").hidden = $("notifiche-disattiva").hidden = true;
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !installata()) {
    testo.textContent = "Per ricevere gli avvisi (consiglio pronto, formazione cambiata, promemoria prima della consegna) " +
      "apri questa pagina con Safari, tocca Condividi → Aggiungi alla schermata Home e apri l'app da lì.";
    return;
  }
  const reg = await navigator.serviceWorker.ready;
  const iscrizione = await reg.pushManager.getSubscription();
  if (iscrizione && leggiLocale(`notifiche:${squadra.codice}`, false)) {
    testo.textContent = "Notifiche attive per questa squadra su questo telefono.";
    $("notifiche-disattiva").hidden = false;
  } else {
    testo.textContent = "Ricevi un avviso quando esce il consiglio, quando cambia la formazione e prima della consegna.";
    $("notifiche-nome").value = leggiLocale("nome", "");
    $("notifiche-azioni").hidden = false;
  }
}

$("notifiche-attiva").addEventListener("click", async () => {
  const nome = $("notifiche-nome").value.trim();
  if (!nome) return $("notifiche-nome").focus();
  scriviLocale("nome", nome);
  try {
    if ((await Notification.requestPermission()) !== "granted") {
      $("notifiche-testo").textContent = "Permesso negato. Puoi riattivarlo da Impostazioni → Notifiche → Consigliere.";
      return;
    }
    const reg = await navigator.serviceWorker.ready;
    const iscrizione = (await reg.pushManager.getSubscription())
      || (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: chiaveVapid() }));
    await rpc("salva_iscrizione", { p_codice: squadra.codice, p_nome: nome, p_iscrizione: iscrizione.toJSON() });
    scriviLocale(`notifiche:${squadra.codice}`, true);
    await preparaNotifiche();
  } catch (e) {
    mostraErrore(`Non riesco ad attivare le notifiche: ${e.message}`);
  }
});

$("notifiche-disattiva").addEventListener("click", async () => {
  try {
    const reg = await navigator.serviceWorker.ready;
    const iscrizione = await reg.pushManager.getSubscription();
    if (iscrizione) await rpc("rimuovi_iscrizione", { p_codice: squadra.codice, p_endpoint: iscrizione.endpoint });
    scriviLocale(`notifiche:${squadra.codice}`, null);
    await preparaNotifiche();
  } catch (e) {
    mostraErrore(`Non riesco a disattivare le notifiche: ${e.message}`);
  }
});

// --- Avvio ----------------------------------------------------------------------------------------

// Link condiviso o notifica: ?squadra=<codice> apre direttamente quella squadra.
const daLink = new URLSearchParams(location.search).get("squadra");
if (daLink) history.replaceState(null, "", `${location.pathname}#/s/${daLink.toLowerCase()}`);
instrada();

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
