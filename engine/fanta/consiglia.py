"""Calcola la formazione consigliata per ogni squadra e la salva (Supabase o, in locale, output/).

Uso:  python -m fanta.consiglia                  tutte le squadre
      python -m fanta.consiglia --codice ABC123   solo quella squadra (più quelle con un ricalcolo in sospeso)
(dalla cartella engine/)
"""

import argparse
import json
import re
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from . import archivio as A, fonti, modello, notifiche, ottimizzatore, regole, rosa as R, simulazione

ROOT = Path(__file__).resolve().parents[2]
REGOLE_STANDARD = json.loads((ROOT / "config" / "regole" / "standard.json").read_text(encoding="utf-8"))
MINIMO_PER_RUOLO = {"P": 1, "D": 3, "C": 3, "A": 1}


def stato_giornata(dati, adesso):
    """Giornata da consigliare. Le probabili restano sulla giornata in corso finché il sito non passa
    alla successiva: se è già iniziata la formazione non si può più cambiare, quindi si aspetta la prossima."""
    giornata = dati["probabili"]["giornata"]
    inizio = fonti.inizio_giornata(giornata)
    if inizio and adesso >= inizio:
        return {"giornata": giornata + 1, "pronta": False, "inizio": fonti.inizio_giornata(giornata + 1)}
    return {"giornata": giornata, "pronta": True, "inizio": inizio}


def regole_complete(regole):
    """Il regolamento della squadra sopra quello standard: le chiavi mancanti prendono il valore standard."""
    def unisci(base, sopra):
        if isinstance(base, dict) and isinstance(sopra, dict):
            return {k: unisci(base.get(k), sopra[k]) if k in sopra else v for k, v in {**base, **sopra}.items()}
        return sopra if sopra is not None else base
    return unisci(REGOLE_STANDARD, regole or {})


def rosa_incompleta(giocatori):
    conta = {r: sum(g["ruolo"] == r for g in giocatori) for r in "PDCA"}
    mancano = [f"{MINIMO_PER_RUOLO[r] - conta[r]} {nome}" for r, nome in
               (("P", "portiere"), ("D", "difensori"), ("C", "centrocampisti"), ("A", "attaccanti"))
               if conta[r] < MINIMO_PER_RUOLO[r]]
    if mancano or len(giocatori) < 11:
        return "Rosa incompleta: " + (", ".join(f"mancano {m}" for m in mancano) or "servono almeno 11 giocatori")
    return None


def calcola(squadra, dati, giornata, n_simulazioni=4000):
    inizio = giornata["inizio"]
    base = {
        "aggiornato": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "giornata": giornata["giornata"],
        "squadra": squadra["nome"],
        "inizio": inizio.isoformat() if inizio else None,
        "scadenza": (inizio - timedelta(minutes=1)).isoformat() if inizio else None,
    }
    if not giornata["pronta"]:
        return {**base, "stato": "in_attesa"}

    lega = regole_complete(squadra["regole"])
    rosa = {"giocatori": [dict(g) for g in squadra["rosa"]]}
    errore = rosa_incompleta(rosa["giocatori"])
    if errore:
        return {**base, "stato": "rosa_incompleta", "messaggio": errore}
    mancanti = R.collega_id(rosa, dati["stat"], dati["probabili"]["giocatori"], dati["stat_prec"])
    if mancanti:
        return {**base, "stato": "rosa_incompleta",
                "messaggio": f"Giocatori non trovati su Fantacalcio.it: {', '.join(mancanti)}"}

    giocatori, contesto = modello.parametri_giocatori(rosa, dati)
    ha_voto, voto, fv = simulazione.simula(giocatori, contesto, lega, n=n_simulazioni)
    try:
        best, alternative, valore = ottimizzatore.migliore_formazione(giocatori, ha_voto, voto, fv, lega)
    except ValueError as e:
        return {**base, "stato": "rosa_incompleta", "messaggio": str(e)}

    def scheda(i):
        g = giocatori[i]
        prende_voto = ha_voto[:, i]
        return {
            "nome": g["nome"], "ruolo": g["ruolo"], "squadra": g["squadra"],
            "avversario": g["avversario"], "casa": g["casa"],
            "p_voto": round(float(g["p_voto"]), 2),
            "fantavoto_se_gioca": round(float(fv[prende_voto, i].mean()), 2) if prende_voto.any() else None,
            "punti_attesi": round(float(valore[i]), 2),
            "stato": g["stato"], "nota": g["nota"],
            "rigorista": g.get("rigorista"),
            "fonti": g.get("fonti"),
        }

    soglie = lega["scontri_diretti"]["soglie_gol"]
    ruoli = [g["ruolo"] for g in giocatori]

    def formazione(f):
        """Riepilogo di una formazione (quella consigliata o la migliore di un altro modulo)."""
        tot, mod, cambi = regole.punteggio(f["titolari"], f["panchina"], ruoli, ha_voto, voto, fv, lega)
        gol = np.searchsorted(soglie, tot, side="right")
        return {
            "modulo": f["modulo"],
            "punti_attesi": round(float(tot.mean()), 1),
            "intervallo_80": [round(float(np.percentile(tot, 10)), 1), round(float(np.percentile(tot, 90)), 1)],
            "modificatore_atteso": round(float(mod.mean()), 2),
            "cambi_attesi": round(float(cambi.mean()), 1),
            "prob_gol": {str(k): round(float((gol == k).mean()), 3) for k in range(0, 6)},
        }

    return {
        **base,
        "stato": "pronto",
        **formazione(best),
        "titolari": [scheda(i) for i in best["titolari"]],
        "panchina": [scheda(i) for i in best["panchina"]],
        # La migliore formazione per ogni modulo: l'app le mostra se si sceglie un altro modulo.
        "alternative": [{**formazione(a),
                         "titolari": [giocatori[i]["nome"] for i in a["titolari"]],
                         "panchina": [giocatori[i]["nome"] for i in a["panchina"]]} for a in alternative],
    }


