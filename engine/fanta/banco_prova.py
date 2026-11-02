"""Banco di prova: quanto il modello indovina il fantavoto dei titolari, giornata per giornata.

Per ogni giornata N ricostruisce le statistiche fino alla N-1 (più la stagione precedente),
prevede il fantavoto di chi è partito titolare e lo confronta con quello vero (regole Fanta Lignano).

Uso:  python -m fanta.banco_prova   (dalla cartella engine/)
"""

import json
import math
from pathlib import Path

import numpy as np

from . import modello, storico_voti as sv

ROOT = Path(__file__).resolve().parents[2]
LEGA = json.loads((ROOT / "config" / "lega.json").read_text(encoding="utf-8"))
BM = LEGA["bonus_malus"]


def fantavoto_vero(r):
    """Fantavoto con le regole della lega (il portiere prende +1 se non subisce gol)."""
    ru = r["ruolo"]
    fv = r["voto"] + BM["gol"][ru] * (r["gol"] + r["rig_segnati"]) + BM["assist"][ru] * r["assist"] \
        + BM["ammonizione"][ru] * r["giallo"] + BM["espulsione"][ru] * r["rosso"] \
        + BM["rigore_sbagliato"][ru] * r["rig_sbagliati"] + BM["autogol"][ru] * r["autogol"] \
        + BM["rigore_parato"][ru] * r["rig_parati"] + BM["gol_subito"][ru] * r["gol_subiti"] \
        + BM["mvp_panini"][ru] * r["potm"]
    if ru == "P" and r["gol_subiti"] == 0:
        fv += BM["porta_imbattuta"][ru]
    return fv


def previsioni(righe_stagione, stat_prec, giornata, extra=None):
    """Previsione e valore vero per i titolari della giornata."""
    prima = [r for r in righe_stagione if r["giornata"] < giornata]
    della = [r for r in righe_stagione if r["giornata"] == giornata and r["voto"] is not None and not r["subentrato"]]
    partite = {(r["squadra"], r["avversario"]) for r in della if r["casa"]}
    dati = {
        "stat": sv.statistiche(prima),
        "stat_prec": stat_prec,
        "probabili": {"giornata": giornata, "partite": [{"casa": c, "trasferta": t} for c, t in partite],
                      "giocatori": {r["id"]: {"pct_titolare": 1.0, "stato": "ok", "lista": "titolare",
                                              "squadra": r["squadra"]} for r in della}},
        **(extra or {}),
    }
    rosa = {"giocatori": [{"fc_id": r["id"], "nome": r["nome"], "ruolo": r["ruolo"], "squadra": r["squadra"]}
                          for r in della]}
    params, _ = modello.parametri_giocatori(rosa, dati)
    out = []
    for p, r in zip(params, della):
        s = dati["stat"].get(r["id"])
        fm = None
        if s:  # fantamedia "ingenua" fino alla giornata prima, con le stesse regole
            fm = (s["mv"] * s["pv"] + 3 * s["gol"] + s["ass"] - 0.5 * s["amm"] - s["esp"]
                  - 3 * (s["rig_tirati"] - s["rig_segnati"]) + (3 * s["rp"] - s["gs"] if r["ruolo"] == "P" else 0)) / s["pv"]
        out.append({"ruolo": r["ruolo"], "giornata": giornata, "prev": modello.fantavoto_atteso(p, BM),
                    "fm": fm, "vero": fantavoto_vero(r), "id": r["id"]})
    return out


def metriche(righe, chiave="prev"):
    x = np.array([r[chiave] for r in righe])
    y = np.array([r["vero"] for r in righe])
    err = x - y
    # Correlazione di rango tra giocatori dello stesso ruolo nella stessa giornata: è la scelta
    # che fa l'ottimizzatore (quale difensore schierare), quindi è la misura che conta di più.
    rho, pesi = [], []
    for g, ru in sorted({(r["giornata"], r["ruolo"]) for r in righe}):
        sel = [r for r in righe if r["giornata"] == g and r["ruolo"] == ru]
        if len(sel) < 5:
            continue
        a = np.argsort(np.argsort([r[chiave] for r in sel]))
        b = np.argsort(np.argsort([r["vero"] for r in sel]))
        rho.append(np.corrcoef(a, b)[0, 1])
        pesi.append(len(sel))
    return {"n": len(righe), "errore_medio": float(np.abs(err).mean()), "rmse": float(math.sqrt((err ** 2).mean())),
            "distorsione": float(err.mean()), "corr_rango": float(np.average(rho, weights=pesi))}


def valuta(stagione, prec, giornate, extra=None):
    righe = sv.carica_stagione(stagione, max(giornate))
    stat_prec = sv.statistiche(sv.carica_stagione(prec)) if prec else {}
    tutte = []
    for g in giornate:
        tutte += previsioni(righe, stat_prec, g, extra)
    return tutte


def stampa(nome, risultati):
    con_fm = [r for r in risultati if r["fm"] is not None]
    m, b = metriche(con_fm), metriche(con_fm, "fm")
    print(f"{nome:<28} n={m['n']:>5}  errore medio {m['errore_medio']:.3f} (fantamedia {b['errore_medio']:.3f})  "
          f"rmse {m['rmse']:.3f} ({b['rmse']:.3f})  corr. rango {m['corr_rango']:.3f} ({b['corr_rango']:.3f})  "
          f"distorsione {m['distorsione']:+.3f}")
    for ruolo in "PDCA":
        sel = [r for r in con_fm if r["ruolo"] == ruolo]
        m, b = metriche(sel), metriche(sel, "fm")
        print(f"   {ruolo}  n={m['n']:>5}  errore medio {m['errore_medio']:.3f} ({b['errore_medio']:.3f})  "
              f"corr. rango {m['corr_rango']:.3f} ({b['corr_rango']:.3f})  distorsione {m['distorsione']:+.3f}")


if __name__ == "__main__":
    stampa("2025-26, giornate 4-38", valuta("2025-26", "2024-25", range(4, 39)))
    stampa("2026-27, giornate 2-9", valuta("2026-27", "2025-26", range(2, 10)))
