"""Archivio delle probabili (Fantacalcio.it + Sky) giornata per giornata, per tarare le probabilità.

Dopo la partita nessuno pubblica più le probabili, quindi le salviamo noi. Per ogni giornata
il file tiene la prima versione vista e l'ultima prima della scadenza (quella su cui si decide).
Sono dati pubblici: stanno nel repository, in output/probabili/<stagione>/giornata-NN.json.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

CARTELLA = Path(__file__).resolve().parents[2] / "output" / "probabili"


def istantanea(dati):
    """Per ogni giocatore citato da almeno una fonte: cosa dicevano Fantacalcio.it e Sky."""
    giocatori = {}
    for pid, g in dati["probabili"]["giocatori"].items():
        if pid is None:
            continue
        giocatori[str(pid)] = {"squadra": g["squadra"], "fc": g["pct_titolare"] if g["stato"] == "ok" else g["stato"],
                               "lista": g["lista"]}
    sky = dati.get("sky") or {"giocatori": {}, "squadre": {}}
    for pid, s in sky["giocatori"].items():
        voce = giocatori.setdefault(str(pid), {"squadra": None, "fc": None, "lista": None})
        voce.update({"sky": s["sky"], "uff": s["ufficiale"]})
    return {"squadre_sky": sorted(sky["squadre"]),
            "ufficiali": sorted(sq for sq, uff in sky["squadre"].items() if uff), "giocatori": giocatori}


def salva(dati, giornata, stagione="2026-27"):
    """Aggiorna il file della giornata. Ritorna True se è cambiato qualcosa (oltre all'orario)."""
    file = CARTELLA / stagione / f"giornata-{giornata:02d}.json"
    vecchio = json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}
    nuova = istantanea(dati)
    if vecchio.get("ultimo", {}).get("dati") == nuova:
        return False
    ora = datetime.now(timezone.utc).isoformat(timespec="minutes")
    contenuto = {
        "giornata": giornata,
        "primo": vecchio.get("primo") or {"salvato": ora, "dati": nuova},
        "ultimo": {"salvato": ora, "dati": nuova},
    }
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(contenuto, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return True


def carica(stagione="2026-27"):
    """{giornata: contenuto del file} per tutte le giornate salvate."""
    cartella = CARTELLA / stagione
    return {int(f.stem.split("-")[1]): json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(cartella.glob("giornata-*.json"))} if cartella.exists() else {}