def stampa(c):
    if c["stato"] != "pronto":
        motivo = c.get("messaggio") or f"probabili non ancora uscite, scadenza {c['scadenza'] or 'non ancora fissata'}"
        print(f"\n{c['squadra']} — giornata {c['giornata']}: {motivo}")
        return
    casa = lambda g: "" if g["avversario"] is None else (f"vs {g['avversario']}" if g["casa"] else f"@ {g['avversario']}")
    riga = lambda g: (f"  {g['ruolo']} {g['nome']:<22}{g['squadra']:<11}{casa(g):<16}"
                      f"voto {g['p_voto']:>4.0%}  se gioca {g['fantavoto_se_gioca'] or 0:>5.1f}  "
                      f"atteso {g['punti_attesi']:>5.2f}" + (f"  ⚠ {g['stato']}" if g["stato"] != "ok" else ""))
    print(f"\n{c['squadra']} — giornata {c['giornata']} — modulo {c['modulo']}")
    print(f"Punti attesi {c['punti_attesi']} (80% tra {c['intervallo_80'][0]} e {c['intervallo_80'][1]}), "
          f"modificatore difesa atteso {c['modificatore_atteso']}, cambi attesi {c['cambi_attesi']}")
    print("Gol:", ", ".join(f"{k}: {v:.0%}" for k, v in c["prob_gol"].items()))
    print("\nTITOLARI")
    for g in c["titolari"]:
        print(riga(g))
    print("\nPANCHINA (in ordine)")
    for g in c["panchina"]:
        print(riga(g))
    print("\nALTRI MODULI:", ", ".join(f"{a['modulo']} {a['punti_attesi']}" for a in c["alternative"]))


def cambiato(vecchio, nuovo):
    """Conta tutto tranne l'orario di calcolo: evita scritture (e commit) inutili."""
    return vecchio is None or {**vecchio, "aggiornato": None} != {**nuovo, "aggiornato": None}


def pubblica_dati_comuni(dati, giornata):
    """Listone per la ricerca nell'app e orari della giornata per pianifica.py: dati pubblici."""
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    (out / "listone.json").write_text(json.dumps(dati["listone"], ensure_ascii=False, separators=(",", ":")),
                                      encoding="utf-8")
    inizio = giornata["inizio"]
    (out / "giornata.json").write_text(json.dumps({
        "giornata": giornata["giornata"], "pronta": giornata["pronta"],
        "inizio": inizio.isoformat() if inizio else None,
        "scadenza": (inizio - timedelta(minutes=1)).isoformat() if inizio else None,
    }, indent=2) + "\n", encoding="utf-8")


def main(codice=None, adesso=None):
    arch = A.da_ambiente()
    adesso = adesso or datetime.now(fonti.ROMA)
    dati = fonti.carica_tutto()
    giornata = stato_giornata(dati, adesso)
    pubblica_dati_comuni(dati, giornata)

    if codice and not re.fullmatch(r"[0-9a-f]{6,32}", codice):
        raise SystemExit("Codice squadra non valido")
    if codice:
        squadre = {s["codice"]: s for s in arch.squadre([codice]) + arch.squadre(solo_da_ricalcolare=True)}.values()
    else:
        squadre = arch.squadre()

    errori = 0
    for sq in squadre:
        try:
            c = calcola(sq, dati, giornata)
            prec = arch.ultimo_consiglio(sq["codice"])
            if cambiato(prec, c):
                arch.salva_consiglio(sq["codice"], c)
            inviate = json.loads(json.dumps(sq.get("notifiche_inviate") or {}))
            avvisi = notifiche.messaggi(prec, c, inviate, adesso)
            notifiche.invia(avvisi, sq, arch)
            campi = {}
            if inviate != (sq.get("notifiche_inviate") or {}):
                campi["notifiche_inviate"] = inviate
            if sq.get("ricalcolo_richiesto"):
                campi["ricalcolo_richiesto"] = None
            if campi:
                arch.aggiorna_squadra(sq["codice"], campi)
            stampa(c)
        except Exception:
            errori += 1
            print(f"\n⚠ Errore con la squadra {sq.get('nome')} ({sq['codice'][:4]}…):")
            traceback.print_exc()
    if errori:
        raise SystemExit(f"{errori} squadre non calcolate")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--codice")
    main(ap.parse_args().codice)
