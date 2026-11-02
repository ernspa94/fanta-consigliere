"""Valore dei giocatori per l'asta: fantapunti attesi a giornata, sul lungo periodo.

Diverso dal consiglio settimanale: non guarda l'avversario della prossima partita né le probabili,
ma quanto spesso il giocatore prende voto e quanto fa in media. Le "componenti" (media voto, frequenza
di gol, assist, cartellini, rigori, presenza) si pubblicano per tutto il listone; il fantavoto con il
regolamento di ogni lega lo calcola l'app, che conosce il regolamento (stessa formula di fantavoto()).

Verifica sul passato:  python -m fanta.mercato   (dalla cartella engine/)
"""

import json
import math
from pathlib import Path

import numpy as np

from . import modello as M, storico_voti as SV

ROOT = Path(__file__).resolve().parents[2]
# Quota di giornate a voto di un giocatore "tipico" del listone, e quanto pesa questo valore di partenza.
PRIOR_PRESENZA = {"P": 0.30, "D": 0.45, "C": 0.45, "A": 0.45}
PARTITE_PRIOR_PRESENZA = 6
FINESTRA = 8                     # ultime giornate che contano per la presenza
PESI_PRESENZA = (0.4, 0.3, 0.3)  # stagione, a voto nelle ultime 8, titolare nelle ultime 8
VUOTO = {"pv": 0, "mv": 0, "gol": 0, "ass": 0, "amm": 0, "esp": 0, "rig_segnati": 0, "rig_tirati": 0, "rp": 0, "gs": 0}


def presenze_recenti(righe, fino_a, finestra=FINESTRA):
    """{id: (quota di giornate a voto, quota di giornate da titolare)} nelle ultime `finestra` giornate."""
    n = min(finestra, fino_a)
    if n <= 0:
        return {}
    voti, titolare = {}, {}
    for x in righe:
        if fino_a - n < x["giornata"] <= fino_a and x["voto"] is not None:
            voti[x["id"]] = voti.get(x["id"], 0) + 1
            if not x["subentrato"]:
                titolare[x["id"]] = titolare.get(x["id"], 0) + 1
    return {pid: (v / n, titolare.get(pid, 0) / n) for pid, v in voti.items()}


def _presenza(pid, ruolo, s1, s0, giornate_giocate, recenti, era_in_a):
    """Quota attesa di giornate a voto. Tarata sul 2025-26 (vedi verifica): pesano molto le ultime
    giornate, e la stagione precedente peggiora la stima (allenatori, mercato, età)."""
    if giornate_giocate == 0:  # pre-campionato: solo la stagione scorsa, ristretta verso la media di ruolo
        if not era_in_a:
            return PRIOR_PRESENZA[ruolo]
        return (s0["pv"] + PRIOR_PRESENZA[ruolo] * PARTITE_PRIOR_PRESENZA) / (38 + PARTITE_PRIOR_PRESENZA)
    stagione = s1["pv"] / giornate_giocate
    if recenti is None:
        return min(stagione, 0.98)
    voti, titolare = recenti.get(pid, (0.0, 0.0))
    return min(PESI_PRESENZA[0] * stagione + PESI_PRESENZA[1] * voti + PESI_PRESENZA[2] * titolare, 0.98)


