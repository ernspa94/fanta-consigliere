# Consigliere formazione — Fanta Lignano

App che ogni giornata consiglia la formazione migliore per la nostra rosa, usando probabili/ufficiali, statistiche e calendario.

## Decisioni (2 novembre 2026)

| Tema | Scelta |
|---|---|
| Lega | Classic, Fanta Lignano su Leghe Fantacalcio, scontri diretti a soglia |
| Regole | `config/lega.json` (dal regolamento 2026/27) |
| Utenti | 2 persone, stessa squadra, entrambi modificano la rosa |
| App | PWA su GitHub Pages (Safari → Aggiungi a Home) |
| Calcolo | Python su GitHub Actions, aggiornamenti continui da metà settimana alla scadenza |
| Rosa condivisa | Supabase (piano gratuito), accesso con codice squadra |
| Dati | Solo gratuiti: API-Football free + probabili formazioni da 2–3 siti |
| Notifiche | Web push (iOS 16.4+, PWA aggiunta alla Home) |
| Inserimento rosa | Cerca e aggiungi dal listone Serie A |

## La rosa

`config/rosa.json` — **Berlusca Dortmund** (Gianmarco & ern), 25 giocatori trascritti dagli screenshot dell'app il 2 novembre 2026.

- Tutti e 3 i portieri sono del Napoli: ogni giornata va schierato chi gioca titolare tra Meret e Milinkovic-Savic.
- 6 giocatori del Napoli in rosa: le partite del Napoli pesano molto sulla giornata.

Repository: https://github.com/ernspa94/fanta-consigliere (pubblico). Il workflow `.github/workflows/consiglio.yml` ricalcola il consiglio ogni 2 ore (7–23 ora italiana) e fa un commit solo se cambia.

## Motore (engine/)

Si lancia da `engine/` con `../.venv/bin/python -m fanta.consiglia` e salva il risultato in `output/consiglio.json`.

| File | Cosa fa |
|---|---|
| `fanta/fonti.py` | Scarica da Fantacalcio.it le probabili (con % di titolarità, infortunati, squalificati) e le statistiche della stagione in corso e della scorsa |
| `fanta/rosa.py` | Collega i giocatori di `config/rosa.json` agli id di Fantacalcio.it |
| `fanta/modello.py` | Forza delle squadre, gol attesi della partita, probabilità di prendere voto, media voto e frequenza di bonus e malus per giocatore |
| `fanta/simulazione.py` | 4000 scenari della giornata (gol delle squadre condivisi tra compagni, voti legati a gol e gol subiti) |
| `fanta/regole.py` | Punteggio con le regole della lega: sostituzioni, cambio modulo, massimo 5 cambi, modificatore difesa |
| `fanta/ottimizzatore.py` | Per ogni modulo: formazione iniziale, poi scambi titolare/panchinaro finché migliora |
| `tests/test_regole.py` | Test delle regole su scenari costruiti a mano |

Limiti noti del modello: non usa le quote dei bookmaker, non sa chi tira i rigori e non tiene conto dei minuti giocati dai subentrati. Le statistiche di Serie B delle neopromosse non sono disponibili.

## Regole che contano per l'algoritmo

- **Modificatore difesa** (+1/+3/+6) vale solo con **almeno 4 difensori** schierati e portiere a voto: con un 3-x-x si rinuncia. L'ottimizzatore deve sommarne il valore atteso al modulo.
- **Porta imbattuta +1** al portiere e **MVP Panini +0,5** sono nella tabella bonus ma non nel testo dell'Art. 6.
- **Massimo 5 sostituzioni**, panchina lunga, il primo panchinaro dello stesso ruolo nell'ordine di panchina: l'ordine della panchina va consigliato.
- **Senza voto non sostituibile = 0**: penalizza molto i titolari incerti.
- **Soglie gol** 66 / 70 / 74 …: si ragiona sui fantapunti attesi, la soglia serve solo per mostrare i gol stimati.
