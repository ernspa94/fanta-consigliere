"""Stima, per ogni giocatore della rosa, i parametri della prossima partita.

Il modello è volutamente semplice e trasparente:
- forza delle squadre da gol fatti/subiti (stagione in corso + scorsa, con peso decrescente);
- gol attesi della partita = attacco squadra × difesa avversaria × fattore campo;
- per il giocatore: media voto e frequenza di bonus/malus "ristrette" verso una media di ruolo,
  così chi ha poche presenze non viene sopravvalutato;
- probabilità di prendere voto dalle probabili formazioni di Fantacalcio.it.
"""

import math
from collections import defaultdict

PESO_STAGIONE_PREC = 0.35  # una partita della scorsa stagione vale un terzo di una di questa
PRIOR_PARTITE = 10         # "partite fittizie" di media di ruolo aggiunte a ogni giocatore
PRIOR_PARTITE_SQUADRA = 8  # idem per la forza delle squadre
# Valori tarati con banco_prova.py sui voti veri 2025-26 e verificati sul 2026-27.
FATTORE_CASA, FATTORE_TRASFERTA = 1.08, 0.92
AFFIDABILITA_TITOLARE = 0.94  # anche al 100% sulle probabili c'è qualche sorpresa
# Quanto la difficoltà della partita sposta il voto in pagella (per gol attesi di differenza).
COEF_VOTO_DIFESA, COEF_VOTO_ATTACCO = 0.25, 0.35

# Valori medi per ruolo, per partita a voto.
PRIOR = {
    "P": {"mv": 6.10, "gol": 0.0,   "ass": 0.005, "amm": 0.03, "esp": 0.005, "rig_err": 0.0,   "rp": 0.03},
    "D": {"mv": 5.95, "gol": 0.035, "ass": 0.05,  "amm": 0.20, "esp": 0.012, "rig_err": 0.0,   "rp": 0.0},
    "C": {"mv": 6.00, "gol": 0.07,  "ass": 0.09,  "amm": 0.18, "esp": 0.010, "rig_err": 0.005, "rp": 0.0},
    "A": {"mv": 6.00, "gol": 0.25,  "ass": 0.08,  "amm": 0.10, "esp": 0.008, "rig_err": 0.015, "rp": 0.0},
}
# Gol su azione (rigori esclusi) per partita a voto: i rigori si stimano a parte.
PRIOR_GOL_AZIONE = {"P": 0.0, "D": 0.03, "C": 0.06, "A": 0.21}
USA_RIGORISTI = True
QUOTA_RIGORI = (0.85, 0.10, 0.05)  # quanti rigori della squadra tira il 1°, 2°, 3° rigorista
CONVERSIONE_RIGORI = 0.78           # media di Serie A
PRIOR_PARTITE_RIGORI = 15
# Seconda fonte (Sky Sport): probabilità di partire titolare per ciascuna voce e peso di Fantacalcio.it.
P_SKY = {"titolare": 0.9, "dubbio": 0.55, "riserva": 0.08}
P_SKY_NON_IN_LISTA = 0.05
PESO_FANTACALCIO = 0.6  # ha le percentuali, Sky solo titolare/riserva
# Probabilità di entrare dalla panchina (e prendere voto) se non si parte titolari.
INGRESSO_DA_PANCHINA = {"P": 0.01, "D": 0.25, "C": 0.40, "A": 0.45}


def forza_squadre(stat, stat_prec, partite_giocate):
    """Gol fatti e subiti attesi per partita, per squadra."""
    fatti, subiti = defaultdict(float), defaultdict(float)
    fatti_prec, subiti_prec = defaultdict(float), defaultdict(float)
    for s, f, sub in ((stat, fatti, subiti), (stat_prec, fatti_prec, subiti_prec)):
        for g in s.values():
            f[g["squadra"]] += g["gol"]
            if g["ruolo"] == "P":
                sub[g["squadra"]] += g["gs"]

    squadre = (set(fatti) | set(subiti)) or (set(fatti_prec) | set(subiti_prec))  # pre-campionato: squadre dell'anno prima
    media_prec = sum(fatti_prec.values()) / max(len(fatti_prec), 1) / 38
    forza = {}
    for sq in squadre:
        # Neopromosse: senza storico in A, partono un po' sotto la media.
        att_prec = fatti_prec[sq] / 38 if sq in fatti_prec else media_prec * 0.85
        dif_prec = subiti_prec[sq] / 38 if sq in subiti_prec else media_prec * 1.15
        k = PRIOR_PARTITE_SQUADRA
        forza[sq] = {
            "attacco": (fatti[sq] + att_prec * k) / (partite_giocate + k),
            "difesa": (subiti[sq] + dif_prec * k) / (partite_giocate + k),
        }
    media = sum(f["attacco"] for f in forza.values()) / len(forza)
    return forza, media


