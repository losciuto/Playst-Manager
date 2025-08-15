# Playlist Manager

Playlist Manager è un'applicazione desktop in Python per la gestione e visualizzazione di playlist video, con integrazione dei metadati dai file `.nfo` stile Kodi e un'interfaccia per la gestione completa del database.

## Funzionalità principali

- Caricamento automatico dei metadati dai file `.nfo`
- Visualizzazione di poster e dettagli video
- Filtri per genere, anno e regista
- Creazione e gestione di playlist
- Interfaccia per la gestione delle tabelle del database (eliminazione di più record in base a un campo selezionato)
- Supporto a vari formati video: `.mp4`, `.mkv`, `.avi`, `.mov`

## Requisiti

- Python 3.8+
- Librerie indicate in `requirements.txt`

## Installazione

1. Clona o scarica questo repository
2. Installa i requisiti:
   ```bash
   pip install -r requirements.txt
   ```
3. Assicurati che il database SQLite (`videos.db`) sia nella stessa cartella del codice

## Utilizzo

Avvia l'app con:
```bash
python main_window.py
```

### Pulsanti principali
- **Apri cartella**: scansiona una cartella alla ricerca di file video e `.nfo`
- **Gestione DB**: apre la finestra di gestione delle tabelle
- **Filtri**: filtra i video per genere, anno o regista

## Licenza

Questo progetto è distribuito sotto licenza [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html).
