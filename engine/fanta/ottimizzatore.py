"""Sceglie modulo, titolari e ordine della panchina che massimizzano i punti attesi."""

import numpy as np

from .regole import punteggio

TOLLERANZA = 0.05  # differenze di punti attesi più piccole di così sono rumore


def _formazione(modulo, valore, per_ruolo):
    d, c, a = (int(x) for x in modulo.split("-"))
    titolari = []
    for r, quanti in (("P", 1), ("D", d), ("C", c), ("A", a)):
        titolari += per_ruolo[r][:quanti]
    panchina = sorted((i for r in "PDCA" for i in per_ruolo[r] if i not in titolari),
                      key=lambda i: -valore[i])
    return titolari, panchina


def _ordina(titolari, panchina, valore, ruoli):
    """Titolari in ordine P, D, C, A (dentro il ruolo per valore), panchina per valore."""
    tit = sorted(titolari, key=lambda i: ("PDCA".index(ruoli[i]), -valore[i]))
    return tit, sorted(panchina, key=lambda i: -valore[i])


def migliore_formazione(giocatori, ha_voto, voto, fv, lega):
    ruoli = [g["ruolo"] for g in giocatori]
    valore = fv.mean(axis=0)  # fantapunti attesi del singolo, contando anche il rischio di non giocare
    per_ruolo = {r: sorted((i for i, x in enumerate(ruoli) if x == r), key=lambda i: -valore[i]) for r in "PDCA"}

    def totali(tit, pan):
        return punteggio(tit, pan, ruoli, ha_voto, voto, fv, lega)[0]

    def confronta(nuovo, vecchio):
        """Differenza media tra due formazioni sugli stessi scenari, e la soglia oltre cui non è rumore."""
        d = nuovo - vecchio
        return d.mean(), max(TOLLERANZA, 2 * d.std() / np.sqrt(len(d)))

    risultati = []
    for modulo in lega["moduli"]:
        d, c, a = (int(x) for x in modulo.split("-"))
        if len(per_ruolo["P"]) < 1 or len(per_ruolo["D"]) < d or len(per_ruolo["C"]) < c or len(per_ruolo["A"]) < a:
            continue  # la rosa non ha abbastanza giocatori per questo modulo
        tit, pan = _formazione(modulo, valore, per_ruolo)
        migliore = totali(tit, pan)
        # Ricerca locale: prova a scambiare ogni titolare con un panchinaro dello stesso ruolo.
        # Si cambia solo se il guadagno supera il rumore della simulazione; a parità preferisce
        # il giocatore che vale di più da solo (altrimenti potrebbe tenere titolare un incerto
        # "tanto se non gioca entra il panchinaro", che in media vale uguale ma è controintuitivo).
        migliorato, giri = True, 0
        while migliorato and giri < 50:
            migliorato, giri = False, giri + 1
            for s in range(len(tit)):
                for k in range(len(pan)):
                    if ruoli[tit[s]] != ruoli[pan[k]]:
                        continue
                    t2, p2 = tit.copy(), pan.copy()
                    t2[s], p2[k] = pan[k], tit[s]
                    t2, p2 = _ordina(t2, p2, valore, ruoli)
                    t = totali(t2, p2)
                    diff, soglia = confronta(t, migliore)
                    meglio = diff > soglia
                    pari_ma_piu_forte = diff > -soglia and valore[pan[k]] > valore[tit[s]] + 0.1
                    if meglio or pari_ma_piu_forte:
                        tit, pan, migliore, migliorato = t2, p2, t, True
                        break
                if migliorato:
                    break
        tit, pan = _ordina(tit, pan, valore, ruoli)
        risultati.append({"modulo": modulo, "titolari": tit, "panchina": pan, "media": float(migliore.mean())})

    if not risultati:
        raise ValueError("Con questa rosa non si può schierare nessuno dei moduli ammessi")
    risultati.sort(key=lambda x: -x["media"])
    best = risultati[0]
    totale, mod, cambi = punteggio(best["titolari"], best["panchina"], ruoli, ha_voto, voto, fv, lega)
    best.update({"totale": totale, "modificatore": mod, "cambi": cambi})
    return best, risultati, valore
