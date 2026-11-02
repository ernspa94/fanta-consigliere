"""Stima, per ogni giocatore della rosa, i parametri della prossima partita.

Il modello è volutamente semplice e trasparente:
- forza delle squadre da gol fatti/subiti (stagione in corso + scorsa, con peso decrescente);
- gol attesi della partita = attacco squadra × difesa avversaria × fattore campo;
- per il giocatore: media voto e frequenza di bonus/malus "ristrette" verso una media di ruolo,
  così chi ha poche presenze non viene sopravvalutato;
- probabilità di prendere voto dalle probabili formazioni di Fantacalcio.it.
"""

from collections import defaultdict

PESO_STAGIONE_PREC = 0.5   # una partita della scorsa stagione vale mezza partita di questa
PRIOR_PARTITE = 4          # "partite fittizie" di media di ruolo aggiunte a ogni giocatore
PRIOR_PARTITE_SQUADRA = 8  # idem per la forza delle squadre
FATTORE_CASA, FATTORE_TRASFERTA = 1.08, 0.92
AFFIDABILITA_TITOLARE = 0.94  # anche al 100% sulle probabili c'è qualche sorpresa

# Valori medi per ruolo, per partita a voto.
PRIOR = {
    "P": {"mv": 6.10, "gol": 0.0,   "ass": 0.005, "amm": 0.03, "esp": 0.005, "rig_err": 0.0,   "rp": 0.03},
    "D": {"mv": 5.95, "gol": 0.035, "ass": 0.05,  "amm": 0.20, "esp": 0.012, "rig_err": 0.0,   "rp": 0.0},
    "C": {"mv": 6.00, "gol": 0.07,  "ass": 0.09,  "amm": 0.18, "esp": 0.010, "rig_err": 0.005, "rp": 0.0},
    "A": {"mv": 6.00, "gol": 0.25,  "ass": 0.08,  "amm": 0.10, "esp": 0.008, "rig_err": 0.015, "rp": 0.0},
}
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

    squadre = set(fatti) | set(subiti)
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


def parametri_giocatori(rosa, dati):
    prob = dati["probabili"]
    partite_giocate = prob["giornata"] - 1
    forza, media = forza_squadre(dati["stat"], dati["stat_prec"], partite_giocate)
    ctx = contesto_partite(prob["partite"], forza, media)

    vuoto = {"pv": 0, "mv": 0, "gol": 0, "ass": 0, "amm": 0, "esp": 0, "rig_segnati": 0, "rig_tirati": 0, "rp": 0}
    out = []
    for g in rosa["giocatori"]:
        pid, ruolo = g["fc_id"], g["ruolo"]
        s1 = dati["stat"].get(pid, vuoto)
        s0 = dati["stat_prec"].get(pid, vuoto)
        pr = PRIOR[ruolo]
        info_prob = prob["giocatori"].get(pid)
        squadra = s1.get("squadra") or (info_prob or {}).get("squadra") or g["squadra"].lower()
        c = ctx.get(squadra)

        p = {
            "fc_id": pid, "nome": g["nome"], "ruolo": ruolo, "squadra": squadra,
            "stato": "ok", "nota": None, "lista": None,
        }

        # Probabilità di partire titolare e di entrare dalla panchina.
        presenze = s1["pv"] / partite_giocate if partite_giocate else 0.5
        ingresso = INGRESSO_DA_PANCHINA[ruolo] * min(1.0, max(0.3, presenze * 1.2))
        if c is None:
            p_tit, ingresso, p["stato"] = 0.0, 0.0, "non gioca"
        elif info_prob is None:
            p_tit, ingresso = 0.02, ingresso * 0.25
            p["stato"], p["nota"] = "non in lista", "non compare nelle probabili formazioni"
        elif info_prob["stato"] != "ok":
            p_tit, ingresso = 0.0, 0.0
            p["stato"], p["nota"] = info_prob["stato"], info_prob.get("nota")
        else:
            p_tit = info_prob["pct_titolare"] * AFFIDABILITA_TITOLARE
            p["lista"] = info_prob["lista"]
        p["p_titolare"] = p_tit
        p["p_ingresso"] = ingresso
        p["p_voto"] = p_tit * 0.97 + (1 - p_tit) * ingresso

        # Rendimento atteso.
        mv = _ristretto(s1["mv"], s1["pv"], s0["mv"], s0["pv"], pr["mv"])
        rig_err = lambda s: s["rig_tirati"] - s["rig_segnati"]
        tasso = lambda k, t1, t0: _tasso(t1, s1["pv"], t0, s0["pv"], pr[k])
        p.update({
            "mv": mv,
            "gol": tasso("gol", s1["gol"], s0["gol"]),
            "ass": tasso("ass", s1["ass"], s0["ass"]),
            "amm": tasso("amm", s1["amm"], s0["amm"]),
            "esp": tasso("esp", s1["esp"], s0["esp"]),
            "rig_err": tasso("rig_err", rig_err(s1), rig_err(s0)),
            "rp": tasso("rp", s1["rp"], s0["rp"]),
            "pv": s1["pv"], "fm": s1.get("fm", 0.0),
        })

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
                p["mv_partita"] = mv + 0.25 * (dif_media - c["gol_subiti"])
            else:
                p["mv_partita"] = mv + 0.10 * (c["gol_fatti"] - att_medio)
        else:
            p.update({"avversario": None, "casa": None, "gol_fatti_squadra": 0.0,
                      "gol_subiti_squadra": 0.0, "fattore_attacco": 1.0, "mv_partita": mv})
        out.append(p)
    return out, ctx
