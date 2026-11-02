# Consigliere formazione — Fanta Lignano

App che ogni giornata consiglia la formazione migliore per la nostra rosa, usando probabili/ufficiali, statistiche e calendario.

## Decisioni (2 novembre 2026)

| Tema | Scelta |
|---|---|
| Lega | Classic, Fanta Lignano su Leghe Fantacalcio, scontri diretti a soglia |
| Regole | `config/regole/fanta-lignano.json` (dal regolamento 2026/27); modello di partenza per le altre leghe in `config/regole/standard.json` |
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

## Squadre e database (Supabase)

Dal 2 novembre 2026 l'app gestisce più squadre (gruppo di amici, leghe diverse), senza registrazione:
- ogni squadra ha un codice segreto di 12 caratteri; chi ha il link `?squadra=<codice>` la vede e la modifica;
- rosa, regolamento, consigli e iscrizioni alle notifiche stanno su Supabase (progetto `lqqkvfctyjtsainhmdkj`), non più nel repository pubblico;
- l'app usa la chiave anon e può solo chiamare le funzioni di `supabase/schema.sql` (le tabelle le sono chiuse); il motore usa la chiave service_role (segreto `SUPABASE_SERVICE_KEY`);
- "Ricalcola" chiama `richiedi_ricalcolo`, che avvia il workflow con il token `github_token` salvato nel Vault di Supabase (senza token il ricalcolo parte al giro successivo, entro 15 minuti);
- senza Supabase configurato il motore usa ancora `config/rosa.json` e `config/regole/fanta-lignano.json` (comodo in locale);
- regolamenti di partenza in `config/regole/`; le voci mancanti in quello di una squadra prendono il valore di `standard.json`.

## App (app/)

Web app su https://ernspa94.github.io/fanta-consigliere/ — su iPhone: Safari → Condividi → Aggiungi alla schermata Home.
Pubblicata da `.github/workflows/pages.yml` quando cambia `app/`. Squadre e consigli arrivano da Supabase; listone (`output/listone.json`) e modelli di regolamento da raw.githubusercontent.com. Tiene una copia dell'ultimo consiglio per l'uso offline.

## Asta (scheda "Asta")

- Il motore pubblica `output/valori.json` (`fanta/mercato.py`): per tutto il listone presenza attesa, media voto, frequenza di gol/assist/cartellini/rigori, gol subiti della squadra, FVM, nome completo da Sky (per cercare "Lautaro" invece di "Martinez L.").
- L'app (`app/asta.js`) applica il regolamento della squadra: fantavoto medio, punti attesi della formazione migliore (con le sostituzioni dalla panchina), "per te" = quanto salgono se lo prendi (o se sostituisce il peggiore del ruolo), offerta massima = crediti divisi in proporzione al valore portato da un piano di acquisti, tenendo 1 credito per ogni posto.
- Asta dal vivo: crediti, acquisti previsti e "presi da altri" stanno solo sul telefono; "preso da me" aggiorna la rosa sul server (e, se il ruolo è pieno, svincola il meno utile dopo conferma).
- Verifica sul 2025-26 (`python -m fanta.mercato`): con i dati fino alla g19, il valore del modello ordina i giocatori per i punti delle g20–38 un po' meglio di fantamedia × presenze (difensori 0,63 vs 0,62, centrocampisti 0,61 vs 0,57; attaccanti 0,63 vs 0,65). La presenza pesa le ultime 8 giornate (40% stagione, 30% a voto, 30% titolare): la stagione precedente peggiorava la stima. Per l'asta estiva, con la sola stagione prima, entrambi i metodi indovinano poco (0,3–0,4).
- FVM di Fantacalcio.it è su 1000 crediti: l'app lo riporta al budget della lega (`crediti_asta` nel regolamento, 500).

## Notifiche

