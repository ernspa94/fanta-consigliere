"""Dove stanno squadre e consigli: Supabase (con la chiave service_role) o, in locale, i file in config/.

Solo libreria standard: lo usa anche pianifica.py, prima che il workflow installi le dipendenze.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Supabase:
    def __init__(self, url, chiave):
        self.base = url.rstrip("/") + "/rest/v1/"
        self.intestazioni = {"apikey": chiave, "Authorization": f"Bearer {chiave}",
                             "Content-Type": "application/json"}

    def _richiesta(self, metodo, percorso, corpo=None, prefer=None):
        intest = dict(self.intestazioni)
        if prefer:
            intest["Prefer"] = prefer
        dati = json.dumps(corpo).encode() if corpo is not None else None
        req = urllib.request.Request(self.base + percorso, data=dati, method=metodo, headers=intest)
        with urllib.request.urlopen(req, timeout=30) as r:
            testo = r.read().decode()
        return json.loads(testo) if testo else None

    def squadre(self, codici=None, solo_da_ricalcolare=False):
        filtro = "select=codice,nome,lega,rosa,regole,notifiche_inviate,ricalcolo_richiesto"
        if codici:
            filtro += "&codice=in.(" + ",".join(urllib.parse.quote(c) for c in codici) + ")"
        if solo_da_ricalcolare:
            filtro += "&ricalcolo_richiesto=not.is.null"
        return self._richiesta("GET", "squadre?" + filtro)

    def ultimo_consiglio(self, codice):
        righe = self._richiesta("GET", f"consigli?codice=eq.{urllib.parse.quote(codice)}"
                                       "&select=dati&order=giornata.desc&limit=1")
        return righe[0]["dati"] if righe else None

    def salva_consiglio(self, codice, consiglio):
        # Nella colonna "giornata" va la chiave stagione+giornata (202611): così le stagioni non si mescolano.
        self._richiesta("POST", "consigli?on_conflict=codice,giornata",
                        [{"codice": codice, "giornata": consiglio.get("chiave") or consiglio["giornata"],
                          "dati": consiglio, "aggiornato": consiglio["aggiornato"]}],
                        prefer="resolution=merge-duplicates")

    def prepara(self):
        """Una volta sola: i primi consigli (2026-27) erano salvati con il solo numero di giornata."""
        vecchi = self._richiesta("GET", "consigli?giornata=lt.1000&select=codice,giornata,dati,aggiornato")
        for r in vecchi:
            chiave = 2026 * 100 + r["giornata"]
            dati = {**r["dati"], "stagione": "2026-27", "chiave": chiave}
            self._richiesta("POST", "consigli?on_conflict=codice,giornata",
                            [{"codice": r["codice"], "giornata": chiave, "dati": dati, "aggiornato": r["aggiornato"]}],
                            prefer="resolution=merge-duplicates")
            self._richiesta("DELETE", f"consigli?codice=eq.{urllib.parse.quote(r['codice'])}&giornata=eq.{r['giornata']}")
        if vecchi:
            print(f"Convertiti {len(vecchi)} consigli al nuovo formato (stagione+giornata)")

    def aggiorna_squadra(self, codice, campi):
        self._richiesta("PATCH", f"squadre?codice=eq.{urllib.parse.quote(codice)}", campi)

    def iscrizioni(self, codice):
        return self._richiesta("GET", f"iscrizioni?codice=eq.{urllib.parse.quote(codice)}&select=nome,iscrizione,endpoint")

    def rimuovi_iscrizione(self, codice, endpoint):
        self._richiesta("DELETE", f"iscrizioni?codice=eq.{urllib.parse.quote(codice)}"
                                  f"&endpoint=eq.{urllib.parse.quote(endpoint, safe='')}")


class Locale:
    """Una sola squadra dai file config/rosa.json e config/regole/fanta-lignano.json; il consiglio va in output/."""

    codice = "locale"

    def squadre(self, codici=None, solo_da_ricalcolare=False):
        if solo_da_ricalcolare:
            return []
        rosa = json.loads((ROOT / "config" / "rosa.json").read_text(encoding="utf-8"))
        regole = json.loads((ROOT / "config" / "regole" / "fanta-lignano.json").read_text(encoding="utf-8"))
        file_inviate = ROOT / "output" / "notifiche_inviate.json"
        inviate = json.loads(file_inviate.read_text(encoding="utf-8")) if file_inviate.exists() else {}
        giocatori = [{"fc_id": g.get("fc_id"), "nome": g["nome"], "ruolo": g["ruolo"], "squadra": g["squadra"]}
                     for g in rosa["giocatori"]]
        return [{"codice": self.codice, "nome": rosa["squadra"], "lega": rosa.get("lega"), "rosa": giocatori,
                 "regole": regole, "notifiche_inviate": inviate, "ricalcolo_richiesto": None}]

    def prepara(self):
        pass

    def ultimo_consiglio(self, codice):
        file = ROOT / "output" / "consiglio.json"
        return json.loads(file.read_text(encoding="utf-8")) if file.exists() else None

    def salva_consiglio(self, codice, consiglio):
        out = ROOT / "output"
        (out / "storico").mkdir(parents=True, exist_ok=True)
        testo = json.dumps(consiglio, ensure_ascii=False, indent=2)
        (out / "consiglio.json").write_text(testo, encoding="utf-8")
        if consiglio["stato"] == "pronto":
            (out / "storico" / f"giornata-{consiglio['giornata']:02d}.json").write_text(testo, encoding="utf-8")
        giornate = sorted(int(f.stem.split("-")[1]) for f in (out / "storico").glob("giornata-*.json"))
        (out / "storico" / "indice.json").write_text(json.dumps({"giornate": giornate}), encoding="utf-8")

    def aggiorna_squadra(self, codice, campi):
        if "notifiche_inviate" in campi:
            (ROOT / "output" / "notifiche_inviate.json").write_text(
                json.dumps(campi["notifiche_inviate"], indent=2) + "\n", encoding="utf-8")

    def iscrizioni(self, codice):
        return json.loads(os.environ.get("PUSH_ISCRIZIONI") or "[]")

    def rimuovi_iscrizione(self, codice, endpoint):
        pass


def da_ambiente():
    url, chiave = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    return Supabase(url, chiave) if url and chiave else Locale()
