# Playlist Manager

Questo è un programma per la gestione di playlist video con estrazione dei metadati dai file `.nfo` stile Kodi,
visualizzazione dei poster e gestione del database SQLite.

This is a program for managing video playlists with Kodi-style metadata extraction from .nfo files,
poster viewing, and SQLite database management.

# Playlist

**Playlist Manager** è un'applicazione desktop in Python che permette di:
- Scansionare cartelle contenenti video e file `.nfo`
- Estrarre automaticamente metadati (titolo, anno, genere, regista, trama, poster) dai file `.nfo`
- Memorizzare i dati in un database SQLite locale
- Visualizzare i video in una GUI con filtri per genere, anno e regista
- Creare e gestire playlist video
- Mostrare i poster dei film/video sia nella finestra principale sia nella finestra della playlist
- Gestire completamente il database tramite un'interfaccia dedicata (senza inserimento manuale, solo modifica/eliminazione)

---

## Funzionalità principali

- **Parsing NFO**: legge e interpreta file `.nfo` compatibili con standard come Kodi o XBMC.
- **Gestione database**: archivia i dati in un database SQLite nella stessa cartella dell'app.
- **Filtri avanzati**: per selezionare contenuti in base a genere, anno o regista.
- **Playlist personalizzate**: crea, visualizza e salva playlist contenenti i video selezionati.
- **Poster nella GUI**: visualizzazione immediata del poster associato al video.
- **Gestione DB da GUI**: possibilità di eliminare più record contemporaneamente secondo un campo selezionato.

---

## Requisiti

- **Python** >= 3.9
- Librerie Python richieste:
  ```bash
  pip install pillow


- oppure **Installare le dipendenze**
  ```bash
  pip install -r requirements.txt


# Come usare l'applicazione

## Clonare o scaricare il progetto
  ```bash 
  git clone https://github.com/tuo-utente/PlaylistDue.git
  cd PlaylistDue


- Avviare l'applicazione
  ```bash 
  python (o python3) main_window.py

# Funzionamento base

- Usa il pulsante "Scansiona cartella" per indicare una directory contenente video + .nfo.
- Filtra i risultati usando i menu a tendina.
- Crea playlist con i video selezionati.
- Visualizza i poster e la trama direttamente dalla GUI.
- Accedi alla Gestione Database dal pulsante dedicato.

# Formato NFO supportato

## Esempio minimo:
```xml
"<movie>
    <title>Il mio film</title>
    <year>2023</year>
    <genre>Azione</genre>
    <genre>Avventura</genre>
    <director>Mario Rossi</director>
    <plot>Una trama avvincente.</plot>
    <thumb>poster.jpg</thumb>
</movie>"

- **Il file .nfo deve avere lo stesso nome del video corrispondente.**

# Contributi

Sono benvenuti contributi, segnalazioni di bug e nuove funzionalità!
Apri una **Issue** o invia una **Pull Request** su GitHub.

## Licenza
Distribuito sotto GPL v3.

Distributed under GPL v3.