def componenti(giocatori, stat, stat_prec, giornate_giocate, rigoristi=None, recenti=None):
    """Per ogni giocatore {id, nome, ruolo, squadra}: le componenti del suo fantavoto e la presenza.
    recenti: da presenze_recenti(); senza, la presenza è quella della stagione intera."""
    forza, _ = M.forza_squadre(stat, stat_prec, giornate_giocate)
    rig_squadra, rig_medi = M.rigori_per_partita(stat, stat_prec, giornate_giocate)
    rigoristi = rigoristi or M.rigoristi_dalle_statistiche(stat, stat_prec)
    out = []
    for g in giocatori:
        pid, r, sq = g["id"], g["ruolo"], g["squadra"]
        s1, s0 = stat.get(pid, VUOTO), stat_prec.get(pid, VUOTO)
        pr = M.PRIOR[r]
        tasso = lambda t1, t0, prior: M._tasso(t1, s1["pv"], t0, s0["pv"], prior)

        presenza = _presenza(pid, r, s1, s0, giornate_giocate, recenti, pid in stat_prec)

        ordine = rigoristi.get(sq, [])
        quota = M.QUOTA_RIGORI[ordine.index(pid)] if pid in ordine[:len(M.QUOTA_RIGORI)] else 0.0
        tiri = quota * rig_squadra.get(sq, rig_medi)
        conv = (s1["rig_segnati"] + M.PESO_STAGIONE_PREC * s0["rig_segnati"] + M.CONVERSIONE_RIGORI * 5) / (
            s1["rig_tirati"] + M.PESO_STAGIONE_PREC * s0["rig_tirati"] + 5)
        gol_azione = tasso(s1["gol"] - s1["rig_segnati"], s0["gol"] - s0["rig_segnati"], M.PRIOR_GOL_AZIONE[r])

        out.append({
            **{k: g[k] for k in ("id", "nome", "ruolo", "squadra")},
            "presenza": round(min(presenza, 0.98), 3),
            "mv": round(M._ristretto(s1["mv"], s1["pv"], s0["mv"], s0["pv"], pr["mv"]), 3),
            "gol": round(gol_azione + tiri * conv, 4),
            "ass": round(tasso(s1["ass"], s0["ass"], pr["ass"]), 4),
            "amm": round(tasso(s1["amm"], s0["amm"], pr["amm"]), 4),
            "esp": round(tasso(s1["esp"], s0["esp"], pr["esp"]), 4),
            "rig_err": round(tiri * (1 - conv), 4),
            "rp": round(tasso(s1["rp"], s0["rp"], pr["rp"]), 4),
            # Gol subiti a partita dalla squadra: per il portiere (malus e porta imbattuta).
            "gs": round(forza[sq]["difesa"], 3) if sq in forza else 1.4,
        })
    return out


def fantavoto(c, bm):
    """Fantavoto medio quando gioca, con i bonus/malus della lega (la stessa formula è in app/asta.js)."""
    r = c["ruolo"]
    fv = c["mv"] + bm["gol"][r] * c["gol"] + bm["assist"][r] * c["ass"] + bm["ammonizione"][r] * c["amm"] \
        + bm["espulsione"][r] * c["esp"] + bm["rigore_sbagliato"][r] * c["rig_err"]
    if r == "P":
        fv += bm["gol_subito"][r] * c["gs"] + bm["porta_imbattuta"][r] * math.exp(-c["gs"]) + bm["rigore_parato"][r] * c["rp"]
    return fv


def pubblica(dati, info_giornata, stato_giocatori):
    """output/valori.json: componenti di tutto il listone, per la scheda Asta dell'app (dati pubblici).
    info_giornata: da consiglia.stato_giornata (giornata e stagione da consigliare)."""
    giornata, stagione = info_giornata["giornata"], info_giornata["stagione"]
    stat, stat_prec = dati["stat"], dati["stat_prec"]
    if stagione != dati["stagione"]:
        # Fine maggio-giugno: si guarda già alla stagione nuova, quella appena finita diventa "precedente".
        stat, stat_prec = {}, dati["stat"]
    giocate = giornata - 1
    righe = SV.carica_stagione(stagione, giocate) if giocate > 0 else []
    # Per le presenze recenti contano solo le giornate finite: in una giornata in corso chi non ha
    # ancora giocato sembrerebbe assente.
    finite = [g for g in range(1, giocate + 1) if len({r["squadra"] for r in righe if r["giornata"] == g}) >= 20]
    ultima_finita = max(finite, default=0)
    comp = componenti(dati["listone"], stat, stat_prec, giocate, dati.get("rigoristi"),
                      recenti=presenze_recenti(righe, ultima_finita) if ultima_finita > 0 else None)
    prezzi = {g["id"]: g for g in dati["listone"]}
    for c in comp:
        c["q"] = prezzi[c["id"]]["q"]
        c["fvm"] = prezzi[c["id"]].get("fvm")
        nome_completo = ((dati.get("sky") or {}).get("alias") or {}).get(c["id"])
        if nome_completo:
            c["alias"] = nome_completo
        info = stato_giocatori.get(c["id"])
        if info and info.get("stato") not in (None, "ok"):
            c["stato"] = info["stato"]
            c["nota"] = info.get("nota")
    contenuto = {"giornata": giornata, "stagione": stagione, "giornate_rimanenti": 38 - giornata + 1, "giocatori": comp}
    (ROOT / "output" / "valori.json").write_text(json.dumps(contenuto, ensure_ascii=False, separators=(",", ":")),
                                                 encoding="utf-8")


