"""Simulazione Monte Carlo della giornata: per ogni scenario, chi prende voto e quanto fa.

Simulare (invece di sommare medie) permette di applicare esattamente le regole della lega:
sostituzioni dalla panchina, massimo 5 cambi, modificatore difesa.
"""

import numpy as np

SD_VOTO = {"P": 0.75, "D": 0.55, "C": 0.55, "A": 0.6}
MINUTI_DA_SUBENTRATO = 0.3


def simula(giocatori, contesto, lega, n=4000, seed=0):
    """Ritorna (ha_voto, voto, fantavoto): array n × giocatori."""
    rng = np.random.default_rng(seed)
    bm = lega["bonus_malus"]

    # Gol per squadra, condivisi da tutti i giocatori della stessa partita.
    gol_squadra = {}
    for sq, c in contesto.items():
        if c["casa"]:
            gol_squadra[sq] = rng.poisson(c["gol_fatti"], n)
            gol_squadra[c["avversario"]] = rng.poisson(c["gol_subiti"], n)

    k = len(giocatori)
    ha_voto = np.zeros((n, k), dtype=bool)
    voto = np.zeros((n, k))
    fv = np.zeros((n, k))

    for j, g in enumerate(giocatori):
        r = g["ruolo"]
        u = rng.random(n)
        titolare = u < g["p_titolare"] * 0.97
        subentrato = (u >= g["p_titolare"]) & (u < g["p_titolare"] + (1 - g["p_titolare"]) * g["p_ingresso"])
        gioca = titolare | subentrato
        minuti = np.where(titolare, 1.0, MINUTI_DA_SUBENTRATO)
        fa = g["fattore_attacco"]

        gol = rng.poisson(g["gol"] * fa * minuti)
        ass = rng.poisson(g["ass"] * fa * minuti)
        giallo = rng.random(n) < g["amm"] * minuti
        rosso = rng.random(n) < g["esp"] * minuti
        rig_err = rng.random(n) < g["rig_err"] * minuti

        v = g["mv_partita"] + rng.normal(0, SD_VOTO[r], n)
        # Chi segna o fa assist prende anche un voto più alto (rispetto alla sua media).
        v += 0.5 * (gol - g["gol"] * fa * minuti) + 0.25 * (ass - g["ass"] * fa * minuti)
        bonus = gol * bm["gol"][r] + ass * bm["assist"][r] + giallo * bm["ammonizione"][r] \
            + rosso * bm["espulsione"][r] + rig_err * bm["rigore_sbagliato"][r]

        sq, avv = g["squadra"], g.get("avversario")
        if avv is not None:
            subiti = gol_squadra[avv]
            if r in ("P", "D"):
                v -= 0.25 * (subiti - g["gol_subiti_squadra"]) * minuti
            else:
                v += 0.10 * (gol_squadra[sq] - g["gol_fatti_squadra"])
            if r == "P":
                bonus = bonus + subiti * bm["gol_subito"][r] + (subiti == 0) * bm["porta_imbattuta"][r] \
                    + (rng.random(n) < g["rp"]) * bm["rigore_parato"][r]

        p_mvp = np.where(titolare, np.where(gol > 0, 0.25, 0.02), 0.0)
        bonus = bonus + (rng.random(n) < p_mvp) * bm["mvp_panini"][r]

        v = np.clip(np.round(v * 2) / 2, 3.0, 10.0)
        ha_voto[:, j] = gioca
        voto[:, j] = np.where(gioca, v, 0.0)
        fv[:, j] = np.where(gioca, v + bonus, 0.0)

    return ha_voto, voto, fv
