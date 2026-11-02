from fanta.consiglia import REGOLE_STANDARD, cambiato, regole_complete, rosa_incompleta


def test_regole_mancanti_prendono_lo_standard():
    r = regole_complete({"bonus_malus": {"gol": {"A": 4.0}}, "moduli": ["4-4-2"]})
    assert r["bonus_malus"]["gol"] == {**REGOLE_STANDARD["bonus_malus"]["gol"], "A": 4.0}
    assert r["bonus_malus"]["assist"] == REGOLE_STANDARD["bonus_malus"]["assist"]
    assert r["moduli"] == ["4-4-2"]  # le liste si sostituiscono, non si uniscono
    assert r["modificatore_difesa"] == REGOLE_STANDARD["modificatore_difesa"]


def test_rosa_incompleta():
    g = lambda r: {"ruolo": r}
    assert rosa_incompleta([g("P")] + [g("D")] * 4 + [g("C")] * 4 + [g("A")] * 2) is None
    assert "mancano 1 portiere" in rosa_incompleta([g("D")] * 4 + [g("C")] * 4 + [g("A")] * 3)
    assert "almeno 11" in rosa_incompleta([g("P")] + [g("D")] * 3 + [g("C")] * 3 + [g("A")])


def test_cambiato_ignora_l_orario():
    a = {"aggiornato": "2026-11-02T10:00", "giornata": 11, "stato": "in_attesa"}
    assert not cambiato(a, {**a, "aggiornato": "2026-11-02T12:00"})
    assert cambiato(a, {**a, "stato": "pronto"})
    assert cambiato(None, a)