# --- Verifica sul passato -------------------------------------------------------------------------

def _rango_per_ruolo(righe, chiave):
    rho = []
    for r in "PDCA":
        sel = [x for x in righe if x["ruolo"] == r]
        if len(sel) > 10:
            a = np.argsort(np.argsort([x[chiave] for x in sel]))
            b = np.argsort(np.argsort([x["vero"] for x in sel]))
            rho.append((r, len(sel), float(np.corrcoef(a, b)[0, 1])))
    return rho


def verifica(stagione="2025-26", prec="2024-25", taglio=19, regole="fanta-lignano"):
    """Con i dati fino alla giornata `taglio`, quanto si indovinano i fantapunti delle giornate successive?
    Confronto con la fantamedia × presenze fino a quel momento (quello che si guarda di solito)."""
    from .banco_prova import fantavoto_vero
    bm = json.loads((ROOT / "config" / "regole" / f"{regole}.json").read_text(encoding="utf-8"))["bonus_malus"]
    righe = SV.carica_stagione(stagione, 38)
    prima = [x for x in righe if x["giornata"] <= taglio]
    dopo = [x for x in righe if x["giornata"] > taglio and x["voto"] is not None]
    stat = SV.statistiche(prima)
    stat_prec = SV.statistiche(SV.carica_stagione(prec, 38)) if prec else {}
    vero = {}
    for x in dopo:
        vero[x["id"]] = vero.get(x["id"], 0.0) + fantavoto_vero(x)
    rimanenti = 38 - taglio

    if taglio:
        giocatori = [{"id": pid, "nome": s["nome"], "ruolo": s["ruolo"], "squadra": s["squadra"]} for pid, s in stat.items()]
    else:  # pre-campionato: chi era in A la stagione prima ed è rimasto in A
        giocatori = [{"id": pid, "nome": s["nome"], "ruolo": s["ruolo"], "squadra": s["squadra"]}
                     for pid, s in stat_prec.items() if any(x["id"] == pid for x in righe)]
    comp = componenti(giocatori, stat, stat_prec, taglio, recenti=presenze_recenti(prima, taglio) if taglio else None)
    base = stat if taglio else stat_prec
    partite_base = taglio or 38
    risultati = []
    for c in comp:
        s = base.get(c["id"])
        if not s or not s["pv"]:
            continue
        fm = (s["mv"] * s["pv"] + 3 * s["gol"] + s["ass"] - 0.5 * s["amm"] - s["esp"]
              - 3 * (s["rig_tirati"] - s["rig_segnati"]) + (3 * s["rp"] - s["gs"] if c["ruolo"] == "P" else 0)) / s["pv"]
        risultati.append({"ruolo": c["ruolo"], "nome": c["nome"],
                          "modello": c["presenza"] * fantavoto(c, bm) * rimanenti,
                          "fantamedia": fm * s["pv"] / partite_base * rimanenti,
                          "vero": vero.get(c["id"], 0.0)})
    return risultati


def stampa_verifica(nome, risultati):
    m, b = _rango_per_ruolo(risultati, "modello"), _rango_per_ruolo(risultati, "fantamedia")
    print(f"{nome}: {len(risultati)} giocatori — correlazione di rango per ruolo, modello (fantamedia × presenze)")
    for (r, n, a), (_, _, c) in zip(m, b):
        print(f"   {r}  n={n:>4}  {a:.3f}  ({c:.3f})")
    # Errore sui totali: quanto ci si sbaglia in fantapunti sul resto della stagione.
    err = np.mean([abs(x["modello"] - x["vero"]) for x in risultati])
    err_b = np.mean([abs(x["fantamedia"] - x["vero"]) for x in risultati])
    print(f"   errore medio sui fantapunti del periodo: {err:.1f} ({err_b:.1f})")


if __name__ == "__main__":
    stampa_verifica("Asta di gennaio 2026 (dati fino alla g19, risultato g20-38)", verifica(taglio=19))
    stampa_verifica("Asta d'estate 2025 (solo stagione 2024-25, risultato 2025-26 intera)", verifica(taglio=0))
