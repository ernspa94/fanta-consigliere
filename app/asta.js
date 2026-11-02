// Calcoli per l'asta, fatti sul telefono così si aggiornano subito mentre si segnano i giocatori presi.
// I valori dei giocatori (presenza, media voto, frequenza di bonus/malus) li pubblica il motore in
// output/valori.json (engine/fanta/mercato.py); qui si applicano il regolamento, la rosa e i crediti.

const Asta = (() => {
  const RUOLI = ["P", "D", "C", "A"];
  const ROSA_STANDARD = { P: 3, D: 8, C: 8, A: 6 };

  // Fantavoto medio quando gioca, con i bonus/malus della lega (stessa formula di mercato.fantavoto).
  function fantavoto(c, bm) {
    const v = (chiave) => bm?.[chiave]?.[c.ruolo] ?? 0;
    let fv = c.mv + v("gol") * c.gol + v("assist") * c.ass + v("ammonizione") * c.amm
      + v("espulsione") * c.esp + v("rigore_sbagliato") * c.rig_err;
    if (c.ruolo === "P") fv += v("gol_subito") * c.gs + v("porta_imbattuta") * Math.exp(-c.gs) + v("rigore_parato") * c.rp;
    return fv;
  }

  // Punti attesi a giornata di k posti di un ruolo: si schierano i migliori, e se uno non prende voto
  // entra il successivo. dist[j] = probabilità che j dei precedenti abbiano già preso voto (fino a k).
  function puntiRuolo(giocatori, k) {
    if (k === 0) return 0;
    const ordinati = [...giocatori].sort((a, b) => b.fv - a.fv);
    let dist = new Float64Array(k + 1);
    dist[0] = 1;
    let totale = 0;
    for (const g of ordinati) {
      let postoLibero = 0;
      for (let j = 0; j < k; j++) postoLibero += dist[j];
      if (postoLibero < 1e-6) break;
      totale += g.fv * g.p * postoLibero;
      const nuova = new Float64Array(k + 1);
      for (let j = 0; j < k; j++) { nuova[j] += dist[j] * (1 - g.p); nuova[j + 1] += dist[j] * g.p; }
      nuova[k] += dist[k];
      dist = nuova;
    }
    return totale;
  }

  function moduli(regole) {
    return (regole?.moduli?.length ? regole.moduli : ["3-4-3", "3-5-2", "4-5-1", "4-4-2", "4-3-3", "5-3-2", "5-4-1"])
      .map((m) => { const [D, C, A] = m.split("-").map(Number); return { P: 1, D, C, A }; });
  }

  // Punti attesi a giornata della squadra con il modulo migliore.
  function valoreSquadra(giocatori, mods) {
    const perRuolo = Object.fromEntries(RUOLI.map((r) => [r, giocatori.filter((g) => g.ruolo === r)]));
    const cache = {};
    const pr = (r, k) => (cache[r + k] ??= puntiRuolo(perRuolo[r], k));
    return Math.max(...mods.map((m) => RUOLI.reduce((s, r) => s + pr(r, m[r]), 0)));
  }

  // Prepara tutto ciò che serve: giocatori con fantavoto della lega, rosa attuale, posti liberi.
  function prepara(valori, rosa, regole, presiDaAltri) {
    const bm = regole?.bonus_malus;
    const tutti = valori.giocatori.map((c) => ({ ...c, fv: fantavoto(c, bm), p: c.presenza }));
    const perId = new Map(tutti.map((g) => [g.id, g]));
    const inRosa = new Set(rosa.map((g) => g.fc_id));
    const miei = rosa.map((g) => perId.get(g.fc_id)).filter(Boolean);
    const limiti = { ...ROSA_STANDARD, ...(regole?.rosa || {}) };
    const liberi = Object.fromEntries(RUOLI.map((r) => [r, Math.max(0, limiti[r] - miei.filter((g) => g.ruolo === r).length)]));
    const presi = new Set(presiDaAltri);
    const disponibili = tutti.filter((g) => !inRosa.has(g.id) && !presi.has(g.id));
    const mods = moduli(regole);
    return { tutti, perId, miei, liberi, disponibili, mods, rimanenti: valori.giornate_rimanenti,
             crediti_asta: regole?.crediti_asta || 500, base: valoreSquadra(miei, mods) };
  }

  // Quanto sale la squadra (punti a giornata) prendendo g. Se il ruolo è pieno, al posto del peggiore.
  function guadagno(s, g) {
    if (s.liberi[g.ruolo] > 0) return { punti: valoreSquadra([...s.miei, g], s.mods) - s.base, fuori: null };
    let meglio = { punti: -Infinity, fuori: null };
    for (const x of s.miei.filter((m) => m.ruolo === g.ruolo)) {
      const punti = valoreSquadra([...s.miei.filter((m) => m !== x), g], s.mods) - s.base;
      if (punti > meglio.punti) meglio = { punti, fuori: x };
    }
    return meglio;
  }

  // Piano: `acquisti` giocatori presi uno alla volta, ogni volta il più utile. Nei ruoli con posti
  // liberi si aggiunge, in quelli pieni si sostituisce il peggiore (asta di riparazione: compro e svincolo).
  // Serve a dire quanti crediti vale un punto: il budget si divide in proporzione al valore portato.
  function piano(s, acquisti) {
    const posti = { ...s.liberi };
    let rosa = [...s.miei], valore = s.base, guadagnoTotale = 0;
    // Per velocità si considerano i 40 migliori per ruolo come candidati.
    const candidati = RUOLI.flatMap((r) => s.disponibili.filter((g) => g.ruolo === r)
      .sort((a, b) => b.fv * b.p - a.fv * a.p).slice(0, 40));
    const scelti = [];
    for (let i = 0; i < acquisti; i++) {
      let best = null;
      for (const g of candidati) {
        if (scelti.includes(g)) continue;
        const prove = posti[g.ruolo] > 0 ? [[...rosa, g]]
          : rosa.filter((x) => x.ruolo === g.ruolo).map((x) => [...rosa.filter((y) => y !== x), g]);
        for (const r of prove) {
          const v = valoreSquadra(r, s.mods);
          if (v > (best?.v ?? valore)) best = { g, v, rosa: r };
        }
      }
      if (!best) break;
      if (posti[best.g.ruolo] > 0) posti[best.g.ruolo]--;
      scelti.push(best.g); rosa = best.rosa;
      guadagnoTotale += best.v - valore; valore = best.v;
    }
    return { scelti, guadagnoTotale, totPosti: acquisti };
  }

  const postiLiberi = (s) => RUOLI.reduce((a, r) => a + s.liberi[r], 0);

  // Offerta massima consigliata in crediti per un giocatore con guadagno `punti` (a giornata).
  function offertaMassima(s, pianoS, crediti, punti) {
    if (punti <= 0) return 1;
    const postiTotali = Math.max(pianoS.totPosti, 1);
    const spendibili = Math.max(crediti - postiTotali, 0);  // 1 credito tenuto per ogni posto
    const perPunto = pianoS.guadagnoTotale > 0 ? spendibili / pianoS.guadagnoTotale : 0;
    const massimo = Math.max(crediti - (postiTotali - 1), 1);
    return Math.max(1, Math.min(massimo, Math.round(1 + perPunto * punti)));
  }

  // Svincoli: chi fa perdere meno punti se tolto dalla rosa.
  function menoUtili(s, n = 5) {
    return s.miei.map((g) => ({ g, perdita: s.base - valoreSquadra(s.miei.filter((x) => x !== g), s.mods) }))
      .sort((a, b) => a.perdita - b.perdita).slice(0, n);
  }

  return { prepara, guadagno, piano, offertaMassima, menoUtili, fantavoto, postiLiberi };
})();
