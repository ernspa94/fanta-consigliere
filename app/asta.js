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
    return { tutti, perId, miei, liberi, limiti, disponibili, mods, rimanenti: valori.giornate_rimanenti,
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

  // --- Asta da zero: prezzo "giusto" per tutta la lega --------------------------------------------
  // Un giocatore vale quanto è migliore dell'ultimo che verrà comprato nel suo ruolo (con 8 squadre e
  // 6 attaccanti a testa, il 48° attaccante si prende a 1 credito). I crediti che restano a tutta la
  // lega si dividono in proporzione a questo "di più": se gli altri spendono tanto, i prezzi scendono.
  // Il "rimpiazzo" si misura sui posti da titolare (più un quarto di panchina), non su quelli in rosa:
  // in campo va un solo portiere, quindi il 9° portiere della lega vale già poco.
  function titolariMedi(s) {
    const media = (r) => s.mods.reduce((a, m) => a + m[r], 0) / s.mods.length;
    return Object.fromEntries(RUOLI.map((r) => [r, Math.min(s.limiti[r], media(r) * 1.25)]));
  }

  // Valuta tutti i disponibili rispetto ai crediti che restano a tutta la lega.
  // valoreDi(g) dà il valore "sopra l'ultimo comprato" (≥ 0); i crediti oltre il minimo (1 a posto)
  // si dividono in proporzione. Lo usano sia il valore statistico sia la stima del prezzo reale.
  function dividiCrediti(s, squadre, budget, spesiLega, valoreDi) {
    const assegnati = new Set(s.miei.map((g) => g.id));
    const presiLega = s.tutti.filter((g) => !s.disponibili.includes(g) && !assegnati.has(g.id));
    let somma = 0, posti = 0;
    for (const r of RUOLI) {
      const giaPresi = s.miei.filter((g) => g.ruolo === r).length + presiLega.filter((g) => g.ruolo === r).length;
      const postiRuolo = Math.max(0, squadre * s.limiti[r] - giaPresi);
      posti += postiRuolo;
      somma += s.disponibili.filter((g) => g.ruolo === r).map(valoreDi).sort((a, b) => b - a)
        .slice(0, postiRuolo).reduce((a, b) => a + b, 0);
    }
    const soldi = Math.max(0, squadre * budget - spesiLega);
    const perUnita = somma > 0 ? Math.max(0, soldi - posti) / somma : 0;
    return { prezzo: (g) => Math.max(1, Math.round(1 + valoreDi(g) * perUnita)), soldi, posti };
  }

  function mercatoLega(s, squadre, budget, spesiLega) {
    const ev = (g) => g.fv * g.p;
    const tit = titolariMedi(s), rimpiazzo = {};
    for (const r of RUOLI) {
      const valori = s.tutti.filter((g) => g.ruolo === r).map(ev).sort((a, b) => b - a);
      rimpiazzo[r] = valori[Math.min(valori.length - 1, Math.round(squadre * tit[r]))] ?? 0;
    }
    // Valore secondo le statistiche: punti a giornata in più dell'ultimo titolare comprato.
    const statistico = dividiCrediti(s, squadre, budget, spesiLega, (g) => Math.max(0, ev(g) - rimpiazzo[g.ruolo]));
    // Prezzo probabile: FVM di Fantacalcio.it (quanto si paga di solito), sugli stessi crediti rimasti.
    const reale = dividiCrediti(s, squadre, budget, spesiLega, (g) => Math.max(0, (g.fvm || 0) - 1));
    return { valore: statistico.prezzo, probabile: reale.prezzo, soldi: statistico.soldi, posti: statistico.posti };
  }

  // Offerta massima per la mia rosa in costruzione: media tra valore statistico e prezzo probabile
  // (le statistiche non sanno se un inizio di stagione da record durerà, il mercato in parte sì),
  // ridotta se per me sarebbe una riserva (conta la parte del suo valore che entra davvero nella mia
  // formazione) e mai tanto da non lasciare 1 credito per ogni posto ancora vuoto.
  function offertaDaZero(s, mercato, crediti, g) {
    if (s.liberi[g.ruolo] <= 0) return 0;
    const ev = g.fv * g.p;
    const quota = ev > 0 ? Math.min(1, Math.max(0, guadagno(s, g).punti / ev)) : 0;
    const tetto = Math.max(1, crediti - (postiLiberi(s) - 1));
    const giusto = (mercato.valore(g) + mercato.probabile(g)) / 2;
    return Math.max(1, Math.min(tetto, Math.round(giusto * quota)));
  }

  // Giudizio sul prezzo probabile rispetto al valore statistico.
  function giudizio(mercato, g) {
    const v = mercato.valore(g), p = mercato.probabile(g);
    if (p <= 0.8 * v) return "affare";
    if (p >= 1.25 * v + 2) return "caro";
    return "prezzo giusto";
  }

  // Svincoli: chi fa perdere meno punti se tolto dalla rosa.
  function menoUtili(s, n = 5) {
    return s.miei.map((g) => ({ g, perdita: s.base - valoreSquadra(s.miei.filter((x) => x !== g), s.mods) }))
      .sort((a, b) => a.perdita - b.perdita).slice(0, n);
  }

  return { prepara, guadagno, piano, offertaMassima, menoUtili, fantavoto, postiLiberi, mercatoLega, offertaDaZero, giudizio };
})();
