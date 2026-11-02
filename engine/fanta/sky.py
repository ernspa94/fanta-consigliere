"""Seconda fonte per chi gioca: probabili (o formazioni ufficiali) di Sky Sport.

Sky non dà percentuali ma dice titolari, riserve, in dubbio, squalificati e indisponibili, e
un'ora prima della partita pubblica le formazioni ufficiali. I nomi sono scritti in un altro modo
("Højlund R.", "Gustavo Varela"), quindi vanno abbinati agli id di Fantacalcio.it squadra per squadra.
"""

import difflib
import re
import unicodedata
import urllib.request

from bs4 import BeautifulSoup

URL = "https://sport.sky.it/calcio/serie-a/probabili-formazioni"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
LISTE = ["riserve", "dubbio", "squalificati", "indisponibili", "allenatore"]  # coppie casa/trasferta, in quest'ordine
SQUADRE_SKY = {"hellas verona": "verona"}  # nomi Sky diversi dallo slug di Fantacalcio.it
LETTERE = str.maketrans({"ø": "o", "Ø": "o", "æ": "ae", "ß": "ss", "đ": "d", "ł": "l", "ı": "i"})


def parole(testo):
    testo = unicodedata.normalize("NFKD", testo.translate(LETTERE)).encode("ascii", "ignore").decode().lower()
    return [p for p in re.split(r"[^a-z]+", testo) if p]


def scarica():
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _voce(a):
    """(nome come lo scrive Sky, parole del nome completo preso dal link della scheda)."""
    link = a.get("href", "").rstrip("/").split("/")
    nome = re.sub(r"^\d+", "", a.get_text(strip=True))  # nella pagina ufficiale c'è il numero di maglia davanti
    return nome, parole(link[-2]) if len(link) >= 2 else []


def leggi_ufficiali(html):
    """Formazioni ufficiali di una partita: [casa, trasferta], ognuna {titolari, riserve}."""
    soup = BeautifulSoup(html, "html.parser")
    squadre = []
    for corpo in soup.select("tbody.ftbl__report-tabs-panel__body"):
        sezioni, attuale = {"titolari": [], "riserve": []}, None
        for riga in corpo.select("tr"):
            intestazione = riga.select_one(".ftbl__report-tabs-panel__header-td")
            if intestazione:
                testo = intestazione.get_text(strip=True).lower()
                attuale = testo if testo in sezioni else None
                continue
            if attuale:
                sezioni[attuale] += [_voce(a) for a in riga.select("a[href*='/atleti/']")]
        if len(sezioni["titolari"]) >= 11:
            squadre.append(sezioni)
    return squadre[:2]


