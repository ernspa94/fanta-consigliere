"""Calcola la formazione consigliata e la salva in output/consiglio.json.

Uso:  python -m fanta.consiglia   (dalla cartella engine/)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import fonti, modello, rosa as R, simulazione, ottimizzatore

ROOT = Path(__file__).resolve().parents[2]


def calcola(n_simulazioni=4000):
    lega = json.loads((ROOT / "config" / "lega.json").read_text(encoding="utf-8"))
    dati = fonti.carica_tutto()
    rosa = R.carica_rosa()
    mancanti = R.collega_id(rosa, dati["stat"], dati["probabili"]["giocatori"], dati["stat_prec"])
    if mancanti:
        raise SystemExit(f"Giocatori non trovati su Fantacalcio.it: {', '.join(mancanti)}")

    giocatori, contesto = modello.parametri_giocatori(rosa, dati)
    ha_voto, voto, fv = simulazione.simula(giocatori, contesto, lega, n=n_simulazioni)
    best, alternative, valore = ottimizzatore.migliore_formazione(giocatori, ha_voto, voto, fv, lega)

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
        }

    tot = best["totale"]
    soglie = lega["scontri_diretti"]["soglie_gol"]
    gol = np.searchsorted(soglie, tot, side="right")
    return {
        "aggiornato": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "giornata": dati["probabili"]["giornata"],
        "squadra": rosa["squadra"],
        "modulo": best["modulo"],
        "titolari": [scheda(i) for i in best["titolari"]],
        "panchina": [scheda(i) for i in best["panchina"]],
        "punti_attesi": round(float(tot.mean()), 1),
        "intervallo_80": [round(float(np.percentile(tot, 10)), 1), round(float(np.percentile(tot, 90)), 1)],
        "modificatore_atteso": round(float(best["modificatore"].mean()), 2),
        "cambi_attesi": round(float(best["cambi"].mean()), 1),
        "prob_gol": {str(k): round(float((gol == k).mean()), 3) for k in range(0, 6)},
        "alternative": [{"modulo": a["modulo"], "punti_attesi": round(float(a["media"]), 1)} for a in alternative],
    }


def stampa(c):
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


if __name__ == "__main__":
    consiglio = calcola()
    out = ROOT / "output"
    (out / "storico").mkdir(parents=True, exist_ok=True)
    testo = json.dumps(consiglio, ensure_ascii=False, indent=2)
    (out / "consiglio.json").write_text(testo, encoding="utf-8")
    # Ultima versione per ogni giornata: servirà per misurare quanto indovina il modello.
    (out / "storico" / f"giornata-{consiglio['giornata']:02d}.json").write_text(testo, encoding="utf-8")
    stampa(consiglio)
