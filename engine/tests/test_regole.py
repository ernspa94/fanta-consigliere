"""Verifica le regole di Fanta Lignano su scenari costruiti a mano (uno scenario = una riga)."""

import json
from pathlib import Path

import numpy as np
import pytest

from fanta.regole import punteggio

LEGA = json.loads((Path(__file__).resolve().parents[2] / "config" / "regole" / "fanta-lignano.json").read_text(encoding="utf-8"))


def squadra(spec):
    """spec: lista di (ruolo, voto o None se senza voto, bonus). Ritorna ruoli, ha_voto, voto, fv (n=1)."""
    ruoli = [r for r, _, _ in spec]
    ha = np.array([[v is not None for _, v, _ in spec]])
    voto = np.array([[v or 0.0 for _, v, _ in spec]])
    fv = np.array([[(v or 0.0) + b if v is not None else 0.0 for _, v, b in spec]])
    return ruoli, ha, voto, fv


def calcola(spec, n_titolari=11):
    ruoli, ha, voto, fv = squadra(spec)
    tit = list(range(n_titolari))
    pan = list(range(n_titolari, len(spec)))
    tot, mod, cambi = punteggio(tit, pan, ruoli, ha, voto, fv, LEGA)
    return tot[0], mod[0], cambi[0]


# 4-3-3 tutti a 6, nessun bonus. Difesa media 6.0 → modificatore +1.
BASE_433 = [("P", 6, 0)] + [("D", 6, 0)] * 4 + [("C", 6, 0)] * 3 + [("A", 6, 0)] * 3


def test_tutti_a_voto_con_modificatore_minimo():
    tot, mod, cambi = calcola(BASE_433)
    assert mod == 1 and cambi == 0 and tot == 66 + 1


def test_sostituzione_stesso_ruolo_rispetta_ordine_panchina():
    spec = BASE_433.copy()
    spec[1] = ("D", None, 0)
    spec += [("C", 7, 0), ("D", 6.5, 0), ("D", 8, 0)]  # entra il primo D in panchina (6.5), non l'8
    tot, mod, cambi = calcola(spec)
    assert cambi == 1
    assert tot == 60 + 6.5 + 1  # media difesa (6 + 6.5 + 6 + 6)/4 < 6.5 → +1


def test_portiere_senza_voto_e_senza_riserva_vale_zero_e_niente_modificatore():
    spec = BASE_433.copy()
    spec[0] = ("P", None, 0)
    spec += [("D", 6, 0)]
    tot, mod, cambi = calcola(spec)
    assert mod == 0 and tot == 60


def test_massimo_cinque_cambi():
    spec = [("P", 6, 0)] + [("D", None, 0)] * 4 + [("C", None, 0)] * 3 + [("A", 6, 0)] * 3
    spec += [("D", 6, 0)] * 4 + [("C", 6, 0)] * 3
    tot, mod, cambi = calcola(spec)
    assert cambi == 5
    assert mod == 1  # entrano i 4 difensori: portiere + difesa tutti a 6
    assert tot == 6 + 18 + 5 * 6 + 1  # due centrocampisti restano a 0


def test_cambio_modulo_se_ammesso():
    # 4-3-3: manca un attaccante, nessun A in panchina → entra un C (diventa 4-4-2, ammesso).
    spec = BASE_433.copy()
    spec[10] = ("A", None, 0)
    spec += [("C", 7, 0)]
    tot, _, cambi = calcola(spec)
    assert cambi == 1 and tot == 60 + 7 + 1


def test_cambio_modulo_vietato_se_modulo_inesistente():
    # 3-4-3: manca un difensore, in panchina solo un attaccante → 2-4-4 non esiste, resta 0.
    spec = [("P", 6, 0)] + [("D", 6, 0)] * 2 + [("D", None, 0)] + [("C", 6, 0)] * 4 + [("A", 6, 0)] * 3
    spec += [("A", 9, 0)]
    tot, _, cambi = calcola(spec)
    assert cambi == 0 and tot == 60


@pytest.mark.parametrize("portiere, voti_dif, atteso", [
    (7, (7, 7, 7, 4), 6),          # (7 + 7 + 7 + 7) / 4 = 7     → +6; il 4 è escluso
    (6.5, (6.5, 6.5, 6.5, 5), 3),  # media 6.5                   → +3
    (7, (6, 6, 5.5, 5), 1),        # (7 + 6 + 6 + 5.5) / 4 = 6.125 → +1
    (5.5, (6, 6, 5.5, 5), 0),      # media 5.75                  → 0
])
def test_fasce_modificatore(portiere, voti_dif, atteso):
    spec = [("P", portiere, 0)] + [("D", v, 0) for v in voti_dif] + [("C", 6, 0)] * 3 + [("A", 6, 0)] * 3
    _, mod, _ = calcola(spec)
    assert mod == atteso


def test_modificatore_non_conta_i_bonus():
    spec = BASE_433.copy()
    spec[1] = ("D", 6, 3)  # gol del difensore: +3 al totale ma non alla media del modificatore
    tot, mod, _ = calcola(spec)
    assert mod == 1 and tot == 66 + 3 + 1


def test_modificatore_serve_almeno_quattro_difensori():
    spec = [("P", 8, 0)] + [("D", 8, 0)] * 3 + [("C", 6, 0)] * 4 + [("A", 6, 0)] * 3
    _, mod, _ = calcola(spec)
    assert mod == 0
