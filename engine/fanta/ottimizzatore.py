"""Sceglie modulo, titolari e ordine della panchina che massimizzano i punti attesi."""

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

    def media(tit, pan):
        return punteggio(tit, pan, ruoli, ha_voto, voto, fv, lega)[0].mean()

    risultati = []
    for modulo in lega["moduli"]:
        d, c, a = (int(x) for x in modulo.split("-"))
        if len(per_ruolo["P"]) < 1 or len(per_ruolo["D"]) < d or len(per_ruolo["C"]) < c or len(per_ruolo["A"]) < a:
            continue  # la rosa non ha abbastanza giocatori per questo modulo
        tit, pan = _formazione(modulo, valore, per_ruolo)
        migliore = media(tit, pan)
        # Ricerca locale: prova a scambiare ogni titolare con un panchinaro dello stesso ruolo.
        # A parità di punti (entro TOLLERANZA) preferisce il giocatore che vale di più da solo:
        # altrimenti potrebbe tenere titolare un infortunato "tanto entra il panchinaro".
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
                    m = media(t2, p2)
                    meglio = m > migliore + TOLLERANZA
                    pari_ma_piu_forte = m > migliore - TOLLERANZA and valore[pan[k]] > valore[tit[s]] + 0.1
                    if meglio or pari_ma_piu_forte:
                        tit, pan, migliore, migliorato = t2, p2, m, True
                        break
                if migliorato:
                    break
        tit, pan = _ordina(tit, pan, valore, ruoli)
        risultati.append({"modulo": modulo, "titolari": tit, "panchina": pan, "media": migliore})

    if not risultati:
        raise ValueError("Con questa rosa non si può schierare nessuno dei moduli ammessi")
    risultati.sort(key=lambda x: -x["media"])
    best = risultati[0]
    totale, mod, cambi = punteggio(best["titolari"], best["panchina"], ruoli, ha_voto, voto, fv, lega)
    best.update({"totale": totale, "modificatore": mod, "cambi": cambi})
    return best, risultati, valore
