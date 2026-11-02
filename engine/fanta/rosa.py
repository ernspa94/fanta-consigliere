"""Collega i giocatori della rosa agli id di Fantacalcio.it."""

import json
import unicodedata
from pathlib import Path

FILE_ROSA = Path(__file__).resolve().parents[2] / "config" / "rosa.json"


def normalizza(testo):
    testo = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode()
    return "".join(c for c in testo.lower() if c.isalnum())


def carica_rosa():
    return json.loads(FILE_ROSA.read_text(encoding="utf-8"))


def collega_id(rosa, *fonti_giocatori):
    """Assegna `fc_id` a ogni giocatore cercando nome+squadra nelle fonti. Ritorna i non trovati."""
    indice = {}
    for fonte in fonti_giocatori:
        for pid, g in fonte.items():
            if pid is not None and g.get("squadra"):
                indice.setdefault((normalizza(g["nome"]), g["squadra"]), pid)

    mancanti = []
    for g in rosa["giocatori"]:
        if g.get("fc_id"):
            continue
        chiave = (normalizza(g["nome"]), normalizza(g["squadra"]))
        if chiave in indice:
            g["fc_id"] = indice[chiave]
        else:
            mancanti.append(g["nome"])
    return mancanti


def salva_rosa(rosa):
    FILE_ROSA.write_text(json.dumps(rosa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
