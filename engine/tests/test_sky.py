from fanta.modello import AFFIDABILITA_TITOLARE as A, probabilita_titolare
from fanta.sky import _trova

LISTONE_NAPOLI = [
    {"id": 1, "nome": "Hojlund"}, {"id": 2, "nome": "Milinkovic-Savic V."}, {"id": 3, "nome": "Zambo Anguissa"},
    {"id": 4, "nome": "Marin R."}, {"id": 5, "nome": "Di Lorenzo"}, {"id": 6, "nome": "Martinez L."},
    {"id": 7, "nome": "Martinez J."}, {"id": 8, "nome": "N'Dicka"},
]


def trova(nome, link=""):
    g = _trova(nome, link.split("-") if link else [], LISTONE_NAPOLI)
    return g and g["id"]


def test_abbinamento_nomi_sky():
    assert trova("Højlund R.", "rasmus-hojlund") == 1           # lettere speciali
    assert trova("Anguissa A.", "frank-anguissa") == 3          # cognome composto, metà basta
    assert trova("Marín R.", "rafa-marin") == 4                 # accenti
    assert trova("Di Lorenzo G.", "giovanni-di-lorenzo") == 5
    assert trova("Lautaro Martinez", "lautaro-martinez") == 6   # omonimi: decide l'iniziale
    assert trova("Milinkovic-Savic") == 2                       # liste senza link (solo cognome)
    assert trova("Ndicka") == 8                                 # nome attaccato
    assert trova("Martinez") is None                            # omonimi senza iniziale: non indovina
    assert trova("Rossi") is None


FC_TITOLARE = {"stato": "ok", "pct_titolare": 1.0, "lista": "titolare"}
FC_BALLOTTAGGIO = {"stato": "ok", "pct_titolare": 0.55, "lista": "titolare"}
FC_INFORTUNATO = {"stato": "infortunato", "pct_titolare": 0.0, "lista": None, "nota": "out"}
SKY = lambda tipo, uff=False: {"sky": tipo, "ufficiale": uff}


def test_fonti_d_accordo_e_in_disaccordo():
    p, _, stato, nota = probabilita_titolare(FC_TITOLARE, SKY("titolare"), True)
    assert stato == "ok" and abs(p - (0.6 + 0.4 * 0.9) * A) < 1e-9 and nota is None
    p2, _, _, nota2 = probabilita_titolare(FC_TITOLARE, SKY("riserva"), True)
    assert p2 < p and "disaccordo" in nota2
    p3, _, _, _ = probabilita_titolare(FC_BALLOTTAGGIO, SKY("titolare"), True)
    assert 0.55 * A < p3 < p                                    # Sky scioglie il ballottaggio a favore


def test_infortunato_per_una_fonte_titolare_per_l_altra():
    p, ingresso, stato, _ = probabilita_titolare(FC_INFORTUNATO, SKY("titolare"), True)
    assert stato == "in dubbio" and 0 < p < 0.5 and ingresso == 0.5
    assert probabilita_titolare(FC_INFORTUNATO, SKY("indisponibile"), True)[:3] == (0.0, 0.0, "infortunato")
    assert probabilita_titolare(FC_TITOLARE, SKY("squalificato"), True)[2] == "in dubbio"


def test_formazione_ufficiale_decide():
    assert probabilita_titolare(FC_INFORTUNATO, SKY("titolare", True), True, True)[:3] == (0.99, 1.0, "ok")
    p, ingresso, stato, _ = probabilita_titolare(FC_TITOLARE, SKY("riserva", True), True, True)
    assert p == 0.0 and ingresso == 1.0 and stato == "ok"
    # Né titolare né in panchina nella formazione ufficiale: non gioca, anche se le probabili lo davano al 100%.
    assert probabilita_titolare(FC_TITOLARE, None, True, True)[:3] == (0.0, 0.0, "non convocato")


def test_senza_sky_resta_fantacalcio():
    assert probabilita_titolare(FC_BALLOTTAGGIO, None, False)[0] == 0.55 * A
    assert probabilita_titolare(None, None, False)[2] == "non in lista"


def test_archivio_probabili_tiene_prima_e_ultima(tmp_path, monkeypatch):
    from fanta import storico_probabili as SP
    monkeypatch.setattr(SP, "CARTELLA", tmp_path)
    dati = lambda pct: {"probabili": {"giocatori": {1: {"squadra": "napoli", "pct_titolare": pct, "stato": "ok",
                                                        "lista": "titolare"}}},
                        "sky": {"giocatori": {1: {"sky": "titolare", "ufficiale": False}}, "squadre": {"napoli": False}}}
    assert SP.salva(dati(0.55), 11)
    assert not SP.salva(dati(0.55), 11)          # niente di nuovo: non riscrive
    assert SP.salva(dati(1.0), 11)
    f = SP.carica()[11]
    assert f["primo"]["dati"]["giocatori"]["1"]["fc"] == 0.55
    assert f["ultimo"]["dati"]["giocatori"]["1"] == {"squadra": "napoli", "fc": 1.0, "lista": "titolare",
                                                     "sky": "titolare", "uff": False}
