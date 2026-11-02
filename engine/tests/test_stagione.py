from datetime import datetime

from fanta import consiglia, fonti
from fanta.fonti import ROMA, chiave_giornata, stagione_corrente, stagione_dopo


def test_stagione_dalla_data():
    assert stagione_corrente(datetime(2026, 11, 2, tzinfo=ROMA)) == "2026-27"
    assert stagione_corrente(datetime(2027, 5, 30, tzinfo=ROMA)) == "2026-27"
    assert stagione_corrente(datetime(2027, 7, 1, tzinfo=ROMA)) == "2027-28"
    assert stagione_corrente(datetime(2026, 11, 2, tzinfo=ROMA), indietro=1) == "2025-26"
    assert stagione_corrente(datetime(2099, 8, 1, tzinfo=ROMA)) == "2099-00"
    assert stagione_dopo("2026-27") == "2027-28"
    assert chiave_giornata("2026-27", 11) == 202611


def stato(monkeypatch, giornata, stagione_pagina, adesso, inizio=None):
    monkeypatch.setattr(fonti, "inizio_giornata", lambda g, st=None: inizio if g == giornata else None)
    dati = {"stagione": stagione_corrente(adesso),
            "probabili": {"giornata": giornata, "stagione": stagione_pagina}}
    return consiglia.stato_giornata(dati, adesso)


def test_giornata_normale(monkeypatch):
    adesso = datetime(2026, 11, 2, 12, tzinfo=ROMA)
    s = stato(monkeypatch, 11, "2026-27", adesso, inizio=datetime(2026, 11, 6, 20, 45, tzinfo=ROMA))
    assert (s["giornata"], s["pronta"], s["stagione"]) == (11, True, "2026-27")


def test_giornata_iniziata_aspetta_la_prossima(monkeypatch):
    adesso = datetime(2026, 11, 8, 12, tzinfo=ROMA)
    s = stato(monkeypatch, 11, "2026-27", adesso, inizio=datetime(2026, 11, 6, 20, 45, tzinfo=ROMA))
    assert (s["giornata"], s["pronta"]) == (12, False)


def test_dopo_la_38a_aspetta_la_prima_della_stagione_dopo(monkeypatch):
    adesso = datetime(2027, 6, 10, 12, tzinfo=ROMA)
    s = stato(monkeypatch, 38, "2026-27", adesso, inizio=datetime(2027, 5, 30, 18, tzinfo=ROMA))
    assert (s["giornata"], s["pronta"], s["stagione"]) == (1, False, "2027-28")


def test_d_estate_la_pagina_della_stagione_vecchia_non_conta(monkeypatch):
    adesso = datetime(2027, 8, 1, 12, tzinfo=ROMA)
    s = stato(monkeypatch, 38, "2026-27", adesso, inizio=datetime(2027, 5, 30, 18, tzinfo=ROMA))
    assert (s["giornata"], s["pronta"], s["stagione"]) == (1, False, "2027-28")


def test_pagina_senza_giornata(monkeypatch):
    s = stato(monkeypatch, None, None, datetime(2027, 7, 20, 12, tzinfo=ROMA))
    assert (s["giornata"], s["pronta"], s["stagione"], s["inizio"]) == (1, False, "2027-28", None)


def test_nuova_stagione_pronta(monkeypatch):
    adesso = datetime(2027, 8, 18, 12, tzinfo=ROMA)
    s = stato(monkeypatch, 1, "2027-28", adesso, inizio=datetime(2027, 8, 21, 18, 30, tzinfo=ROMA))
    assert (s["giornata"], s["pronta"], s["stagione"]) == (1, True, "2027-28")
