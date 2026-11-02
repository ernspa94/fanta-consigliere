from fanta.banco_prova import fantavoto_vero
from fanta.storico_voti import _voto


def test_voto_letto_dal_sito():
    assert _voto("6,5") == 6.5
    assert _voto("7") == 7.0
    assert _voto("55") is None  # Fantacalcio.it scrive 55 per "senza voto"
    assert _voto("") is None


def riga(**k):
    base = {"ruolo": "A", "voto": 6.0, "gol": 0, "rig_segnati": 0, "rig_sbagliati": 0, "rig_parati": 0,
            "gol_subiti": 0, "autogol": 0, "assist": 0, "potm": 0, "giallo": False, "rosso": False}
    return {**base, **k}


def test_fantavoto_vero_con_regole_della_lega():
    # gol su azione e su rigore valgono 3, assist 1, giallo -0.5
    assert fantavoto_vero(riga(voto=7.5, gol=1, rig_segnati=1, assist=1, giallo=True)) == 7.5 + 6 + 1 - 0.5
    # portiere: -1 a gol subito, +1 porta imbattuta, +3 rigore parato
    assert fantavoto_vero(riga(ruolo="P", voto=6.5, gol_subiti=2)) == 4.5
    assert fantavoto_vero(riga(ruolo="P", voto=6.5, rig_parati=1)) == 6.5 + 1 + 3
    # rigore sbagliato -3, autogol -2, MVP +0.5
    assert fantavoto_vero(riga(voto=5.0, rig_sbagliati=1, autogol=1, potm=1)) == 5.0 - 3 - 2 + 0.5
