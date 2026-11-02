"""Punteggio di una formazione secondo le regole di Leghe Fantacalcio / Fanta Lignano.

Lavora su tutti gli scenari simulati insieme (array numpy, una riga per scenario).
"""

import numpy as np

RUOLI = "PDCA"


def _moduli_validi(lega):
    ok = np.zeros((11, 11, 11), dtype=bool)
    for m in lega["moduli"]:
        d, c, a = (int(x) for x in m.split("-"))
        ok[d, c, a] = True
    return ok


def punteggio(titolari, panchina, ruoli, ha_voto, voto, fv, lega):
    """Punti della squadra in ogni scenario.

    titolari: 11 indici di giocatori, portiere per primo; panchina: indici in ordine di ingresso.
    ruoli: lista ruolo ('P','D','C','A') per indice giocatore.
    Ritorna (totale, modificatore, cambi): array di lunghezza n.
    """
    n = ha_voto.shape[0]
    sost = lega["sostituzioni"]
    moduli_ok = _moduli_validi(lega)

    ruolo_slot = np.tile(np.array([RUOLI.index(ruoli[t]) for t in titolari]), (n, 1))
    pieno = ha_voto[:, titolari].copy()
    fv_slot = fv[:, titolari].copy()
    voto_slot = voto[:, titolari].copy()
    usato = np.zeros((n, len(panchina)), dtype=bool)
    cambi = np.zeros(n, dtype=int)
    ruolo_panca = [RUOLI.index(ruoli[b]) for b in panchina]

    def entra(mask, s, k, b):
        pieno[mask, s] = True
        fv_slot[mask, s] = fv[mask, b]
        voto_slot[mask, s] = voto[mask, b]
        usato[mask, k] = True
        cambi[mask] += 1

    # 1) Panchinaro dello stesso ruolo, nell'ordine della panchina (portiere per primo).
    for s in range(11):
        manca = ~pieno[:, s]
        for k, b in enumerate(panchina):
            cand = manca & (ruolo_slot[:, s] == ruolo_panca[k]) & ha_voto[:, b] & ~usato[:, k] \
                & (cambi < sost["max"])
            if cand.any():
                entra(cand, s, k, b)
                manca &= ~cand

    # 2) Cambio modulo: un panchinaro di altro ruolo, solo se il modulo risultante è ammesso.
    for s in range(1, 11):
        for k, b in enumerate(panchina):
            rb = ruolo_panca[k]
            if rb == 0:
                continue
            manca = ~pieno[:, s]
            if not manca.any():
                break
            conta = np.stack([(ruolo_slot == r).sum(axis=1) for r in (1, 2, 3)], axis=1)
            conta[np.arange(n), ruolo_slot[:, s] - 1] -= 1
            conta[:, rb - 1] += 1
            cand = manca & (ruolo_slot[:, s] != rb) & ha_voto[:, b] & ~usato[:, k] \
                & (cambi < sost["max"]) & moduli_ok[conta[:, 0], conta[:, 1], conta[:, 2]]
            if cand.any():
                ruolo_slot[cand, s] = rb
                entra(cand, s, k, b)

    totale = np.where(pieno, fv_slot, sost["voto_senza_voto_non_sostituibile"]).sum(axis=1)

    # Modificatore difesa: portiere a voto e almeno 4 difensori a voto.
    mod = np.zeros(n)
    md = lega["modificatore_difesa"]
    if md["attivo"]:
        dif = pieno & (ruolo_slot == 1)
        portiere_ok = pieno[:, 0] & (ruolo_slot[:, 0] == 0)
        attivo = portiere_ok & (dif.sum(axis=1) >= md["minimo_difensori_schierati"])
        voti_dif = np.sort(np.where(dif, voto_slot, -np.inf), axis=1)[:, -md["difensori_considerati"]:]
        media = (voto_slot[:, 0] + np.where(np.isfinite(voti_dif), voti_dif, 0).sum(axis=1)) \
            / (md["difensori_considerati"] + 1)
        for fascia in sorted(md["fasce"], key=lambda f: f["media_min"]):
            mod = np.where(attivo & (media >= fascia["media_min"]), fascia["bonus"], mod)

    return totale + mod, mod, cambi