def contesto_partite(partite, forza, media):
    """Per ogni squadra in campo: avversario, casa/trasferta, gol attesi fatti e subiti."""
    ctx = {}
    for p in partite:
        c, t = p["casa"], p["trasferta"]
        lam_c = forza[c]["attacco"] * forza[t]["difesa"] / media * FATTORE_CASA
        lam_t = forza[t]["attacco"] * forza[c]["difesa"] / media * FATTORE_TRASFERTA
        ctx[c] = {"avversario": t, "casa": True, "gol_fatti": lam_c, "gol_subiti": lam_t}
        ctx[t] = {"avversario": c, "casa": False, "gol_fatti": lam_t, "gol_subiti": lam_c}
    return ctx


def _ristretto(valore_corr, pv_corr, valore_prec, pv_prec, prior):
    peso_prec = PESO_STAGIONE_PREC * pv_prec
    return (valore_corr * pv_corr + valore_prec * peso_prec + prior * PRIOR_PARTITE) / (
        pv_corr + peso_prec + PRIOR_PARTITE)


def _tasso(totale_corr, pv_corr, totale_prec, pv_prec, prior):
    return (totale_corr + PESO_STAGIONE_PREC * totale_prec + prior * PRIOR_PARTITE) / (
        pv_corr + PESO_STAGIONE_PREC * pv_prec + PRIOR_PARTITE)


def probabilita_titolare(prob, sky, sky_copre_la_squadra, ufficiale_squadra=False):
    """Probabilità di partire titolare dalle due fonti.

    prob: voce delle probabili di Fantacalcio.it (con % di titolarità) o None;
    sky: {"sky": titolare|dubbio|riserva|squalificato|indisponibile, "ufficiale": bool} o None.
    Ritorna (probabilità titolare, quota della probabilità di entrare dalla panchina, stato, nota).
    """
    fuori_fc = prob is not None and prob["stato"] != "ok"
    fuori_sky = sky is not None and sky["sky"] in ("squalificato", "indisponibile")
    nota_fc = (prob or {}).get("nota")

    if ufficiale_squadra or (sky and sky["ufficiale"]):  # formazioni ufficiali: decidono loro
        if sky and sky["sky"] in ("titolare", "dubbio"):
            return 0.99, 1.0, "ok", "titolare nella formazione ufficiale"
        if fuori_fc or fuori_sky:
            return 0.0, 0.0, prob["stato"] if fuori_fc else sky["sky"], nota_fc
        if sky and sky["sky"] == "riserva":
            return 0.0, 1.0, "ok", "in panchina nella formazione ufficiale"
        return 0.0, 0.0, "non convocato", "non è nella formazione ufficiale"

    if fuori_fc and fuori_sky:
        return 0.0, 0.0, prob["stato"], nota_fc
    if fuori_fc or fuori_sky:
        stato = prob["stato"] if fuori_fc else sky["sky"]
        altra_lo_da_titolare = (sky or {}).get("sky") == "titolare" if fuori_fc else (prob or {}).get("lista") == "titolare"
        if altra_lo_da_titolare:
            fonte = "Fantacalcio.it" if fuori_fc else "Sky"
            return 0.3 * AFFIDABILITA_TITOLARE, 0.5, "in dubbio", f"{stato} per {fonte}, titolare per l'altra fonte" + (
                f" ({nota_fc})" if nota_fc else "")
        return 0.0, 0.0, stato, nota_fc

    p_fc = prob["pct_titolare"] if prob else None
    p_sky = P_SKY[sky["sky"]] if sky else (P_SKY_NON_IN_LISTA if sky_copre_la_squadra else None)
    if p_fc is None and p_sky is None:
        return 0.02, 0.25, "non in lista", "non compare nelle probabili formazioni"
    if p_fc is None:
        p = p_sky
    elif p_sky is None:
        p = p_fc
    else:
        p = PESO_FANTACALCIO * p_fc + (1 - PESO_FANTACALCIO) * p_sky
    nota = None
    if p_fc is not None and p_sky is not None and abs(p_fc - p_sky) >= 0.5:
        nota = f"fonti in disaccordo: Fantacalcio.it {round(p_fc * 100)}%, Sky {sky['sky'] if sky else 'non lo cita'}"
    return p * AFFIDABILITA_TITOLARE, 1.0 if p_fc is not None or sky else 0.25, "ok", nota


