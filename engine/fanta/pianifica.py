"""Decide se il giro programmato (ogni 15 minuti) deve ricalcolare i consigli.

Ricalcola sempre se qualche squadra ha chiesto un ricalcolo dall'app, ogni 15 minuti nelle ore
prima della scadenza (formazioni ufficiali, promemoria), altrimenti solo ogni 2 ore di giorno,
per non scaricare le pagine di Fantacalcio.it inutilmente.
Scrive `esegui=true|false` in $GITHUB_OUTPUT (o lo stampa). Solo libreria standard.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .archivio import da_ambiente

ORE_INTENSIVE = 8
FILE = Path(__file__).resolve().parents[2] / "output" / "giornata.json"


def esegui(adesso, scadenza, ricalcoli_in_sospeso=False):
    if ricalcoli_in_sospeso:
        return True
    if scadenza and 0 < (scadenza - adesso).total_seconds() <= ORE_INTENSIVE * 3600:
        return True
    utc = adesso.astimezone(timezone.utc)
    return 6 <= utc.hour <= 22 and utc.hour % 2 == 0 and utc.minute < 15


if __name__ == "__main__":
    scadenza = None
    if FILE.exists():
        s = json.loads(FILE.read_text(encoding="utf-8")).get("scadenza")
        scadenza = datetime.fromisoformat(s) if s else None
    try:
        in_sospeso = bool(da_ambiente().squadre(solo_da_ricalcolare=True))
    except Exception as e:  # se Supabase non risponde si va avanti con l'orario
        print(f"Controllo ricalcoli non riuscito: {e}")
        in_sospeso = False
    risultato = os.environ.get("GITHUB_EVENT_NAME") != "schedule" or esegui(
        datetime.now(timezone.utc), scadenza, in_sospeso)
    riga = f"esegui={'true' if risultato else 'false'}"
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(riga + "\n")
    print(riga)
