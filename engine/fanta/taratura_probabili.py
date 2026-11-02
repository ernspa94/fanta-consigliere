"""Quanto sono affidabili le probabilità di partire titolare? Confronto con chi ha giocato davvero.

Usa le probabili salvate da storico_probabili.py (l'ultima versione prima della scadenza) e i voti
della giornata: è titolare chi ha preso voto (o S.V.) senza essere subentrato.
Misura con il Brier score (errore quadratico medio della probabilità: più basso è meglio) e prova
altri valori dei pesi in modello.py per vedere se migliorano.

Uso:  python -m fanta.taratura_probabili   (dalla cartella engine/)
"""

import itertools

import numpy as np

from . import modello as M, storico_probabili as SP, storico_voti as SV
from .fonti import scarica


def titolari_veri(stagione, giornata):
    """(squadre che hanno giocato, id dei titolari) dai voti della giornata."""
    righe = SV.leggi_voti(scarica(f"/voti-fantacalcio-serie-a/{stagione}/{giornata}", max_eta_min=120), stagione, giornata)
    return {r["squadra"] for r in righe}, {r["id"] for r in righe if not r["subentrato"]}


def casi(contenuto, squadre_giocato, titolari, usa_sky=True):
    """Una riga per giocatore citato dalle fonti o titolare davvero:
    (voce fc, voce sky, Sky copre la squadra, ufficiale uscita, titolare davvero?)."""
    dati = contenuto["ultimo"]["dati"]
    sky_squadre = set(dati["squadre_sky"]) if usa_sky else set()
    out = []
    for pid, g in dati["giocatori"].items():
        if g["squadra"] not in squadre_giocato:
            continue
        fc = None
        if g["fc"] is not None:
            ok = isinstance(g["fc"], (int, float))
            fc = {"stato": "ok" if ok else g["fc"], "pct_titolare": g["fc"] if ok else 0.0, "lista": g["lista"]}
        sky = {"sky": g["sky"], "ufficiale": g.get("uff", False)} if usa_sky and g.get("sky") else None
        uff = usa_sky and g["squadra"] in dati.get("ufficiali", [])
        out.append((fc, sky, g["squadra"] in sky_squadre, uff, int(pid) in titolari))
    citati = {int(p) for p in dati["giocatori"]}
    out += [(None, None, True, False, True) for pid in titolari - citati]  # titolari che nessuno citava
    return out


def brier(righe):
    p = np.array([M.probabilita_titolare(fc, sky, copre, uff)[0] for fc, sky, copre, uff, _ in righe])
    y = np.array([vero for *_, vero in righe], dtype=float)
    return float(((p - y) ** 2).mean()), p, y


def calibrazione(p, y):
    for basso, alto in ((0, 0.1), (0.1, 0.5), (0.5, 0.8), (0.8, 0.95), (0.95, 1.01)):
        sel = (p >= basso) & (p < alto)
        if sel.any():
            print(f"   previsto {basso:.0%}–{min(alto, 1):.0%}: {sel.sum():>4} giocatori, "
                  f"in media {p[sel].mean():.0%} → titolari davvero {y[sel].mean():.0%}")


def griglia(righe):
    """Prova combinazioni dei pesi e stampa le migliori."""
    originali = (M.PESO_FANTACALCIO, dict(M.P_SKY), M.AFFIDABILITA_TITOLARE)
    prove = []
    for peso, tit, ris, aff in itertools.product((0.4, 0.5, 0.6, 0.7, 0.8, 1.0), (0.8, 0.9, 0.95),
                                                 (0.03, 0.08, 0.15), (0.9, 0.94, 0.97, 1.0)):
        M.PESO_FANTACALCIO, M.AFFIDABILITA_TITOLARE = peso, aff
        M.P_SKY.update({"titolare": tit, "riserva": ris})
        prove.append((brier(righe)[0], peso, tit, ris, aff))
    M.PESO_FANTACALCIO, M.AFFIDABILITA_TITOLARE = originali[0], originali[2]
    M.P_SKY.clear(); M.P_SKY.update(originali[1])
    print("   migliori combinazioni (Brier, peso Fantacalcio.it, Sky titolare, Sky riserva, affidabilità):")
    for b, *par in sorted(prove)[:5]:
        print(f"     {b:.4f}  {par}")


def main(stagione="2026-27"):
    salvate = SP.carica(stagione)
    if not salvate:
        print("Nessuna giornata salvata in output/probabili: si riempie da sola a ogni giornata.")
        return
    tutte_sky, tutte_fc = [], []
    for g, contenuto in salvate.items():
        squadre, titolari = titolari_veri(stagione, g)
        if not titolari:
            print(f"Giornata {g}: voti non ancora disponibili")
            continue
        con_sky, solo_fc = casi(contenuto, squadre, titolari), casi(contenuto, squadre, titolari, usa_sky=False)
        print(f"Giornata {g} ({len(squadre)} squadre): Brier con Sky {brier(con_sky)[0]:.4f}, "
              f"solo Fantacalcio.it {brier(solo_fc)[0]:.4f}")
        tutte_sky += con_sky
        tutte_fc += solo_fc
    if not tutte_fc:
        return
    b, p, y = brier(tutte_sky)
    print(f"\nTutte le giornate: Brier {b:.4f} (solo Fantacalcio.it {brier(tutte_fc)[0]:.4f})")
    calibrazione(p, y)
    griglia(tutte_sky)


if __name__ == "__main__":
    main()