def rigoristi_dalle_statistiche(stat, stat_prec):
    """Senza la lista di Fantacalcio.it: per ogni squadra, chi ha tirato più rigori finora."""
    punteggio = defaultdict(dict)
    for pid, s in stat.items():
        if s["rig_tirati"]:
            punteggio[s["squadra"]][pid] = s["rig_tirati"]
    for pid, s in stat_prec.items():
        sq = stat.get(pid, s)["squadra"]  # conta solo se è ancora nella stessa squadra
        if s["rig_tirati"] and sq == s["squadra"]:
            punteggio[sq][pid] = punteggio[sq].get(pid, 0) + PESO_STAGIONE_PREC * s["rig_tirati"]
    return {sq: sorted(p, key=lambda pid: -p[pid]) for sq, p in punteggio.items()}


def rigoristi_in_campo(ordine, probabili):
    """Toglie dalla lista i rigoristi che non dovrebbero giocare: i rigori passano al successivo."""
    def gioca(pid):
        info = probabili.get(pid)
        return info is not None and info.get("stato") == "ok" and info.get("pct_titolare", 0) >= 0.5
    in_campo = [pid for pid in ordine if gioca(pid)]
    return in_campo or ordine


def rigori_per_partita(stat, stat_prec, partite_giocate):
    """Rigori tirati per partita da ogni squadra (ristretti verso la media del campionato)."""
    tiri, tiri_prec = defaultdict(float), 0.0
    for s in stat.values():
        tiri[s["squadra"]] += s["rig_tirati"]
    for s in stat_prec.values():
        tiri_prec += s["rig_tirati"]
    squadre = max(len(tiri), 20)
    media = (sum(tiri.values()) + tiri_prec) / (squadre * (partite_giocate + 38))
    k = PRIOR_PARTITE_RIGORI
    return {sq: (t + media * k) / (partite_giocate + k) for sq, t in tiri.items()}, media


def fantavoto_atteso(p, bm):
    """Fantavoto medio previsto se il giocatore parte titolare (stesse ipotesi della simulazione)."""
    r, fa = p["ruolo"], p["fattore_attacco"]
    fv = p["mv_partita"] + bm["gol"][r] * p["gol"] * fa + bm["assist"][r] * p["ass"] * fa \
        + bm["ammonizione"][r] * p["amm"] + bm["espulsione"][r] * p["esp"] \
        + bm["rigore_sbagliato"][r] * p["rig_err"]
    if r == "P" and p.get("avversario"):
        lam = p["gol_subiti_squadra"]
        fv += bm["gol_subito"][r] * lam + bm["porta_imbattuta"][r] * math.exp(-lam) \
            + bm["rigore_parato"][r] * p["rp"]
    return fv


