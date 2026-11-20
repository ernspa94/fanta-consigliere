"""Decide se il giro programmato (ogni 15 minuti) deve ricalcolare i consigli.

Ricalcola sempre se qualche squadra ha chiesto un ricalcolo dall'app, a ogni giro nelle ore
prima della scadenza (formazioni ufficiali, promemoria), altrimenti di giorno se l'ultimo calcolo
riuscito è di almeno 2 ore fa, per non scaricare le pagine di Fantacalcio.it inutilmente.
L'ultimo calcolo si legge dai giri precedenti del workflow: non conta l'orario del giro, perché
GitHub ne lancia quanti e quando vuole (a volte 3-4 al giorno, a minuti casuali).
Scrive `esegui=true|false` in $GITHUB_OUTPUT (o lo stampa). Solo libreria standard.
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .archivio import da_ambiente

ORE_INTENSIVE = 8
OGNI = timedelta(hours=2) - timedelta(minutes=10)  # margine: i giri non arrivano mai puntuali
PASSO_CALCOLO = "Calcola i consigli"
FILE = Path(__file__).resolve().parents[2] / "output" / "giornata.json"


def esegui(adesso, scadenza, ricalcoli_in_sospeso=False, ultimo_calcolo=None):
    if ricalcoli_in_sospeso:
        return True
    if scadenza and 0 < (scadenza - adesso).total_seconds() <= ORE_INTENSIVE * 3600:
        return True
    utc = adesso.astimezone(timezone.utc)
    return 6 <= utc.hour <= 22 and (ultimo_calcolo is None or adesso - ultimo_calcolo >= OGNI)


def ultimo_calcolo():
    """Fine dell'ultimo calcolo riuscito, dai giri precedenti del workflow (None se non si trova)."""
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return None

    def leggi(url):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                                   "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    giri = leggi(f"https://api.github.com/repos/{repo}/actions/workflows/consiglio.yml/runs"
                 "?status=success&per_page=15")["workflow_runs"]
    for giro in giri:
        for job in leggi(giro["jobs_url"])["jobs"]:
            for passo in job.get("steps", []):
                if passo["name"].startswith(PASSO_CALCOLO) and passo["conclusion"] == "success":
                    return datetime.fromisoformat(passo["completed_at"].replace("Z", "+00:00"))
    return None


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
    try:
        ultimo = ultimo_calcolo()
    except Exception as e:  # nel dubbio si ricalcola
        print(f"Lettura dei giri precedenti non riuscita: {e}")
        ultimo = None
    print(f"Ultimo calcolo riuscito: {ultimo}")
    # Il cron di GitHub è inaffidabile (a volte 3-4 giri al giorno): il giro ogni 15 minuti lo manda
    # Supabase (supabase/programma.sql) come workflow_dispatch con programmato=true. Gli altri avvii manuali
    # (pulsante Ricalcola, Actions → Run workflow) ricalcolano sempre.
    programmato = os.environ.get("GITHUB_EVENT_NAME") == "schedule" or os.environ.get("PROGRAMMATO") == "true"
    risultato = not programmato or esegui(
        datetime.now(timezone.utc), scadenza, in_sospeso, ultimo)
    riga = f"esegui={'true' if risultato else 'false'}"
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(riga + "\n")
    print(riga)