- `engine/fanta/notifiche.py` confronta il consiglio precedente con il nuovo e manda: consiglio pronto (nuova giornata), formazione cambiata (chi entra/esce e perché), promemoria 3 ore e 30 minuti prima della consegna (una volta sola, registrati in `output/notifiche_inviate.json`).
- Notifica di prova: GitHub → Actions → "Aggiorna consiglio formazione" → Run workflow con "Manda solo una notifica di prova" (oppure `gh workflow run consiglio.yml -f prova=true`).
- `engine/fanta/pianifica.py`: il workflow parte ogni 15 minuti ma ricalcola solo nelle 8 ore prima della scadenza, altrimenti ogni 2 ore di giorno.
- Segreti del repository: `VAPID_PRIVATE_KEY` (chiave di firma; copia locale in `data/segreti/`, ignorata da git) e `PUSH_ISCRIZIONI` (lista JSON dei codici che l'app mostra dopo "Attiva notifiche").
- La scadenza è la prima partita della giornata meno 1 minuto, letta da `/serie-a/calendario/N/2026-27`. Se la giornata delle probabili è già iniziata, il consiglio passa in stato `in_attesa` sulla successiva.

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

| `fanta/storico_voti.py` | Voti veri giornata per giornata (Redazione Fantacalcio). Attenzione: il sito scrive 55 per "senza voto" |
| `fanta/banco_prova.py` | Confronta il fantavoto previsto dei titolari con quello vero, giornata per giornata |

### Banco di prova (2 novembre 2026)

Per ogni giornata si ricostruiscono le statistiche fino alla giornata prima e si prevede il fantavoto di chi parte titolare. Misure: errore medio e **correlazione di rango tra giocatori dello stesso ruolo** (quanto bene il modello ordina, ad esempio, i difensori: è la scelta che fa l'ottimizzatore).

| | 2025-26 (taratura) | 2026-27 g2–9 (verifica) |
|---|---|---|
| Fantamedia fino alla giornata prima | errore 1,085 · rango 0,135 | errore 1,300 · rango 0,148 |
| Modello iniziale | errore 1,047 · rango 0,185 | errore 1,151 · rango 0,251 |
| Modello con rigoristi e parametri tarati | errore 1,041 · rango 0,189 | errore 1,138 · rango 0,265 |

- Rigoristi: i gol su rigore si stimano a parte, da quanti rigori ha la squadra e da chi li tira (`/rigoristi-serie-a`); se il 1° rigorista non gioca passano al successivo.
- Taratura sul rango e non sull'errore: minimizzare l'errore "appiattisce" le previsioni e peggiora l'ordine dei giocatori.
- Rilanciare: `../.venv/bin/python -m fanta.banco_prova` dalla cartella `engine/` (prima volta: scarica ~90 pagine di voti, poi resta in `data/voti/`).

### Seconda fonte: Sky Sport (`fanta/sky.py`)

- Legge da sport.sky.it titolari, riserve, in dubbio, squalificati e indisponibili. Attenzione: sulla pagina delle probabili la scritta "Sono disponibili le formazioni ufficiali" è solo un rimando; le ufficiali vere (circa un'ora prima della partita) si leggono dalla pagina `/partite/.../formazioni` (`sky.aggiungi_ufficiali`). Chi non è né titolare né in panchina nella formazione ufficiale risulta "non convocato".
- I nomi si abbinano agli id di Fantacalcio.it squadra per squadra (link della scheda Sky, cognome, iniziale, piccoli refusi); i non riconosciuti sono quasi sempre ragazzi della Primavera fuori dal listone.
- Combinazione (`modello.probabilita_titolare`): formazioni ufficiali decidono (titolare 99%); altrimenti 60% Fantacalcio.it + 40% Sky; se una fonte lo dà fuori e l'altra titolare diventa "in dubbio" (30%). Pesi scelti a ragione, non ancora tarati.

### Archivio delle probabili (per tarare i pesi)

- A ogni giro, finché la giornata non è iniziata, `storico_probabili.py` salva cosa dicevano Fantacalcio.it e Sky su ogni giocatore in `output/probabili/2026-27/giornata-NN.json` (prima versione vista e ultima prima della scadenza). Sono dati pubblici e stanno nel repository.
- Dopo le partite le fonti non servono più per un test onesto: Fantacalcio.it sostituisce le probabili con le formazioni vere. Per questo l'archivio parte dalla giornata 11.
- `python -m fanta.taratura_probabili` confronta l'ultima versione con chi è partito titolare davvero (dai voti): Brier score, tabella di calibrazione e i pesi migliori. Ha senso dopo 4–5 giornate.
- Se Sky non risponde o è su un'altra giornata si usa solo Fantacalcio.it.

Limiti noti: niente quote dei bookmaker (nessuna fonte gratuita affidabile); forza squadre non corretta per gli avversari affrontati; la probabilità di giocare viene solo dalle probabili (la sua precisione si potrà misurare con lo storico dei consigli).

## Regole che contano per l'algoritmo

- **Modificatore difesa** (+1/+3/+6) vale solo con **almeno 4 difensori** schierati e portiere a voto: con un 3-x-x si rinuncia. L'ottimizzatore deve sommarne il valore atteso al modulo.
- **Porta imbattuta +1** al portiere e **MVP Panini +0,5** sono nella tabella bonus ma non nel testo dell'Art. 6.
- **Massimo 5 sostituzioni**, panchina lunga, il primo panchinaro dello stesso ruolo nell'ordine di panchina: l'ordine della panchina va consigliato.
- **Senza voto non sostituibile = 0**: penalizza molto i titolari incerti.
- **Soglie gol** 66 / 70 / 74 …: si ragiona sui fantapunti attesi, la soglia serve solo per mostrare i gol stimati.