def parametri_giocatori(rosa, dati):
    prob = dati["probabili"]
    partite_giocate = prob["giornata"] - 1
    forza, media = forza_squadre(dati["stat"], dati["stat_prec"], partite_giocate)
    ctx = contesto_partite(prob["partite"], forza, media)

    sky = dati.get("sky") or {"giocatori": {}, "squadre": {}}
    rigoristi = dati.get("rigoristi") or rigoristi_dalle_statistiche(dati["stat"], dati["stat_prec"])
    rigori_squadra, rigori_medi = rigori_per_partita(dati["stat"], dati["stat_prec"], partite_giocate)

    vuoto = {"pv": 0, "mv": 0, "gol": 0, "ass": 0, "amm": 0, "esp": 0, "rig_segnati": 0, "rig_tirati": 0, "rp": 0}
    out = []
    for g in rosa["giocatori"]:
        pid, ruolo = g["fc_id"], g["ruolo"]
        s1 = dati["stat"].get(pid, vuoto)
        s0 = dati["stat_prec"].get(pid, vuoto)
        pr = PRIOR[ruolo]
        info_prob = prob["giocatori"].get(pid)
        # Le probabili hanno la squadra attuale (conta per chi è stato ceduto a gennaio).
        squadra = (info_prob or {}).get("squadra") or s1.get("squadra") or g["squadra"].lower()
        c = ctx.get(squadra)

        p = {
            "fc_id": pid, "nome": g["nome"], "ruolo": ruolo, "squadra": squadra,
            "stato": "ok", "nota": None, "lista": None,
        }

        # Probabilità di partire titolare e di entrare dalla panchina.
        presenze = s1["pv"] / partite_giocate if partite_giocate else 0.5
        ingresso = INGRESSO_DA_PANCHINA[ruolo] * min(1.0, max(0.3, presenze * 1.2))
        info_sky = sky["giocatori"].get(pid)
        p["fonti"] = {"fantacalcio": None if info_prob is None else
                      (info_prob["pct_titolare"] if info_prob["stato"] == "ok" else info_prob["stato"]),
                      "sky": info_sky["sky"] if info_sky else None,
                      "ufficiale": bool(info_sky and info_sky["ufficiale"])}
        if c is None:
            p_tit, ingresso, p["stato"] = 0.0, 0.0, "non gioca"
        else:
            p_tit, quota_ingresso, p["stato"], p["nota"] = probabilita_titolare(
                info_prob, info_sky, squadra in sky["squadre"], bool(sky["squadre"].get(squadra)))
            ingresso *= quota_ingresso
            p["lista"] = (info_prob or {}).get("lista")
        p["p_titolare"] = p_tit
        p["p_ingresso"] = ingresso
        p["p_voto"] = p_tit * 0.97 + (1 - p_tit) * ingresso

        # Rendimento atteso.
        mv = _ristretto(s1["mv"], s1["pv"], s0["mv"], s0["pv"], pr["mv"])
        tasso = lambda k, t1, t0: _tasso(t1, s1["pv"], t0, s0["pv"], pr[k])
        p.update({
            "mv": mv,
            "ass": tasso("ass", s1["ass"], s0["ass"]),
            "amm": tasso("amm", s1["amm"], s0["amm"]),
            "esp": tasso("esp", s1["esp"], s0["esp"]),
            "rp": tasso("rp", s1["rp"], s0["rp"]),
            "pv": s1["pv"], "fm": s1.get("fm", 0.0),
        })
        if USA_RIGORISTI:
            # Gol su azione dallo storico; i rigori dipendono da quanti ne ha la squadra e da chi li tira.
            gol_azione = _tasso(s1["gol"] - s1["rig_segnati"], s1["pv"], s0["gol"] - s0["rig_segnati"],
                                s0["pv"], PRIOR_GOL_AZIONE[ruolo])
            ordine = rigoristi_in_campo(rigoristi.get(squadra, []), prob["giocatori"])
            quota = QUOTA_RIGORI[ordine.index(pid)] if pid in ordine[:len(QUOTA_RIGORI)] else 0.0
            tiri = quota * rigori_squadra.get(squadra, rigori_medi)
            segnati = s1["rig_segnati"] + PESO_STAGIONE_PREC * s0["rig_segnati"]
            tirati = s1["rig_tirati"] + PESO_STAGIONE_PREC * s0["rig_tirati"]
            conv = (segnati + CONVERSIONE_RIGORI * 5) / (tirati + 5)
            p.update({"gol": gol_azione + tiri * conv, "rig_err": tiri * (1 - conv),
                      "rigorista": ordine.index(pid) + 1 if pid in ordine else None})
        else:
            rig_err = lambda s: s["rig_tirati"] - s["rig_segnati"]
            p.update({"gol": tasso("gol", s1["gol"], s0["gol"]),
                      "rig_err": tasso("rig_err", rig_err(s1), rig_err(s0)), "rigorista": None})

        if c:
            att_medio = forza[squadra]["attacco"]
            dif_media = forza[squadra]["difesa"]
            p.update({
                "avversario": c["avversario"], "casa": c["casa"],
                "gol_fatti_squadra": c["gol_fatti"], "gol_subiti_squadra": c["gol_subiti"],
                # >1 se la partita è più facile del solito per l'attacco della squadra
                "fattore_attacco": min(1.8, max(0.5, c["gol_fatti"] / att_medio)),
            })
            # Voto in pagella un po' più alto/basso in base alla difficoltà della partita.
            if ruolo in ("P", "D"):
                p["mv_partita"] = mv + COEF_VOTO_DIFESA * (dif_media - c["gol_subiti"])
            else:
                p["mv_partita"] = mv + COEF_VOTO_ATTACCO * (c["gol_fatti"] - att_medio)
        else:
            p.update({"avversario": None, "casa": None, "gol_fatti_squadra": 0.0,
                      "gol_subiti_squadra": 0.0, "fattore_attacco": 1.0, "mv_partita": mv})
        out.append(p)
    return out, ctx
