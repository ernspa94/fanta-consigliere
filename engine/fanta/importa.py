"""Manutenzione: importa nel database il consiglio di una giornata passata, preso dalla storia del repository.

Uso (dal workflow "Importa consiglio", che ha la chiave del database):
    python -m fanta.importa --codice CODICE --sorgente REF:PERCORSO [--nota "testo per l'app"]
Solo libreria standard.
"""

import argparse
import json
import re
import subprocess

from .archivio import Supabase, da_ambiente


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codice", required=True)
    ap.add_argument("--sorgente", required=True, help="es. 6fce4b3~1:output/storico/giornata-10.json")
    ap.add_argument("--nota", default="")
    a = ap.parse_args()
    if not re.fullmatch(r"[0-9a-f]{6,32}", a.codice) or not re.fullmatch(r"[\w~^./:-]+", a.sorgente):
        raise SystemExit("Parametri non validi")
    arch = da_ambiente()
    if not isinstance(arch, Supabase):
        raise SystemExit("Serve il database: mancano SUPABASE_URL / SUPABASE_SERVICE_KEY")
    if not arch.squadre([a.codice]):
        raise SystemExit("Squadra non trovata")

    consiglio = json.loads(subprocess.run(["git", "show", a.sorgente], capture_output=True, text=True, check=True).stdout)
    consiglio.setdefault("stato", "pronto")  # i primi consigli non avevano questo campo
    if a.nota:
        consiglio["nota_storico"] = a.nota
    arch.salva_consiglio(a.codice, consiglio)
    print(f"Importata la giornata {consiglio['giornata']} ({consiglio.get('modulo')}) per la squadra {a.codice[:4]}…")


if __name__ == "__main__":
    main()
