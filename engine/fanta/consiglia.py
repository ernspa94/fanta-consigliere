"""Calcola la formazione consigliata e la salva in output/consiglio.json.

Uso:  python -m fanta.consiglia   (dalla cartella engine/)
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from . import fonti, modello, ottimizzatore, regole, rosa as R, simulazione

ROOT = Path(__file__).resolve().parents[2]


def calcola(n_simulazioni=4000, adesso=None):
    lega = json.loads((ROOT / "config" / "lega.json").read_text(encoding="utf-8"))
    dati = fonti.carica_tutto()
    rosa = R.carica_rosa()
    adesso = adesso or datetime.now(fonti.ROMA)
    giornata = dati["probabili"]["giornata"]
    inizio = fonti.inizio_giornata(giornata)

    # Le probabili restano sulla giornata in corso finché il sito non passa alla successiva:
    # se è già iniziata la formazione non si può più cambiare, quindi si aspetta la prossima.
    if inizio and adesso >= inizio:
        prossima = fonti.inizio_giornata(giornata + 1)
        return {
            "stato": "in_attesa",
            "aggiornato": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "giornata": giornata + 1,
            "squadra": rosa["squadra"],
            "inizio": prossima.isoformat() if prossima else None,
            "scadenza": (prossima - timedelta(minutes=1)).isoformat() if prossima else None,
        }

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
        "stato": "pronto",
        "aggiornato": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "giornata": giornata,
        "squadra": rosa["squadra"],
        "inizio": inizio.isoformat() if inizio else None,
        "scadenza": (inizio - timedelta(minutes=1)).isoformat() if inizio else None,
        **formazione(best),
        "titolari": [scheda(i) for i in best["titolari"]],
        "panchina": [scheda(i) for i in best["panchina"]],
        # La migliore formazione per ogni modulo: l'app le mostra se si sceglie un altro modulo.
        "alternative": [{**formazione(a),
                         "titolari": [giocatori[i]["nome"] for i in a["titolari"]],
                         "panchina": [giocatori[i]["nome"] for i in a["panchina"]]} for a in alternative],
    }


def stampa(c):
    if c["stato"] == "in_attesa":
        print(f"\n{c['squadra']} — giornata {c['giornata']}: probabili non ancora uscite. "
              f"Scadenza formazione: {c['scadenza'] or 'non ancora fissata'}")
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


def scrivi_se_cambiato(file, consiglio):
    """Scrive il consiglio solo se cambia qualcosa oltre all'orario: così il workflow non fa commit inutili."""
    if file.exists():
        vecchio = json.loads(file.read_text(encoding="utf-8"))
        if {**vecchio, "aggiornato": None} == {**consiglio, "aggiornato": None}:
            return False
    file.write_text(json.dumps(consiglio, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


if __name__ == "__main__":
    consiglio = calcola()
    out = ROOT / "output"
    (out / "storico").mkdir(parents=True, exist_ok=True)
    scrivi_se_cambiato(out / "consiglio.json", consiglio)
    if consiglio["stato"] == "pronto":
        # Ultima versione prima della scadenza, per ogni giornata: l'app la mostra nello storico
        # e servirà per misurare quanto indovina il modello.
        scrivi_se_cambiato(out / "storico" / f"giornata-{consiglio['giornata']:02d}.json", consiglio)
    giornate = sorted(int(f.stem.split("-")[1]) for f in (out / "storico").glob("giornata-*.json"))
    (out / "storico" / "indice.json").write_text(json.dumps({"giornate": giornate}), encoding="utf-8")
    stampa(consiglio)
