"""Guida PDF di Fanta Consigliere (copertina, fasce dei capitoli, schermate in cornice da telefono).

Uso:  ../../.venv/bin/python crea_guida.py ../../app/guida.pdf   (dalla cartella docs/guida/)
Le schermate stanno in schermate/ (catturate dall'app a 375×812, tema chiaro). Se l'app cambia aspetto,
vanno rifatte e i ritagli (alto/basso in pixel) nelle chiamate Telefono(...) ricontrollati.
Serve reportlab e pillow:  pip install reportlab pillow
"""
import sys
import tempfile
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

QUI = Path(__file__).parent
IMG = QUI / "schermate"
USCITA = Path(sys.argv[1])
ICONA = str(QUI.parents[1] / "app" / "icons" / "icon-512.png")
LARGH, ALT = A4

F = "/System/Library/Fonts/Supplemental/"
pdfmetrics.registerFont(TTFont("Arial", F + "Arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-B", F + "Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Arial-I", F + "Arial Italic.ttf"))
pdfmetrics.registerFont(TTFont("Tondo", F + "Arial Rounded Bold.ttf"))
addMapping("Arial", 0, 0, "Arial"); addMapping("Arial", 1, 0, "Arial-B"); addMapping("Arial", 0, 1, "Arial-I")

SCURO = colors.HexColor("#0a3a28")
VERDE = colors.HexColor("#0b5d3b")
VERDE_2 = colors.HexColor("#14864f")
VERDE_CHIARO = colors.HexColor("#e9f3ed")
ORO = colors.HexColor("#f2b705")
ORO_CHIARO = colors.HexColor("#fdf5dc")
TESTO = colors.HexColor("#10201a")
GRIGIO = colors.HexColor("#63716b")
BORDO = colors.HexColor("#e2e8e4")
RUOLI = {"P": "#e0a31a", "D": "#2f9e5b", "C": "#2f7fd1", "A": "#e0483d"}

testo = ParagraphStyle("testo", fontName="Arial", fontSize=11.2, leading=15.8, textColor=TESTO, spaceAfter=6)
piccolo = ParagraphStyle("piccolo", parent=testo, fontSize=10, leading=13.5, textColor=GRIGIO)
sottotitolo = ParagraphStyle("sottotitolo", fontName="Tondo", fontSize=13, leading=17, textColor=VERDE,
                             spaceBefore=8, spaceAfter=4)
punto = ParagraphStyle("punto", parent=testo, leftIndent=14, bulletIndent=2, bulletColor=VERDE_2)
domanda = ParagraphStyle("domanda", fontName="Tondo", fontSize=12, leading=16, textColor=VERDE, spaceBefore=4,
                         spaceAfter=2)


def p(t, s=testo):
    return Paragraph(t, s)


def punti(*righe):
    return [Paragraph(r, punto, bulletText="•") for r in righe]


# ---------------------------------------------------------------- elementi grafici

class Cerchio(Flowable):
    """Numero di un passo in un cerchio verde."""

    def __init__(self, n, colore=VERDE, d=0.62 * cm):
        super().__init__()
        self.n, self.colore, self.d = n, colore, d

    def wrap(self, *a):
        return self.d, self.d

    def draw(self):
        c = self.canv
        c.setFillColor(self.colore)
        c.circle(self.d / 2, self.d / 2, self.d / 2, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Tondo", 10)
        c.drawCentredString(self.d / 2, self.d / 2 - 3.4, str(self.n))


def passi(*righe, da=1, larghezza=10.0 * cm):
    """Passi numerati: cerchio verde + testo."""
    righe_t = [[Cerchio(i), p(r, ParagraphStyle("pp", parent=testo, spaceAfter=0))] for i, r in enumerate(righe, da)]
    t = Table(righe_t, colWidths=[0.95 * cm, larghezza - 0.95 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return t


class Simbolo(Flowable):
    """Cerchio colorato con un segno dentro (per i riquadri)."""

    def __init__(self, segno, colore):
        super().__init__()
        self.segno, self.colore = segno, colore

    def wrap(self, *a):
        return 0.7 * cm, 0.7 * cm

    def draw(self):
        c = self.canv
        c.setFillColor(self.colore)
        c.circle(0.35 * cm, 0.35 * cm, 0.35 * cm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Tondo", 12)
        c.drawCentredString(0.35 * cm, 0.35 * cm - 4.2, self.segno)


def riquadro(t, tipo="consiglio", larghezza=17.0 * cm):
    """Riquadro con simbolo: 'consiglio' (oro, !) o 'info' (verde, i)."""
    sfondo, colore, segno = (ORO_CHIARO, ORO, "!") if tipo == "consiglio" else (VERDE_CHIARO, VERDE_2, "i")
    tab = Table([[Simbolo(segno, colore), p(t, ParagraphStyle("r", parent=testo, spaceAfter=0))]],
                colWidths=[1.0 * cm, larghezza - 1.0 * cm])
    tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), sfondo), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                             ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                             ("ROUNDEDCORNERS", [10, 10, 10, 10])]))
    return tab


