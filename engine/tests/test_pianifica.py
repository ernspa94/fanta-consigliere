from datetime import datetime, timedelta, timezone

from fanta.pianifica import esegui

UTC = timezone.utc
POMERIGGIO = datetime(2026, 11, 19, 13, 53, tzinfo=UTC)  # minuto qualsiasi: GitHub non è puntuale
LONTANA = datetime(2026, 11, 21, 13, 59, tzinfo=UTC)


def test_di_giorno_ricalcola_se_l_ultimo_calcolo_e_vecchio():
    assert esegui(POMERIGGIO, LONTANA, ultimo_calcolo=POMERIGGIO - timedelta(hours=5))
    assert esegui(POMERIGGIO, LONTANA, ultimo_calcolo=None)


def test_di_giorno_non_ricalcola_se_e_recente():
    assert not esegui(POMERIGGIO, LONTANA, ultimo_calcolo=POMERIGGIO - timedelta(minutes=40))


def test_di_notte_aspetta():
    notte = datetime(2026, 11, 19, 2, 48, tzinfo=UTC)
    assert not esegui(notte, LONTANA, ultimo_calcolo=notte - timedelta(hours=9))


def test_vicino_alla_scadenza_e_con_richieste_ricalcola_sempre():
    vicina = POMERIGGIO + timedelta(hours=3)
    assert esegui(POMERIGGIO, vicina, ultimo_calcolo=POMERIGGIO - timedelta(minutes=10))
    assert esegui(POMERIGGIO, LONTANA, True, ultimo_calcolo=POMERIGGIO - timedelta(minutes=10))
