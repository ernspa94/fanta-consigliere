"""Decide se il giro programmato (ogni 15 minuti) deve ricalcolare il consiglio.

Ricalcola ogni 15 minuti nelle ore prima della scadenza (formazioni ufficiali, promemoria),
altrimenti solo ogni 2 ore di giorno, per non scaricare le pagine di Fantacalcio.it inutilmente.
Scrive `esegui=true|false` in $GITHUB_OUTPUT (o lo stampa).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ORE_INTENSIVE = 8
FILE = Path(__file__).resolve().parents[2] / "output" / "consiglio.json"


def esegui(adesso, scadenza):
    if scadenza and 0 < (scadenza - adesso).total_seconds() <= ORE_INTENSIVE * 3600:
        return True
    utc = adesso.astimezone(timezone.utc)
    return 6 <= utc.hour <= 22 and utc.hour % 2 == 0 and utc.minute < 15


if __name__ == "__main__":
    scadenza = None
    if FILE.exists():
        s = json.loads(FILE.read_text(encoding="utf-8")).get("scadenza")
        scadenza = datetime.fromisoformat(s) if s else None
    risultato = os.environ.get("GITHUB_EVENT_NAME") != "schedule" or esegui(datetime.now(timezone.utc), scadenza)
    riga = f"esegui={'true' if risultato else 'false'}"
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(riga + "\n")
    print(riga)
