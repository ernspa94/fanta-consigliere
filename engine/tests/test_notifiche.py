from datetime import datetime

from fanta.fonti import ROMA
from fanta.notifiche import messaggi


def g(nome, p_voto=0.94, stato="ok"):
    return {"nome": nome, "p_voto": p_voto, "stato": stato}


def consiglio(titolari, panchina=(), modulo="4-3-3", giornata=11, stato="pronto"):
    return {"stato": stato, "giornata": giornata, "modulo": modulo, "punti_attesi": 74.1,
            "scadenza": "2026-11-06T20:44:00+01:00",
            "titolari": [g(n) for n in titolari], "panchina": list(panchina)}


LUNEDI = datetime(2026, 11, 2, 12, 0, tzinfo=ROMA)
TIT = ["Meret", "Couto", "Dimarco"]


def test_nuova_giornata_pronta():
    attesa = {"stato": "in_attesa", "giornata": 11}
    out = messaggi(attesa, consiglio(TIT), {}, LUNEDI)
    assert [n["titolo"] for n in out] == ["Giornata 11: consiglio pronto"]


def test_niente_se_non_cambia_nulla():
    assert messaggi(consiglio(TIT), consiglio(TIT), {}, LUNEDI) == []


def test_cambio_formazione_spiega_chi_esce_e_perche():
    nuovo = consiglio(["Meret", "Couto", "Vojvoda"], panchina=[g("Dimarco", 0, "infortunato")])
    out = messaggi(consiglio(TIT), nuovo, {}, LUNEDI)
    assert len(out) == 1
    assert "Entra Vojvoda" in out[0]["testo"] and "esce Dimarco (infortunato)" in out[0]["testo"]


def test_promemoria_una_volta_sola_e_salta_quelli_superati():
    inviate = {}
    tre_ore_prima = datetime(2026, 11, 6, 18, 0, tzinfo=ROMA)
    assert [n["titolo"] for n in messaggi(consiglio(TIT), consiglio(TIT), inviate, tre_ore_prima)] \
        == ["Mancano 3 ore alla consegna"]
    assert messaggi(consiglio(TIT), consiglio(TIT), inviate, tre_ore_prima) == []
    venti_minuti_prima = datetime(2026, 11, 6, 20, 24, tzinfo=ROMA)
    assert [n["titolo"] for n in messaggi(consiglio(TIT), consiglio(TIT), inviate, venti_minuti_prima)] \
        == ["Mancano 30 minuti alla consegna"]
    assert inviate == {"11": ["30m", "3h"]}


def test_consiglio_pronto_a_ridosso_manda_solo_il_promemoria_piu_urgente():
    inviate = {}
    out = messaggi(None, consiglio(TIT), inviate, datetime(2026, 11, 6, 20, 30, tzinfo=ROMA))
    assert [n["titolo"] for n in out] == ["Giornata 11: consiglio pronto", "Mancano 30 minuti alla consegna"]
    assert inviate["11"] == ["30m", "3h"]


def test_nessuna_notifica_in_attesa():
    assert messaggi(consiglio(TIT), {"stato": "in_attesa", "giornata": 12}, {}, LUNEDI) == []
