"""Scarica e legge i dati da Fantacalcio.it: probabili formazioni e statistiche."""

import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

BASE = "https://www.fantacalcio.it"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
ROMA = ZoneInfo("Europe/Rome")

def stagione_corrente(oggi=None, indietro=0):
    """Stagione di Serie A da usare oggi, es. '2026-27'. Da luglio si passa a quella nuova
    (asta estiva, calendario). indietro=1 dà la stagione precedente."""
    oggi = oggi or datetime.now(ROMA)
    anno = (oggi.year if oggi.month >= 7 else oggi.year - 1) - indietro
    return f"{anno}-{(anno + 1) % 100:02d}"


def stagione_dopo(stagione):
    anno = int(stagione[:4]) + 1
    return f"{anno}-{(anno + 1) % 100:02d}"


def chiave_giornata(stagione, giornata):
    """Numero unico per giornata e stagione (202611 = giornata 11 del 2026-27): lo storico non mescola le stagioni."""
    return int(stagione[:4]) * 100 + giornata


# /serie-a/squadre/<squadra>/<giocatore>/<id>
LINK_GIOCATORE = re.compile(r"/squadre/([^/]+)/[^/]+/(\d+)")


def scarica(percorso, max_eta_min=30):
    """Scarica una pagina, riusando la copia in cache se è più recente di max_eta_min."""
    CACHE.mkdir(parents=True, exist_ok=True)
    file = CACHE / (percorso.strip("/").replace("/", "_") + ".html")
    if file.exists() and time.time() - file.stat().st_mtime < max_eta_min * 60:
        return file.read_text(encoding="utf-8")
    req = urllib.request.Request(BASE + percorso, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8")
    file.write_text(html, encoding="utf-8")
    return html


def _id_squadra(a):
    m = LINK_GIOCATORE.search(a.get("href", ""))
    return (int(m.group(2)), m.group(1)) if m else (None, None)


def _numero(testo):
    testo = testo.strip().replace(",", ".")
    try:
        return float(testo)
    except ValueError:
        return 0.0


def leggi_probabili(html):
    """Partite della giornata e, per ogni giocatore citato, % di titolarità e stato."""
    soup = BeautifulSoup(html, "html.parser")
    m = re.search(r"Giornata\s+(\d+)", soup.get_text())
    giornata = int(m.group(1)) if m else None
    # Di che stagione sono? D'estate la pagina mostra ancora l'ultima giornata della stagione finita.
    m = re.search(r"Serie A (\d{4}-\d{2})", html)
    stagione = m.group(1) if m else None

    partite, giocatori = [], {}
    for blocco in soup.select(".match.match-item"):
        casa = blocco.select_one("label.team-home a.team-name")["href"].rstrip("/").split("/")[-1]
        trasferta = blocco.select_one("label.team-away a.team-name")["href"].rstrip("/").split("/")[-1]
        partite.append({"casa": casa, "trasferta": trasferta})

        for card in blocco.select("div.team-card"):
            for lista, tipo in (("ul.starters", "titolare"), ("ul.reserves", "panchina")):
                for li in card.select(f"{lista} li.player-item"):
                    pid, squadra = _id_squadra(li.select_one("a.player-link"))
                    pct = li.select_one(".progress-value")
                    giocatori[pid] = {
                        "nome": li.select_one("a.player-link span").get_text(strip=True),
                        "squadra": squadra,
                        "ruolo": li.select_one("span.role")["data-value"].upper(),
                        "lista": tipo,
                        "pct_titolare": _numero(pct.get_text().replace("%", "")) / 100 if pct else 0.0,
                        "stato": "ok",
                    }

        for sezione, stato in (("section.injureds", "infortunato"), ("section.suspendeds", "squalificato")):
            for a in blocco.select(f"{sezione} a.player-link"):
                pid, squadra = _id_squadra(a)
                info = giocatori.setdefault(pid, {"nome": a.get_text(strip=True), "squadra": squadra,
                                                  "ruolo": None, "lista": None, "pct_titolare": 0.0})
                info["stato"] = stato
                info["pct_titolare"] = 0.0
                nota = a.find_next_sibling("p")
                if nota:
                    info["nota"] = nota.get_text(" ", strip=True)

    return {"giornata": giornata, "stagione": stagione, "partite": partite, "giocatori": giocatori}


def leggi_statistiche(html):
    """Statistiche stagionali per giocatore (chiave: id Fantacalcio.it)."""
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for tr in soup.select("tr.player-row"):
        pid, squadra = _id_squadra(tr.select_one("a.player-link"))
        if pid is None:
            continue
        col = {td["data-col-key"]: td.get_text(strip=True) for td in tr.select("td[data-col-key]")}
        rig_segnati, rig_tirati = (int(x) for x in col.get("rig", "0 / 0").replace(" ", "").split("/"))
        out[pid] = {
            "nome": tr.select_one("a.player-link span").get_text(strip=True),
            "squadra": squadra,
            "ruolo": tr["data-filter-role-classic"].upper(),
            "pv": int(_numero(col.get("pg", "0"))),
            "mv": _numero(col.get("mv", "0")),
            "fm": _numero(col.get("mfv", "0")),
            "gol": int(_numero(col.get("gol", "0"))),
            "gs": int(_numero(col.get("gs", "0"))),
            "rig_segnati": rig_segnati,
            "rig_tirati": rig_tirati,
            "rp": int(_numero(col.get("rp", "0"))),
            "ass": int(_numero(col.get("ass", "0"))),
            "amm": int(_numero(col.get("amm", "0"))),
            "esp": int(_numero(col.get("esp", "0"))),
        }
    return out


def leggi_listone(html):
    """Tutti i giocatori di Serie A con ruolo Classic e quotazione attuale, ordinati per nome."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tr in soup.select("tr.player-row"):
        pid, squadra = _id_squadra(tr.select_one("a.player-link"))
        q = tr.select_one('td[data-col-key="c_qa"]')
        fvm = tr.select_one('td[data-col-key="c_fvm"]')
        out.append({"id": pid, "nome": tr.select_one("a.player-link span").get_text(strip=True),
                    "ruolo": tr["data-filter-role-classic"].upper(), "squadra": squadra,
                    "q": int(_numero(q.get_text())) if q else 0,
                    "fvm": int(_numero(fvm.get_text())) if fvm else None})
    return sorted(out, key=lambda g: g["nome"].lower())


def leggi_rigoristi(html):
    """Per ogni squadra, gli id dei rigoristi in ordine (1°, 2°, 3°)."""
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for card in soup.select("div.team-card"):
        for col in card.select("div.col"):
            titolo = col.select_one("header")
            if titolo and titolo.get_text(strip=True).lower() == "rigori":
                ordine = [_id_squadra(a) for a in col.select("ol a.player-link")]
                if ordine:
                    out[ordine[0][1]] = [pid for pid, _ in ordine]
    return out


def inizio_giornata(giornata, stagione=None):
    """Data e ora della prima partita della giornata (la pagina della giornata mostra quella).
    None se non è ancora fissata o la pagina non c'è (es. calendario della stagione nuova non ancora uscito)."""
    try:
        html = scarica(f"/serie-a/calendario/{giornata}/{stagione or stagione_corrente()}", max_eta_min=360)
        box = BeautifulSoup(html, "html.parser").select_one("div.match-date")
        data = box.select_one('meta[itemprop="startDate"]')["content"]
        ora = box.select_one("span.hours").get_text(strip=True)
    except Exception as e:
        print(f"Orario della giornata {giornata} non disponibile: {e}")
        return None
    if data.startswith("1970"):
        return None  # orario non ancora fissato
    return datetime.fromisoformat(f"{data}T{ora}").replace(tzinfo=ROMA)


def carica_sky(giornata, listone):
    """Probabili/ufficiali di Sky abbinate agli id, solo se riguardano la stessa giornata.
    Se Sky non risponde o cambia pagina si va avanti con la sola Fantacalcio.it."""
    from . import sky
    try:
        dati = sky.aggiungi_ufficiali(sky.leggi(sky.scarica()))
    except Exception as e:
        print(f"Sky non disponibile: {e}")
        return None
    if dati["giornata"] != giornata:
        print(f"Sky è sulla giornata {dati['giornata']}, Fantacalcio.it sulla {giornata}: Sky ignorata")
        return None
    giocatori, sconosciuti, alias = sky.abbina(dati, listone)
    if sconosciuti:
        print(f"Sky: {len(sconosciuti)} nomi non riconosciuti (di solito Primavera): {', '.join(sconosciuti[:10])}")
    # squadre coperte da Sky -> True se la formazione ufficiale è già uscita
    return {"giocatori": giocatori, "squadre": {sq: d["ufficiale"] for sq, d in dati["squadre"].items()},
            "alias": alias}


def _facoltativo(nome, funzione, predefinito):
    """Una fonte secondaria che non risponde non deve fermare tutto."""
    try:
        return funzione()
    except Exception as e:
        print(f"{nome} non disponibile: {e}")
        return predefinito


def carica_tutto(stagione=None, stagione_prec=None):
    stagione = stagione or stagione_corrente()
    stagione_prec = stagione_prec or stagione_corrente(indietro=1)
    dati = {
        "stagione": stagione,
        "probabili": leggi_probabili(scarica("/probabili-formazioni-serie-a")),
        # A inizio stagione la pagina delle statistiche può non esserci ancora: si parte da zero.
        "stat": _facoltativo("Statistiche della stagione",
                             lambda: leggi_statistiche(scarica(f"/statistiche-serie-a/{stagione}", max_eta_min=360)), {}),
        "stat_prec": _facoltativo("Statistiche della stagione precedente", lambda: leggi_statistiche(
            scarica(f"/statistiche-serie-a/{stagione_prec}", max_eta_min=60 * 24 * 30)), {}),
        "rigoristi": _facoltativo("Rigoristi", lambda: leggi_rigoristi(scarica("/rigoristi-serie-a", max_eta_min=360)), {}),
        "listone": leggi_listone(scarica("/quotazioni-fantacalcio", max_eta_min=360)),
    }
    dati["sky"] = carica_sky(dati["probabili"]["giornata"], dati["listone"])
    return dati


if __name__ == "__main__":
    dati = carica_tutto()
    p = dati["probabili"]
    print("giornata", p["giornata"], "partite", len(p["partite"]), "giocatori", len(p["giocatori"]))
    print("stat", len(dati["stat"]), "stat_prec", len(dati["stat_prec"]))
    print(json.dumps(p["partite"][:3]))
