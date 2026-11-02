"""Voti veri giornata per giornata (Redazione Fantacalcio), per misurare e tarare il modello.

Ogni riga è un giocatore in una partita: voto, bonus/malus, cartellini, subentrato o titolare.
"""

import json
import re
import time

from bs4 import BeautifulSoup

from .fonti import CACHE, _id_squadra, _numero, scarica

CARTELLA = CACHE.parent / "voti"


def _voto(testo):
    m = re.match(r"^\d+(?:[.,]\d+)?", (testo or "").strip())
    if not m:
        return None
    v = float(m.group(0).replace(",", "."))
    return v if v <= 10 else None  # il sito scrive 55 per "senza voto"


def leggi_voti(html, stagione, giornata):
    soup = BeautifulSoup(html, "html.parser")

    # Avversario e casa/trasferta dalle partite della giornata.
    avversario = {}
    for pill in soup.select(".match-pill"):
        casa = pill.select_one(".team-home a.team-name")
        fuori = pill.select_one(".team-away a.team-name")
        if casa and fuori:
            c, f = (a["href"].rstrip("/").split("/")[-1] for a in (casa, fuori))
            avversario[c] = (f, True)
            avversario[f] = (c, False)

    righe = []
    for tabella in soup.select("li.team-table"):
        for tr in tabella.select("tbody tr"):
            link = tr.select_one("a.player-link")
            if link is None:
                continue
            pid, squadra = _id_squadra(link)
            voto_el = tr.select_one(".pill .player-grade")  # la prima pillola è la Redazione Fantacalcio
            fv_el = tr.select_one(".pill .player-fanta-grade")
            voto = _voto(voto_el.get("data-value")) if voto_el else None
            bonus = {s["title"]: int(_numero(s.get("data-value", "0")))
                     for s in tr.select("span.player-bonus[title]")}
            icone = {i.get("title") for i in tr.select(".player-icon[title], .player-icon [title]")}
            avv, in_casa = avversario.get(squadra, (None, None))
            classi = voto_el.get("class", []) if voto_el else []
            righe.append({
                "stagione": stagione, "giornata": giornata, "id": pid,
                "nome": link.get_text(strip=True), "squadra": squadra,
                "ruolo": tr.select_one("span.role")["data-value"].upper(),
                "avversario": avv, "casa": in_casa,
                "voto": voto, "fv_redazione": _voto(fv_el.get("data-value")) if fv_el else None,
                "gol": bonus.get("Gol segnati", 0),  # esclusi i rigori
                "rig_segnati": bonus.get("Rigori segnati", 0),
                "rig_sbagliati": bonus.get("Rigori sbagliati", 0),
                "rig_parati": bonus.get("Rigori parati", 0),
                "gol_subiti": bonus.get("Gol subiti", 0),
                "autogol": bonus.get("Autoreti", 0),
                "assist": bonus.get("Assist", 0),
                "potm": bonus.get("Player of the match", 0),
                "giallo": "yellow-card" in classi,
                "rosso": "red-card" in classi,
                "subentrato": "Subentrato" in icone,
            })
    return righe


def scarica_stagione(stagione, giornate, pausa=0.5):
    """Voti di più giornate. Le giornate già scaricate restano in cache (30 giorni)."""
    righe = []
    for g in giornate:
        html = scarica(f"/voti-fantacalcio-serie-a/{stagione}/{g}", max_eta_min=60 * 24 * 30)
        righe += leggi_voti(html, stagione, g)
        time.sleep(pausa)
    return righe


def carica_stagione(stagione, fino_a=38):
    """Righe delle giornate 1..fino_a, salvate già lette in data/voti/<stagione>.json."""
    file = CARTELLA / f"{stagione}.json"
    righe = json.loads(file.read_text(encoding="utf-8")) if file.exists() else []
    presenti = {r["giornata"] for r in righe}
    mancanti = [g for g in range(1, fino_a + 1) if g not in presenti]
    if mancanti:
        righe += scarica_stagione(stagione, mancanti)
        CARTELLA.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(righe, ensure_ascii=False), encoding="utf-8")
    return [r for r in righe if r["giornata"] <= fino_a]


def statistiche(righe):
    """Stesse chiavi di fonti.leggi_statistiche, calcolate dalle righe (gol comprende i rigori)."""
    out = {}
    for r in sorted(righe, key=lambda r: (r["stagione"], r["giornata"])):
        if r["voto"] is None:
            continue
        s = out.setdefault(r["id"], {"nome": r["nome"], "ruolo": r["ruolo"], "pv": 0, "somma_voti": 0.0,
                                     "gol": 0, "gs": 0, "rig_segnati": 0, "rig_tirati": 0, "rp": 0,
                                     "ass": 0, "amm": 0, "esp": 0, "subentri": 0})
        s["squadra"] = r["squadra"]  # l'ultima squadra (conta per chi cambia a gennaio)
        s["pv"] += 1
        s["somma_voti"] += r["voto"]
        s["gol"] += r["gol"] + r["rig_segnati"]
        s["gs"] += r["gol_subiti"]
        s["rig_segnati"] += r["rig_segnati"]
        s["rig_tirati"] += r["rig_segnati"] + r["rig_sbagliati"]
        s["rp"] += r["rig_parati"]
        s["ass"] += r["assist"]
        s["amm"] += r["giallo"]
        s["esp"] += r["rosso"]
        s["subentri"] += r["subentrato"]
    for s in out.values():
        s["mv"] = s["somma_voti"] / s["pv"]
    return out