class Telefono(Flowable):
    """Schermata ritagliata dentro una cornice da telefono, con ombra."""

    BORDO = 0.2 * cm

    def __init__(self, nome, alto=0, basso=None, larghezza=5.6 * cm):
        super().__init__()
        img = PILImage.open(IMG / nome)
        basso = basso or img.height
        self.file = Path(tempfile.gettempdir()) / f"guida_{alto}_{basso}_{nome}"
        img.crop((0, alto, img.width, basso)).save(self.file, quality=90)
        self.w = larghezza
        self.h = larghezza * (basso - alto) / img.width

    def wrap(self, *a):
        return self.w + 2 * self.BORDO + 4, self.h + 2 * self.BORDO + 4

    def draw(self):
        c, b = self.canv, self.BORDO
        W, H = self.w + 2 * b, self.h + 2 * b
        c.setFillColor(colors.Color(0, 0, 0, alpha=0.12))
        c.roundRect(3, -3, W, H, 16, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#1b2420"))
        c.roundRect(0, 0, W, H, 16, stroke=0, fill=1)
        c.saveState()
        path = c.beginPath()
        path.roundRect(b, b, self.w, self.h, 11)
        c.clipPath(path, stroke=0, fill=0)
        c.drawImage(str(self.file), b, b, self.w, self.h)
        c.restoreState()


def affiancati(telefono, contenuto, spazio=6.6 * cm):
    t = Table([[telefono, contenuto]], colWidths=[spazio, 17.0 * cm - spazio])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (0, -1), 14), ("RIGHTPADDING", (1, 0), (1, -1), 0)]))
    return t


class Capitolo(Flowable):
    """Fascia verde a tutta larghezza con il numero in un cerchio dorato."""

    def __init__(self, n, titolo, sotto=None):
        super().__init__()
        self.n, self.t, self.sotto = n, titolo, sotto
        self.height = 2.0 * cm if sotto else 1.6 * cm

    def wrap(self, w, h):
        self.width = w
        return w, self.height + 0.35 * cm

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.saveState()
        path = c.beginPath()
        path.roundRect(0, 0.35 * cm, w, h, 14)
        c.clipPath(path, stroke=0, fill=0)
        c.linearGradient(0, 0, w, h, (SCURO, VERDE_2), extend=True)
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.05))
        for x in range(0, int(w), 56):  # strisce del prato
            c.rect(x, 0, 28, h + 1 * cm, stroke=0, fill=1)
        c.restoreState()
        cy = 0.35 * cm + h / 2
        c.setFillColor(ORO)
        c.circle(1.0 * cm, cy, 0.52 * cm, stroke=0, fill=1)
        c.setFillColor(SCURO)
        c.setFont("Tondo", 16)
        c.drawCentredString(1.0 * cm, cy - 5.5, str(self.n))
        c.setFillColor(colors.white)
        c.setFont("Tondo", 19)
        c.drawString(1.9 * cm, cy - (0 if self.sotto else 6.5) + (3 if self.sotto else 0), self.t)
        if self.sotto:
            c.setFont("Arial", 10.5)
            c.setFillColor(colors.Color(1, 1, 1, alpha=0.8))
            c.drawString(1.9 * cm, cy - 14, self.sotto)