def scarica_ufficiali(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return leggi_ufficiali(r.read().decode("utf-8", errors="replace"))


def aggiungi_ufficiali(sky, scarica_pagina=scarica_ufficiali):
    """Dove Sky rimanda alle formazioni ufficiali, le usa al posto delle probabili."""
    pagine = {}
    for squadra, d in sky["squadre"].items():
        url = d.get("link_ufficiali")
        if not url:
            continue
        if url not in pagine:
            try:
                pagine[url] = scarica_pagina(url)
            except Exception as e:
                print(f"Formazioni ufficiali Sky non lette ({url}): {e}")
                pagine[url] = []
        squadre = pagine[url]
        if len(squadre) == 2 and len(squadre[d["lato"]]["titolari"]) == 11:
            d["titolari"] = squadre[d["lato"]]["titolari"]
            d["riserve"] = [nome for nome, _ in squadre[d["lato"]]["riserve"]]
            d["ufficiale"] = True
    return sky


def leggi(html):
    """{giornata, squadre: {slug: {titolari: [(nome, parole del link)], riserve, dubbio, ..., ufficiale}}}"""
    soup = BeautifulSoup(html, "html.parser")
    titolo = soup.select_one(".ftbl__predicted-lineups-hp__header h2")
    m = re.search(r"Giornata\s+(\d+)", titolo.get_text() if titolo else "")
    out = {"giornata": int(m.group(1)) if m else None, "squadre": {}}

    for blocco in soup.select("div.ftbl__predicted-lineups-hp[id]"):
        nomi = [t.get_text(" ", strip=True).lower() for t in blocco.select(".ftbl__team__name")][:2]
        if len(nomi) < 2:
            continue
        squadre = [SQUADRE_SKY.get(n, n.replace(" ", "-")) for n in nomi]
        # Attenzione: "Sono disponibili le formazioni ufficiali" è solo un rimando a un'altra pagina;
        # i nomi qui restano le probabili. Le ufficiali si leggono da quella pagina (leggi_ufficiali).
        rimando = next((a["href"] for a in blocco.select("a[href*='/formazioni']")
                        if "/partite/" in a["href"]), None)
        colonne = [c for c in blocco.select(".ftbl__report-tabs-panel__col")
                   if c.select("a.ftbl__match-formation-player--name")][:2]
        elenchi = blocco.select(".ftbl__report-tabs-panel__joined-array")
        for lato, squadra in enumerate(squadre):
            dati = {"ufficiale": False, "link_ufficiali": rimando, "lato": lato,
                    "titolari": [_voce(a) for a in colonne[lato].select("a.ftbl__match-formation-player--name")]
                    if lato < len(colonne) else []}
            for i, chiave in enumerate(LISTE):
                k = 2 * i + lato
                testo = elenchi[k].get_text(strip=True) if k < len(elenchi) else ""
                dati[chiave] = [n.strip() for n in testo.split(",") if n.strip() and n.strip() != "-"]
            out["squadre"][squadra] = dati
    return out


def _trova(nome, parole_link, candidati):
    """Il giocatore di Fantacalcio.it (tra quelli della squadra) che corrisponde al nome di Sky, o None."""
    dette = set(parole(nome)) | set(parole_link)
    migliori, top = [], 0.0
    for c in candidati:
        p = parole(c["nome"])
        cognome = [x for x in p if len(x) > 1]
        iniziali = [x for x in p if len(x) == 1]
        if not cognome:
            continue
        quota = sum(x in dette for x in cognome) / len(cognome)
        if quota < 0.5:
            continue
        # Iniziale del nome ("Martinez L." ↔ "lautaro-martinez") come spareggio tra omonimi.
        altre = [x for x in dette if x not in cognome]
        if iniziali and altre and not any(a[0] == iniziali[0] for a in altre):
            quota -= 0.4
        if quota > top + 1e-9:
            migliori, top = [c], quota
        elif abs(quota - top) < 1e-9:
            migliori.append(c)
    if len(migliori) == 1:
        return migliori[0]
    if migliori:
        return None  # omonimi: meglio non indovinare
    # Ultimo tentativo: nome tutto attaccato ("N'Dicka" ↔ "Ndicka") o con un piccolo refuso ("PellegrI").
    detto = "".join(parole(nome))
    simili = [(difflib.SequenceMatcher(None, "".join(parole(c["nome"])), detto).ratio(), c)
              for c in candidati]
    simili = sorted((s for s in simili if s[0] >= 0.85), key=lambda s: -s[0])
    if simili and (len(simili) == 1 or simili[0][0] - simili[1][0] > 0.05):
        return simili[0][1]
    return None


def abbina(sky, listone):
    """{id Fantacalcio.it: {"sky": titolare|dubbio|riserva|squalificato|indisponibile, "ufficiale": bool}}
    più l'elenco dei nomi non riconosciuti (per controllo)."""
    per_squadra = {}
    for g in listone:
        per_squadra.setdefault(g["squadra"], []).append(g)
    esito, sconosciuti = {}, []
    for squadra, d in sky["squadre"].items():
        candidati = per_squadra.get(squadra, [])
        voci = [(n, pl, "titolare") for n, pl in d["titolari"]]
        voci += [(n, [], tipo) for tipo, chiave in (("riserva", "riserve"), ("dubbio", "dubbio"),
                                                    ("squalificato", "squalificati"), ("indisponibile", "indisponibili"))
                 for n in d[chiave]]
        for nome, pl, tipo in voci:
            g = _trova(nome, pl, candidati)
            if g is None:
                sconosciuti.append(f"{nome} ({squadra})")
                continue
            prima = esito.get(g["id"], {}).get("sky")
            # Titolare e anche "in dubbio": vale il dubbio.
            if prima == "titolare" and tipo == "dubbio" or prima is None or tipo in ("squalificato", "indisponibile"):
                esito[g["id"]] = {"sky": tipo if not (prima == "titolare" and tipo == "dubbio") else "dubbio",
                                  "ufficiale": d["ufficiale"]}
    return esito, sconosciuti
