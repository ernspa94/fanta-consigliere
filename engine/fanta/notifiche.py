"""Decide quali notifiche mandare confrontando il consiglio precedente con quello nuovo, e le invia.

Uso:  python -m fanta.notifiche <consiglio_precedente.json>   (dalla cartella engine/)
      python -m fanta.notifiche --prova                      (manda solo una notifica di prova)
Variabili d'ambiente: VAPID_PRIVATE_KEY e PUSH_ISCRIZIONI (lista JSON di {nome, iscrizione}).
Senza variabili stampa soltanto le notifiche che manderebbe.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROMA = ZoneInfo("Europe/Rome")

ROOT = Path(__file__).resolve().parents[2]
FILE_INVIATE = ROOT / "output" / "notifiche_inviate.json"
URL_APP = "https://ernspa94.github.io/fanta-consigliere/"
CONTATTO_VAPID = "https://ernspa94.github.io"  # il servizio push vuole un mailto: o un'origine senza percorso
PROMEMORIA = [("30m", 30, "Mancano 30 minuti"), ("3h", 180, "Mancano 3 ore")]  # dal più urgente


def _num(x):
    return f"{x:.1f}".replace(".", ",")


def _riassunto(c):
    return f"{c['modulo']}, {_num(c['punti_attesi'])} punti attesi"


def _motivo(g):
    if g["stato"] not in ("ok", "non in lista"):
        return g["stato"]
    return f"dato al {round(g['p_voto'] * 100)}%"


def messaggi(prec, nuovo, inviate, adesso):
    """Ritorna la lista di notifiche {titolo, testo} e aggiorna `inviate` (promemoria già mandati)."""
    out = []
    if nuovo.get("stato") != "pronto":
        return out
    g = str(nuovo["giornata"])
    gia = set(inviate.get(g, []))

    nuova_giornata = not prec or prec.get("stato") != "pronto" or prec.get("giornata") != nuovo["giornata"]
    if nuova_giornata:
        out.append({"titolo": f"Giornata {g}: consiglio pronto",
                    "testo": f"{_riassunto(nuovo)}. Uscite le probabili formazioni."})
    else:
        prima = {x["nome"] for x in prec["titolari"]}
        dopo = {x["nome"] for x in nuovo["titolari"]}
        entrano, escono = dopo - prima, prima - dopo
        if entrano or escono or prec["modulo"] != nuovo["modulo"]:
            panca = {x["nome"]: x for x in nuovo["panchina"]}
            parti = []
            if entrano:
                parti.append("entra " + ", ".join(sorted(entrano)))
            if escono:
                parti.append("esce " + ", ".join(f"{n} ({_motivo(panca[n])})" if n in panca else n
                                                 for n in sorted(escono)))
            frase = "; ".join(parti)
            out.append({"titolo": f"Formazione cambiata · giornata {g}",
                        "testo": f"{frase[0].upper()}{frase[1:]}. {_riassunto(nuovo)}."})

    if nuovo.get("scadenza"):
        minuti = (datetime.fromisoformat(nuovo["scadenza"]) - adesso).total_seconds() / 60
        for i, (chiave, soglia, frase) in enumerate(PROMEMORIA):
            if 0 < minuti <= soglia and chiave not in gia:
                titolari = ", ".join(x["nome"] for x in nuovo["titolari"])
                out.append({"titolo": f"{frase} alla consegna",
                            "testo": f"{_riassunto(nuovo)}: {titolari}."})
                # Segna anche i promemoria meno urgenti: non ha senso mandarli dopo.
                gia.update(k for k, _, _ in PROMEMORIA[i:])
                break
    inviate[g] = sorted(gia)
    return out


def invia(notifiche):
    chiave = os.environ.get("VAPID_PRIVATE_KEY")
    iscrizioni = json.loads(os.environ.get("PUSH_ISCRIZIONI") or "[]")
    for n in notifiche:
        print(f"🔔 {n['titolo']} — {n['testo']}")
    if not (chiave and iscrizioni and notifiche):
        return
    from pywebpush import WebPushException, webpush

    for n in notifiche:
        dati = json.dumps({**n, "url": URL_APP})
        for persona in iscrizioni:
            try:
                webpush(persona["iscrizione"], dati, vapid_private_key=chiave,
                        vapid_claims={"sub": CONTATTO_VAPID}, ttl=6 * 3600)
                print(f"   inviata a {persona['nome']}")
            except WebPushException as e:
                # 404/410: iscrizione scaduta, va rifatta dall'app. Non blocca le altre.
                print(f"   ⚠ non inviata a {persona['nome']}: {e}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--prova"]:
        invia([{"titolo": "Prova notifiche ✅", "testo": "Se leggi questo messaggio, gli avvisi del Fanta Consigliere funzionano."}])
        sys.exit()
    prec_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    prec = json.loads(prec_file.read_text(encoding="utf-8")) if prec_file and prec_file.stat().st_size else None
    nuovo = json.loads((ROOT / "output" / "consiglio.json").read_text(encoding="utf-8"))
    inviate = json.loads(FILE_INVIATE.read_text(encoding="utf-8")) if FILE_INVIATE.exists() else {}
    notifiche = messaggi(prec, nuovo, inviate, datetime.now(ROMA))
    invia(notifiche)
    FILE_INVIATE.write_text(json.dumps(inviate, indent=2) + "\n", encoding="utf-8")
