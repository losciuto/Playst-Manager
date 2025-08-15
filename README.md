# Playlist Manager

Un'applicazione Python con interfaccia grafica (Tkinter) per gestire playlist video, leggere metadati da file `.nfo`, e fornire strumenti per filtrare e organizzare i contenuti.

## Funzionalità principali

- **Gestione Playlist**: Caricamento e visualizzazione di playlist video.
- **Parsing NFO**: Lettura automatica di informazioni da file `.nfo` associati ai video (titolo, anno, trama, generi, registi, poster).
- **Filtri Avanzati**: Ricerca e filtraggio per genere, anno e regista.
- **Visualizzazione Poster**: Anteprima dei poster associati ai video.
- **Gestione Database**: Interfaccia dedicata per gestire le tabelle del database (visualizzazione, eliminazione multipla).
- **Supporto Formati Video**: `.mp4`, `.mkv`, `.avi`, `.mov`.

## Requisiti

- Python 3.8+
- Le dipendenze sono elencate in `requirements.txt`

## Installazione

1. Clona o scarica questo repository:
   ```bash
   git clone https://github.com/tuo-username/playlist-manager.git
   cd playlist-manager
   ```

2. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```

3. Avvia l'applicazione:
   ```bash
   python main_window.py
   ```

## Struttura del Progetto

```
playlist-manager/
│
├── main_window.py        # Finestra principale dell'applicazione
├── db_manager.py         # Gestione del database SQLite
├── nfo_parser.py         # Parsing dei file NFO
├── README.md             # Documentazione del progetto
├── requirements.txt      # Dipendenze Python
└── database.sqlite       # Database (generato automaticamente)
```

## Licenza

Questo progetto è distribuito sotto licenza **GPLv3** - vedi il file [LICENSE](LICENSE) per i dettagli.
