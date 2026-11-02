"""Decide quali notifiche mandare confrontando il consiglio precedente con quello nuovo, e le invia.

Le chiama consiglia.py per ogni squadra. Prova:  python -m fanta.notifiche --prova [CODICE]
Variabile d'ambiente VAPID_PRIVATE_KEY (senza, stampa soltanto le notifiche che manderebbe).
Le iscrizioni dei telefoni vengono dall'archivio (Supabase, o PUSH_ISCRIZIONI in locale).
"""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROMA = ZoneInfo("Europe/Rome")

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
    id_giornata = str(nuovo.get("chiave") or g)  # stagione+giornata: la giornata 1 di due stagioni è diversa
    gia = set(inviate.get(id_giornata, []))

    giornata_di = lambda c: c.get("chiave") or c.get("giornata")
    nuova_giornata = not prec or prec.get("stato") != "pronto" or giornata_di(prec) != giornata_di(nuovo)
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
    inviate[id_giornata] = sorted(gia)
    return out


def invia(notifiche, squadra, arch):
    """Manda le notifiche a chi segue la squadra. Senza VAPID_PRIVATE_KEY le stampa soltanto."""
    for n in notifiche:
        print(f"🔔 {squadra['nome']}: {n['titolo']} — {n['testo']}")
    chiave = os.environ.get("VAPID_PRIVATE_KEY")
    if not (chiave and notifiche):
        return
    iscrizioni = arch.iscrizioni(squadra["codice"])
    if not iscrizioni:
        return
    from pywebpush import WebPushException, webpush

    url = URL_APP if squadra["codice"] == "locale" else f"{URL_APP}?squadra={squadra['codice']}"
    for n in notifiche:
        # Un iPhone può seguire più squadre: il nome della squadra va nel titolo.
        dati = json.dumps({"titolo": f"{squadra['nome']} · {n['titolo']}", "testo": n["testo"], "url": url})
        for persona in iscrizioni:
            try:
                webpush(persona["iscrizione"], dati, vapid_private_key=chiave,
                        vapid_claims={"sub": CONTATTO_VAPID}, ttl=6 * 3600)
                print(f"   inviata a {persona.get('nome')}")
            except WebPushException as e:
                stato = getattr(e.response, "status_code", None)
                print(f"   ⚠ non inviata a {persona.get('nome')}: {e}")
                if stato in (404, 410):  # iscrizione scaduta: si rifà dall'app
                    arch.rimuovi_iscrizione(squadra["codice"], persona["iscrizione"]["endpoint"])


if __name__ == "__main__":
    # python -m fanta.notifiche --prova [CODICE]: notifica di prova a chi segue la squadra (o tutte)
    if sys.argv[1:2] != ["--prova"]:
        raise SystemExit("Uso: python -m fanta.notifiche --prova [CODICE]")
    from . import archivio
    arch = archivio.da_ambiente()
    for sq in arch.squadre(sys.argv[2:3] or None):
        invia([{"titolo": "Prova notifiche ✅",
                "testo": "Se leggi questo messaggio, gli avvisi del Fanta Consigliere funzionano."}], sq, arch)