class Colori(Flowable):
    """Legenda: pallini colorati con descrizione."""

    def __init__(self, voci, larghezza=9.6 * cm):
        super().__init__()
        self.voci, self.w = voci, larghezza

    def wrap(self, *a):
        return self.w, len(self.voci) * 0.62 * cm + 0.2 * cm

    def draw(self):
        c = self.canv
        y = len(self.voci) * 0.62 * cm - 0.3 * cm
        for colore, testo_v in self.voci:
            c.setFillColor(colors.HexColor(colore))
            c.roundRect(0, y - 4, 0.9 * cm, 0.4 * cm, 5, stroke=0, fill=1)
            c.setFillColor(TESTO)
            c.setFont("Arial", 10.5)
            c.drawString(1.2 * cm, y - 1, testo_v)
            y -= 0.62 * cm


# ---------------------------------------------------------------- pagine speciali

def copertina(c, doc):
    c.saveState()
    c.linearGradient(0, 0, LARGH, ALT, (SCURO, VERDE_2), extend=True)
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.04))
    for x in range(0, int(LARGH), 64):
        c.rect(x, 0, 32, ALT, stroke=0, fill=1)
    # cerchio di centrocampo decorativo
    c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.08))
    c.setLineWidth(3)
    c.circle(LARGH * 0.82, ALT * 0.18, 5.5 * cm, stroke=1, fill=0)
    c.line(0, ALT * 0.18, LARGH, ALT * 0.18)
    # bagliore oro
    c.setFillColor(colors.Color(0.95, 0.72, 0.02, alpha=0.10))
    c.circle(LARGH * 0.95, ALT * 0.95, 7 * cm, stroke=0, fill=1)

    # logo con cornice bianca e ombra, così si stacca dallo sfondo verde
    x0, y0, lato = 2.2 * cm, ALT - 5.4 * cm, 2.6 * cm
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.25))
    c.roundRect(x0 - 3 + 4, y0 - 3 - 5, lato + 6, lato + 6, 18, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.roundRect(x0 - 3, y0 - 3, lato + 6, lato + 6, 18, stroke=0, fill=1)
    c.saveState()
    cornice = c.beginPath()
    cornice.roundRect(x0, y0, lato, lato, 15)
    c.clipPath(cornice, stroke=0, fill=0)
    c.drawImage(ICONA, x0, y0, lato, lato)
    c.restoreState()
    c.setFillColor(colors.white)
    c.setFont("Tondo", 38)
    c.drawString(2.2 * cm, ALT - 7.6 * cm, "Fanta Consigliere")
    c.setFillColor(ORO)
    c.setFont("Tondo", 17)
    c.drawString(2.2 * cm, ALT - 8.6 * cm, "Guida semplice per usare l'app")

    voci = ["La formazione migliore, ogni giornata", "Avvisi sul telefono prima della consegna",
            "Consigli per l'asta, da zero o di riparazione"]
    y = ALT - 10.4 * cm
    for v in voci:
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.12))
        c.roundRect(2.2 * cm, y - 0.32 * cm, 10.2 * cm, 0.95 * cm, 12, stroke=0, fill=1)
        c.setFillColor(ORO)
        c.circle(2.75 * cm, y + 0.15 * cm, 0.14 * cm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Arial", 12)
        c.drawString(3.2 * cm, y + 0.03 * cm, v)
        y -= 1.25 * cm

    c.setFillColor(colors.Color(1, 1, 1, alpha=0.75))
    c.setFont("Arial", 11)
    c.drawString(2.2 * cm, 3.0 * cm, "Si apre da qui:")
    c.setFillColor(colors.white)
    c.setFont("Tondo", 14)
    c.drawString(2.2 * cm, 2.3 * cm, "ernspa94.github.io/fanta-consigliere")
    c.restoreState()

    # telefono con la schermata del consiglio
    tel = Telefono("02_consiglio.jpg", 0, 1240, larghezza=5.4 * cm)
    tel.canv = c
    c.saveState()
    c.translate(LARGH - 7.6 * cm, 4.2 * cm)
    c.rotate(4)
    tel.wrap()
    tel.draw()
    c.restoreState()


def pie_di_pagina(c, doc):
    c.saveState()
    c.setStrokeColor(BORDO)
    c.setLineWidth(1)
    c.line(2 * cm, 1.55 * cm, LARGH - 2 * cm, 1.55 * cm)
    c.setFont("Arial", 9)
    c.setFillColor(GRIGIO)
    c.drawString(2 * cm, 1.1 * cm, "Fanta Consigliere · guida all'uso")
    c.setFillColor(VERDE)
    c.setFont("Tondo", 10)
    c.drawRightString(LARGH - 2 * cm, 1.1 * cm, str(doc.page))
    c.restoreState()


# ---------------------------------------------------------------- contenuto

COL = 9.6 * cm  # colonna di testo accanto al telefono
storia = [PageBreak()]

# 1-2
storia += [
    Capitolo(1, "Mettila sul telefono", "Una volta sola, due minuti"),
    p("Su iPhone", sottotitolo),
    passi("Apri <b>Safari</b> (l'app con la bussola blu) e scrivi l'indirizzo "
          "<b>ernspa94.github.io/fanta-consigliere</b>",
          "Tocca il tasto <b>Condividi</b> in basso al centro: è il quadrato con la freccia verso l'alto.",
          "Scorri il menu e tocca <b>Aggiungi alla schermata Home</b>, poi <b>Aggiungi</b>.",
          "Sulla schermata Home compare l'icona <b>Consigliere</b> con il campo da calcio verde. "
          "Da adesso apri l'app sempre da lì.", larghezza=17 * cm),
    p("Su Android", sottotitolo),
    passi("Apri l'indirizzo con <b>Chrome</b>.",
          "Tocca i <b>tre puntini</b> in alto a destra e scegli <b>Aggiungi a schermata Home</b>.", larghezza=17 * cm),
    Spacer(1, 0.2 * cm),
    riquadro("Su iPhone le <b>notifiche</b> funzionano solo se apri l'app dall'icona sulla schermata Home, non da "
             "Safari."),
    Spacer(1, 0.2 * cm),
    riquadro("L'app <b>non consegna la formazione al posto tuo</b>: la inserisci tu su Leghe Fantacalcio, come hai "
             "sempre fatto. L'app ti dice cosa conviene schierare.", "info"),
    PageBreak(),
    Capitolo(2, "La tua squadra", "La pagina iniziale"),
    affiancati(Telefono("01_home.jpg", 0, 1500),
               [p("Quando apri l'app vedi questa pagina. In alto ci sono due schede: <b>Squadre</b> (le tue squadre "
                  "e i consigli) e <b>Asta</b> (capitolo 9)."),
                p("Un amico ti ha mandato un codice?", sottotitolo),
                p("Scrivilo in <b>Entra con un codice</b> e tocca <b>Entra</b>. Rosa e regolamento sono già pronti: "
                  "non devi rifare niente."),
                p("Vuoi creare una squadra nuova?", sottotitolo),
                passi("Scrivi il <b>nome della squadra</b> e della <b>lega</b>.",
                      "Scegli il <b>regolamento di partenza</b>. Se non sai cosa scegliere, lascia <b>Standard Leghe "
                      "Fantacalcio</b>.",
                      "Tocca <b>Crea squadra</b> e poi inserisci la rosa (capitolo 6).", larghezza=COL),
                p("Le squadre che segui hanno un <b>bollino colorato</b> con le iniziali: tocca il nome per aprirla. "
                  "Puoi seguirne più di una, anche di leghe diverse.")]),
    PageBreak(),
]

# 3
storia += [
    Capitolo(3, "Il consiglio della giornata", "La scheda che userai di più"),
    p("Quando apri una squadra trovi quattro schede: <b>Consiglio</b>, <b>Rosa</b>, <b>Regole</b> e <b>Condividi</b>.",
      piccolo),
    affiancati(Telefono("02_consiglio.jpg", 0, 1380),
               [p("Giornata", sottotitolo),
                p("La giornata che stai guardando. Dal menu puoi scegliere anche le <b>giornate già giocate</b> per "
                  "rivedere cosa ti era stato consigliato."),
                p("Consegna entro", sottotitolo),
                p("L'ora limite per inserire la formazione su Leghe Fantacalcio: un minuto prima della prima partita "
                  "della giornata. Quando manca poco diventa rossa."),
                p("Modulo e punti attesi", sottotitolo),
                p("Nel riquadro verde: il modulo consigliato e, in oro, quanti punti dovresti fare in media. La riga "
                  "sotto (\"8 volte su 10 tra 64,5 e 80,5\") è il risultato più probabile."),
                p("Quanti gol facciamo", sottotitolo),
                p("La probabilità di fare 0, 1, 2, 3 o più gol con le soglie della tua lega. La <b>barra dorata</b> è "
                  "il risultato più probabile.")]),
    Spacer(1, 0.3 * cm),
    riquadro("Se leggi <b>\"In attesa delle probabili\"</b> è tutto normale: il consiglio arriva appena escono le "
             "probabili formazioni, di solito tra martedì e mercoledì. Ti avvisa una notifica.", "info"),
    PageBreak(),
]

# 4
storia += [
    Capitolo(4, "Il campo e la panchina"),
    affiancati(Telefono("03_campo.jpg", 175, 1600),
               [p("Sul campo vedi gli <b>11 titolari consigliati</b>. Sotto ogni nome: l'<b>avversario</b> (\"vs\" = in "
                  "casa, \"@\" = in trasferta) e la <b>probabilità che prenda il voto</b>."),
                p("Il colore della percentuale", sottotitolo),
                Colori([("#16884e", "Verde: quasi sicuro (85% o più)"), ("#c27c0e", "Arancione: in dubbio (60-85%)"),
                        ("#cc3b2f", "Rosso: rischio alto (meno del 60%)")]),
                p("Il colore sopra il nome", sottotitolo),
                Colori([(RUOLI["P"], "Portiere"), (RUOLI["D"], "Difensore"), (RUOLI["C"], "Centrocampista"),
                        (RUOLI["A"], "Attaccante")]),
                p("La panchina", sottotitolo),
                p("È già <b>nell'ordine giusto</b>: inseriscila così su Leghe Fantacalcio. Il numero colorato a destra "
                  "sono i punti che quel giocatore dovrebbe portare. Più sotto, in <b>Non disponibili</b>, trovi "
                  "infortunati e squalificati con il motivo.")]),
    PageBreak(),
    p("Tocca un giocatore per saperne di più", sottotitolo),
    affiancati(Telefono("04_dettaglio.jpg", 930, 1624),
               [p("Si apre un riquadro dal basso con:"),
                *punti("<b>Prende voto</b>: la probabilità che giochi abbastanza da avere il voto.",
                       "<b>Fantavoto se gioca</b>: il fantavoto medio che ci si aspetta, bonus compresi.",
                       "<b>Punti attesi</b>: i due numeri insieme.",
                       "Sotto: cosa dicono le probabili di <b>Fantacalcio.it</b> e di <b>Sky</b>, e se tira i rigori. "
                       "Un'ora prima della partita compare <b>\"Titolare nella formazione ufficiale\"</b>.")]),
    Spacer(1, 0.6 * cm),
    Capitolo(5, "Altri moduli, ricalcolo e notifiche"),
    affiancati(Telefono("05_moduli.jpg", 210, 1430),
               [p("Moduli", sottotitolo),
                p("Il consiglio usa il modulo che porta più punti (quello verde), ma puoi <b>toccarne un altro</b> per "
                  "vedere la sua formazione migliore e quanti punti vale."),
                p("Ricalcola adesso", sottotitolo),
                p("Rifà subito il calcolo, per esempio dopo che hai cambiato la rosa. <b>Di solito non serve</b>: l'app "
                  "si aggiorna da sola ogni 2 ore, e ogni 15 minuti nelle ore prima della consegna."),
                p("Notifiche", sottotitolo),
                p("Apri l'app dall'icona sulla Home, scrivi il tuo nome, tocca <b>Attiva</b> e poi <b>Consenti</b>. "
                  "Ti avvisa quando esce il consiglio, quando cambia la formazione (chi entra, chi esce e perché) e "
                  "<b>3 ore</b> e <b>30 minuti</b> prima della consegna.")]),
    PageBreak(),
]

# 6-7
storia += [
    Capitolo(6, "La rosa"),
    affiancati(Telefono("06_rosa.jpg", 0, 1160),
               [p("In alto vedi quanti giocatori hai per ruolo: <b>P</b> portieri, <b>D</b> difensori, <b>C</b> "
                  "centrocampisti, <b>A</b> attaccanti."),
                p("Aggiungere", sottotitolo),
                p("Scrivi almeno due lettere del nome nel riquadro con la lente e tocca il <b>+</b> verde."),
                p("Togliere", sottotitolo),
                p("Tocca la <b>×</b> accanto al nome."),
                p("Salvare", sottotitolo),
                p("Quando cambi qualcosa compare in basso la barra scura <b>Modifiche non salvate</b>: tocca il bottone "
                  "giallo <b>Salva</b>. Il consiglio si aggiorna da solo in qualche minuto.")]),
    Spacer(1, 0.5 * cm),
    Capitolo(7, "Il regolamento"),
    affiancati(Telefono("07_regole.jpg", 330, 1380),
               [p("Serve all'app per contare i punti <b>come nella tua lega</b>."),
                passi("In <b>Parti da un modello</b> scegli \"Standard Leghe Fantacalcio\" e tocca <b>Applica</b>: va "
                      "bene per la maggior parte delle leghe.",
                      "Cambia solo quello che nella tua lega è diverso. Esempio: se il gol del difensore vale +4, cambia "
                      "solo la casella <b>Gol</b> nella colonna <b>D</b>.",
                      "Più in basso trovi moduli ammessi, modificatore difesa, cambi massimi e soglie dei gol.",
                      "Tocca <b>Salva</b>.", larghezza=COL),
                riquadro("Se non sei sicuro di una regola lascia quella standard: il consiglio resta comunque buono.",
                         larghezza=COL)]),
    PageBreak(),
]

# 8
storia += [
    Capitolo(8, "Condividere la squadra"),
    affiancati(Telefono("08_condividi.jpg", 0, 1560),
               [p("Ogni squadra ha un <b>codice segreto</b>. Chi ce l'ha può vedere e modificare la squadra: non serve "
                  "registrarsi."),
                passi("Tocca <b>Copia link</b>.",
                      "Incollalo su WhatsApp e mandalo a chi gestisce la squadra con te.",
                      "Lui apre il link e trova la squadra pronta. Se usa l'app dall'icona sulla Home, scrive il "
                      "codice in <b>Entra con un codice</b>.", larghezza=COL),
                riquadro("Manda il link <b>solo a chi gestisce la squadra con te</b>, non agli avversari: potrebbero "
                         "vedere e cambiare la tua rosa.", larghezza=COL),
                Spacer(1, 0.3 * cm),
                p("Qui puoi anche cambiare il <b>nome</b> della squadra e della lega. <b>Togli la squadra da questo "
                  "telefono</b> la nasconde solo dal tuo telefono, non la cancella.")]),
    PageBreak(),
]

# 9
storia += [
    Capitolo(9, "L'asta", "Pagina iniziale, scheda Asta"),
    riquadro("Non serve creare prima una squadra. L'asta ti aiuta <b>quando devi comprare</b>: all'asta d'estate (da "
             "zero) o a quella di riparazione. Non giudica le aste già fatte.", "info"),
    Spacer(1, 0.4 * cm),
    affiancati(Telefono("09_asta.jpg", 0, 1010),
               [p("Prima dell'asta", sottotitolo),
                passi("In <b>Che asta fai?</b> scegli <b>Asta da zero</b> se costruisci una rosa nuova, oppure "
                      "<b>Riparazione</b> e il nome di una tua squadra.",
                      "Asta da zero: scegli il <b>regolamento</b> e scrivi quante <b>squadre</b> ci sono in lega e "
                      "quanti <b>crediti</b> ha ognuno.",
                      "Riparazione: scrivi i <b>crediti disponibili</b> e quanti giocatori pensi di comprare.",
                      larghezza=COL),
                p("Sotto il riepilogo ti dice quanti crediti ti restano e quanti ne restano a tutta la lega.")]),
    Spacer(1, 0.4 * cm),
    affiancati(Telefono("09b_asta_lista.jpg", 220, 1240),
               [p("La lista dei più utili", sottotitolo),
                p("Per ogni giocatore leggi:"),
                *punti("<b>max</b>: la tua offerta massima;",
                       "<b>probabile</b>: quanto verrà pagato di solito;",
                       "il numero verde: quanti punti in più a giornata ti porta."),
                p("E un'etichetta colorata:"),
                Colori([("#16884e", "AFFARE: costa meno di quanto rende"), ("#8a958f", "PREZZO GIUSTO"),
                        ("#cc3b2f", "CARO: costa più di quanto rende")]),
                p("Con i bottoni P, D, C, A vedi un ruolo alla volta.")]),
    PageBreak(),
    p("Durante l'asta, per ogni giocatore chiamato", sottotitolo),
    affiancati(Telefono("10_asta_dialog.jpg", 575, 1624),
               [passi("Scrivi il nome nella <b>ricerca</b> (va bene anche il nome di battesimo, es. \"Lautaro\") e "
                      "tocca il giocatore.",
                      "Leggi i tre numeri: <b>Offerta massima</b> (oltre non ti conviene), <b>Prezzo probabile</b> "
                      "(quanto si paga di solito) e <b>Valore statistiche</b> (quanto vale secondo i suoi numeri).",
                      "A fine chiamata: se l'hai preso tu, scrivi il <b>prezzo</b> e tocca <b>Preso da me</b>. Se l'ha "
                      "preso un altro tocca <b>Preso da altri</b>: il prezzo è facoltativo, ma se lo scrivi l'app "
                      "capisce meglio quanti crediti restano in lega.", da=4, larghezza=COL)]),
    Spacer(1, 0.3 * cm),
    riquadro("Se il prezzo probabile è molto più alto della tua offerta massima (\"caro\"), lascialo andare: per la tua "
             "squadra vale meno di quanto costa."),
    Spacer(1, 0.5 * cm),
    affiancati(Telefono("11_asta_rosa.jpg", 400, 1160),
               [p("La tua rosa all'asta", sottotitolo),
                *punti("Nell'asta da zero i giocatori che compri finiscono in <b>La tua rosa</b>, con il prezzo. "
                       "Crediti e posti liberi si aggiornano da soli.",
                       "Hai sbagliato? Tocca la <b>freccia</b> accanto al nome per annullare.",
                       "A fine asta tocca <b>Salva come nuova squadra</b>: da lì ricevi i consigli per ogni giornata.",
                       "Nell'asta di <b>riparazione</b> quello che compri entra subito nella rosa della squadra; se il "
                       "ruolo è pieno l'app ti chiede chi svincolare.")]),
    PageBreak(),
]

# 10
faq = [
    ("Quando arriva il consiglio?",
     "Appena escono le probabili formazioni, di solito tra martedì e mercoledì. Poi si aggiorna da solo fino alla "
     "consegna, anche con le formazioni ufficiali che escono un'ora prima delle partite."),
    ("Devo tenere l'app aperta?", "No. Lavora da sola: quando la apri trovi sempre l'ultimo consiglio."),
    ("L'app si aggiorna da sola?",
     "Sì, sia i consigli sia l'app. Se vedi qualcosa di vecchio, tocca la freccia circolare in alto a destra oppure "
     "chiudi e riapri l'app."),
    ("Il consiglio è sicuro?",
     "È una stima fatta con le statistiche e le probabili formazioni: nel calcio le sorprese ci sono sempre. Su tante "
     "giornate aiuta a fare più punti, ma la scelta finale è tua."),
    ("Ho cambiato la rosa ma il consiglio è uguale.",
     "Hai toccato Salva? Dopo il salvataggio il nuovo consiglio arriva in qualche minuto."),
    ("Non mi arrivano le notifiche.",
     "Apri l'app dall'icona sulla schermata Home, non da Safari, e controlla in Impostazioni → Notifiche → Consigliere "
     "che siano attive. Serve iPhone con iOS 16.4 o più recente."),
    ("Ho cambiato telefono e non vedo più la squadra.",
     "Rientra con il codice della squadra. Se non lo hai, chiedilo a chi la gestisce con te: lo trova nella scheda "
     "Condividi."),
    ("L'app consegna la formazione al posto mio?",
     "No. La formazione la inserisci tu su Leghe Fantacalcio prima della scadenza, seguendo il consiglio."),
]
storia.append(Capitolo(10, "Domande frequenti"))
for d, r in faq:
    blocco = Table([[[p(d, domanda), p(r, ParagraphStyle("fr", parent=testo, spaceAfter=0))]]], colWidths=[17 * cm])
    blocco.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f7f5")),
                                ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                                ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                                ("ROUNDEDCORNERS", [10, 10, 10, 10])]))
    storia += [KeepTogether([blocco]), Spacer(1, 0.25 * cm)]

doc = SimpleDocTemplate(str(USCITA), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                        bottomMargin=2 * cm, title="Fanta Consigliere - Guida all'uso", author="Fanta Consigliere",
                        subject="Guida semplice all'app Fanta Consigliere")
doc.build(storia, onFirstPage=copertina, onLaterPages=pie_di_pagina)
print("scritto", USCITA)
