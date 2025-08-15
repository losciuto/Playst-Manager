# main_window.py
# -*- coding: utf-8 -*-
from PyQt5 import QtWidgets, QtCore, QtGui
import sqlite3
import os
import random
import subprocess
import shutil
import time
import tempfile
import urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET
import csv

# DB nella stessa cartella del codice
DB_FILENAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'videos.db')
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv']


# --------------------------- Dialog di progresso ---------------------------
class ProgressDialog(QtWidgets.QDialog):
    cancel_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None, maximum=100):
        super().__init__(parent)
        self.setWindowTitle("Processing")
        self.setModal(True)
        self.canceled = False
        layout = QtWidgets.QVBoxLayout(self)
        self.label = QtWidgets.QLabel("Processing files...")
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximum(maximum)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        layout.addWidget(self.label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.cancel_btn)
        self.resize(420, 140)

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        QtWidgets.QApplication.processEvents()

    def cancel(self):
        self.canceled = True
        self.cancel_requested.emit()


# --------------------------- Gestore DB ---------------------------
class DBManager:
    """Database helper per la tabella `videos`."""

    def __init__(self, db_path: str = DB_FILENAME):
        self.db_path = db_path
        # isolation_level=None => autocommit disattivato, usiamo commit manuale
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self):
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE,
                mtime REAL,
                genres TEXT,
                year TEXT,
                directors TEXT,
                plot TEXT,
                actors TEXT,
                duration TEXT,
                rating TEXT,
                poster TEXT
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_videos_path ON videos(path)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_videos_year ON videos(year)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_videos_directors ON videos(directors)')
        self.conn.commit()

    def close(self):
        try:
            self.conn.commit()
            self.conn.close()
        except Exception:
            pass

    # CRUD minimi usati dall’app
    def add_or_update_video(self, path, mtime, genres, year, directors, plot, actors, duration, rating, poster):
        cur = self.conn.cursor()
        cur.execute('''INSERT OR REPLACE INTO videos(path, mtime, genres, year, directors, plot, actors, duration, rating, poster)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (path, mtime, genres, year, directors, plot, actors, duration, rating, poster))
        self.conn.commit()

    def _split_serialized(self, s: str):
        if not s:
            return []
        if '|' in s:
            parts = [p.strip() for p in s.split('|') if p.strip()]
        else:
            parts = [p.strip() for p in s.split(',') if p.strip()]
        return parts

    def get_all_genres(self):
        cur = self.conn.cursor()
        cur.execute('SELECT genres FROM videos WHERE genres IS NOT NULL AND genres != ""')
        rows = cur.fetchall()
        genres = set()
        for row in rows:
            g = row['genres']
            if g:
                genres.update(self._split_serialized(g))
        return sorted(genres, key=lambda x: x.lower())

    def get_all_years(self):
        cur = self.conn.cursor()
        cur.execute('SELECT DISTINCT year FROM videos WHERE year IS NOT NULL AND year != ""')
        rows = cur.fetchall()
        years = [row['year'] for row in rows if row['year']]
        try:
            years_num = sorted(set(years), key=lambda y: int(y), reverse=True)
            return years_num
        except Exception:
            return sorted(set(years), key=lambda x: x, reverse=True)

    def get_all_directors(self):
        cur = self.conn.cursor()
        cur.execute('SELECT directors FROM videos WHERE directors IS NOT NULL AND directors != ""')
        rows = cur.fetchall()
        directors = set()
        for row in rows:
            d = row['directors']
            if d:
                directors.update(self._split_serialized(d))
        return sorted(directors, key=lambda x: x.lower())

    def query_videos(self, genres=None, years=None, directors=None, limit=1000):
        conditions = []
        params = []

        if genres:
            sub = ' OR '.join(['genres LIKE ?' for _ in genres])
            conditions.append(f'({sub})')
            params.extend([f'%{g}%' for g in genres])

        if years:
            placeholders = ','.join(['?'] * len(years))
            conditions.append(f'year IN ({placeholders})')
            params.extend(years)

        if directors:
            sub = ' OR '.join(['directors LIKE ?' for _ in directors])
            conditions.append(f'({sub})')
            params.extend([f'%{d}%' for d in directors])

        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        q = ("SELECT path, genres, year, directors, plot, actors, duration, rating, poster, mtime "
             "FROM videos " + where + " ORDER BY path LIMIT ?")
        params.append(limit)
        cur = self.conn.cursor()
        cur.execute(q, params)
        return cur.fetchall()

    # --- funzioni a supporto della finestra Gestione DB ---
    def fetch_all(self, order_by="path"):
        allowed = {"id", "path", "year", "mtime", "rating"}
        order_clause = order_by if order_by in allowed else "path"
        cur = self.conn.cursor()
        cur.execute(f'''SELECT id, path, genres, year, directors, plot, actors, duration, rating, poster, mtime
                        FROM videos
                        ORDER BY {order_clause}''')
        return cur.fetchall()

    def delete_by_field_match(self, field: str, value: str, use_like: bool = True):
        allowed = {"path", "genres", "year", "directors", "actors", "duration", "rating", "poster"}
        if field not in allowed:
            raise ValueError("Campo non valido")
        cur = self.conn.cursor()
        if use_like:
            cur.execute(f'DELETE FROM videos WHERE {field} LIKE ?', (value,))
        else:
            cur.execute(f'DELETE FROM videos WHERE {field} = ?', (value,))
        count = cur.rowcount
        self.conn.commit()
        return count

    def delete_ids(self, ids):
        if not ids:
            return 0
        cur = self.conn.cursor()
        placeholders = ','.join(['?'] * len(ids))
        cur.execute(f'DELETE FROM videos WHERE id IN ({placeholders})', ids)
        count = cur.rowcount
        self.conn.commit()
        return count

    def vacuum(self):
        cur = self.conn.cursor()
        cur.execute('VACUUM')
        self.conn.commit()


# --------------------------- Parser NFO ---------------------------
class NFOParser:
    """Legge generi, anno, registi, trama, runtime, rating, poster/thumb, attori dai .nfo."""

    def _get_actor_names(self, root):
        names = []
        for a in root.findall('actor'):
            name = a.findtext('name') or a.findtext('actor') or a.text
            if name and name.strip():
                names.append(name.strip())
        for a in root.findall('actors'):
            for child in a:
                if child.text and child.text.strip():
                    names.append(child.text.strip())
        return names

    def parse_video_info(self, nfo_path):
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            genres = [g.text.strip() for g in root.findall('genre') if g.text]
            genres_s = '|'.join(genres)
            year = root.findtext('year', '').strip()
            directors = [d.text.strip() for d in root.findall('director') if d.text]
            directors_s = '|'.join(directors)
            plot = root.findtext('plot', '').strip()
            actors_list = self._get_actor_names(root)
            actors_s = '|'.join(actors_list)
            duration = (root.findtext('runtime', '') or root.findtext('duration', '') or '').strip()
            rating = (root.findtext('rating', '') or '').strip()
            poster = ''
            for tag in ('thumb', 'poster', 'fanart'):
                v = root.findtext(tag)
                if v and v.strip():
                    poster = v.strip()
                    break
            if not poster:
                f = root.find('fanart')
                if f is not None:
                    t = f.findtext('thumb') or f.findtext('poster')
                    if t and t.strip():
                        poster = t.strip()
            return genres_s, year, directors_s, plot, actors_s, duration, rating, poster
        except Exception as e:
            print(f"Error parsing {nfo_path}: {e}")
            return '', '', '', '', '', '', '', ''


# --------------------------- Dialog locandine playlist ---------------------------
class PlaylistPosterDialog(QtWidgets.QDialog):
    def __init__(self, parent, items):
        super().__init__(parent)
        self.setWindowTitle('Playlist - Locandina')
        self.resize(900, 650)
        layout = QtWidgets.QVBoxLayout(self)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(container)

        for it in items:
            roww = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(roww)
            poster_label = QtWidgets.QLabel()
            poster_label.setFixedSize(150, 225)
            poster_label.setStyleSheet('border:1px solid #ccc; background:#000')
            pix = None
            poster = it.get('poster') or ''
            if poster and os.path.exists(poster):
                pix = QtGui.QPixmap(poster)
            elif poster:
                try:
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(poster)[1] if '.' in poster else '.img')
                    tmp.close()
                    urllib.request.urlretrieve(poster, tmp.name)
                    pix = QtGui.QPixmap(tmp.name)
                except Exception:
                    pix = None
            if pix and not pix.isNull():
                poster_label.setPixmap(pix.scaled(poster_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            h.addWidget(poster_label)

            info_w = QtWidgets.QWidget()
            info_l = QtWidgets.QVBoxLayout(info_w)
            fname = os.path.basename(it.get('path') or '')
            title_label = QtWidgets.QLabel(f"<b>{fname}</b>")
            title_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            info_l.addWidget(title_label)
            meta = []
            if it.get('year'):
                meta.append(f"Anno: {it.get('year')}")
            if it.get('directors'):
                meta.append(f"Regia: {it.get('directors')}")
            if it.get('actors'):
                meta.append(f"Cast: {it.get('actors')}")
            if it.get('genres'):
                meta.append(f"Generi: {it.get('genres')}")
            meta_label = QtWidgets.QLabel(' | '.join(meta))
            meta_label.setWordWrap(True)
            info_l.addWidget(meta_label)
            plot = it.get('plot') or ''
            if plot:
                plot_label = QtWidgets.QLabel(plot)
                plot_label.setWordWrap(True)
                plot_label.setFixedHeight(80)
                info_l.addWidget(plot_label)

            h.addWidget(info_w, 1)
            v.addWidget(roww)
            v.addSpacing(8)

        container.setLayout(v)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)


# --------------------------- Dialog gestione DB ---------------------------
class DBManagementDialog(QtWidgets.QDialog):
    """
    Gestione DB (nessun inserimento manuale):
      - Elimina più record per campo/valore (LIKE o =)
      - Elimina record selezionati
      - Esporta CSV
      - VACUUM
    """
    def __init__(self, db: DBManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Gestione DB")
        self.resize(1100, 650)

        layout = QtWidgets.QVBoxLayout(self)

        # Barra comandi
        cmd = QtWidgets.QHBoxLayout()
        self.field_combo = QtWidgets.QComboBox()
        self.field_combo.addItems(["path", "genres", "year", "directors", "actors", "duration", "rating", "poster"])
        self.value_edit = QtWidgets.QLineEdit()
        self.value_edit.setPlaceholderText("Valore da cercare… (puoi usare % con LIKE)")
        self.like_check = QtWidgets.QCheckBox("Usa LIKE")
        self.like_check.setChecked(True)
        del_match_btn = QtWidgets.QPushButton("Elimina corrispondenze")
        del_match_btn.clicked.connect(self.delete_matching)

        del_sel_btn = QtWidgets.QPushButton("Elimina selezionati")
        del_sel_btn.clicked.connect(self.delete_selected)

        export_btn = QtWidgets.QPushButton("Esporta CSV…")
        export_btn.clicked.connect(self.export_csv)

        vacuum_btn = QtWidgets.QPushButton("VACUUM")
        vacuum_btn.clicked.connect(self.do_vacuum)

        refresh_btn = QtWidgets.QPushButton("Aggiorna")
        refresh_btn.clicked.connect(self.load_table)

        cmd.addWidget(QtWidgets.QLabel("Campo:"))
        cmd.addWidget(self.field_combo)
        cmd.addWidget(QtWidgets.QLabel("Valore:"))
        cmd.addWidget(self.value_edit, 1)
        cmd.addWidget(self.like_check)
        cmd.addWidget(del_match_btn)
        cmd.addSpacing(20)
        cmd.addWidget(del_sel_btn)
        cmd.addStretch(1)
        cmd.addWidget(export_btn)
        cmd.addWidget(vacuum_btn)
        cmd.addWidget(refresh_btn)

        layout.addLayout(cmd)

        # Tabella
        self.table = QtWidgets.QTableWidget()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.table, 1)

        # Pulsanti fondo
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.load_table()

    def load_table(self):
        rows = self.db.fetch_all(order_by="path")
        headers = ['ID', 'Path', 'Genres', 'Year', 'Directors', 'Plot', 'Actors', 'Duration', 'Rating', 'Poster', 'MTime']
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(row['id'])))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(row['path'] or ''))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(row['genres'] or ''))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(row['year'] or ''))
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(row['directors'] or ''))
            self.table.setItem(r, 5, QtWidgets.QTableWidgetItem(row['plot'] or ''))
            self.table.setItem(r, 6, QtWidgets.QTableWidgetItem(row['actors'] or ''))
            self.table.setItem(r, 7, QtWidgets.QTableWidgetItem(row['duration'] or ''))
            self.table.setItem(r, 8, QtWidgets.QTableWidgetItem(row['rating'] or ''))
            self.table.setItem(r, 9, QtWidgets.QTableWidgetItem(row['poster'] or ''))
            self.table.setItem(r, 10, QtWidgets.QTableWidgetItem(str(row['mtime']) if row['mtime'] is not None else ''))
        self.table.resizeColumnsToContents()

    def _selected_ids(self):
        ids = set()
        for it in self.table.selectedItems():
            if it.column() == 0:
                try:
                    ids.add(int(it.text()))
                except Exception:
                    pass
        # se l’utente seleziona intere righe, potremmo non avere colonna 0 nella selezione:
        if not ids:
            for r in {i.row() for i in self.table.selectedItems()}:
                item = self.table.item(r, 0)
                if item:
                    try:
                        ids.add(int(item.text()))
                    except Exception:
                        pass
        return list(ids)

    def delete_selected(self):
        ids = self._selected_ids()
        if not ids:
            QtWidgets.QMessageBox.information(self, "Info", "Nessuna riga selezionata.")
            return
        if QtWidgets.QMessageBox.question(self, "Conferma",
                                          f"Eliminare {len(ids)} record selezionati?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            count = self.db.delete_ids(ids)
            self.load_table()
            QtWidgets.QMessageBox.information(self, "Eliminazione", f"Eliminati {count} record.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Errore", f"Impossibile eliminare: {e}")

    def delete_matching(self):
        field = self.field_combo.currentText()
        value = self.value_edit.text().strip()
        if not value:
            QtWidgets.QMessageBox.information(self, "Info", "Inserisci un valore.")
            return
        use_like = self.like_check.isChecked()
        shown = value if not use_like else (value if '%' in value or '_' in value else f"%{value}%")
        if QtWidgets.QMessageBox.question(self, "Conferma",
                                          f"Eliminare i record dove {field} "
                                          f"{'LIKE' if use_like else '='} '{shown}' ?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            count = self.db.delete_by_field_match(field, shown, use_like=True if use_like else False)
            self.load_table()
            QtWidgets.QMessageBox.information(self, "Eliminazione", f"Eliminati {count} record.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Errore", f"Impossibile eliminare: {e}")

    def export_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Salva CSV', '', 'CSV Files (*.csv)')
        if not path:
            return
        try:
            rows = self.db.fetch_all(order_by="path")
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['id', 'path', 'genres', 'year', 'directors', 'plot', 'actors', 'duration', 'rating', 'poster', 'mtime'])
                for r in rows:
                    w.writerow([r['id'], r['path'], r['genres'], r['year'], r['directors'], r['plot'],
                                r['actors'], r['duration'], r['rating'], r['poster'], r['mtime']])
            QtWidgets.QMessageBox.information(self, "Esporta", f"Esportati {len(rows)} record in {path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Errore", f"Impossibile esportare: {e}")

    def do_vacuum(self):
        try:
            self.db.vacuum()
            QtWidgets.QMessageBox.information(self, "VACUUM", "Operazione completata.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Errore", f"VACUUM fallito: {e}")


# --------------------------- Finestra principale ---------------------------
class VideoBrowser(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.db = DBManager()
        self.parser = NFOParser()
        self.stop_scan = False
        self.temp_images = []   # temp files da pulire
        self.last_playlist_paths = []  # ultima playlist
        self.init_ui()
        self.load_filters()
        self.load_data()

    def init_ui(self):
        self.setWindowTitle('Video Browser (kodi_videos.db)')
        main_layout = QtWidgets.QHBoxLayout(self)

        left_vlayout = QtWidgets.QVBoxLayout()

        # Top: selezione cartella + scan + gestione DB
        top_scan_layout = QtWidgets.QHBoxLayout()
        self.folder_edit = QtWidgets.QLineEdit()
        self.folder_edit.setPlaceholderText('Seleziona cartella da scansionare…')
        browse_btn = QtWidgets.QPushButton('Sfoglia')
        browse_btn.clicked.connect(self.browse_folder)
        scan_btn = QtWidgets.QPushButton('Scansione (ricorsiva)')
        scan_btn.clicked.connect(self.scan_videos)
        manage_btn = QtWidgets.QPushButton('Gestione DB…')
        manage_btn.clicked.connect(self.open_db_management)
        top_scan_layout.addWidget(self.folder_edit)
        top_scan_layout.addWidget(browse_btn)
        top_scan_layout.addWidget(scan_btn)
        top_scan_layout.addWidget(manage_btn)
        left_vlayout.addLayout(top_scan_layout)

        # Filtri
        filter_layout = QtWidgets.QHBoxLayout()

        gen_layout = QtWidgets.QVBoxLayout()
        gen_layout.addWidget(QtWidgets.QLabel('Generi'))
        self.genre_list = QtWidgets.QListWidget()
        self.genre_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        gen_layout.addWidget(self.genre_list)
        filter_layout.addLayout(gen_layout)

        year_layout = QtWidgets.QVBoxLayout()
        year_layout.addWidget(QtWidgets.QLabel('Anni'))
        self.year_list = QtWidgets.QListWidget()
        self.year_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        year_layout.addWidget(self.year_list)
        filter_layout.addLayout(year_layout)

        dir_layout = QtWidgets.QVBoxLayout()
        dir_layout.addWidget(QtWidgets.QLabel('Registi'))
        self.director_list = QtWidgets.QListWidget()
        self.director_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        dir_layout.addWidget(self.director_list)
        filter_layout.addLayout(dir_layout)

        ctrl_layout = QtWidgets.QVBoxLayout()
        self.apply_btn = QtWidgets.QPushButton('Applica filtri')
        self.apply_btn.clicked.connect(self.load_data)
        self.refresh_filters_btn = QtWidgets.QPushButton('Aggiorna filtri')
        self.refresh_filters_btn.clicked.connect(self.load_filters)
        ctrl_layout.addWidget(self.apply_btn)
        ctrl_layout.addWidget(self.refresh_filters_btn)
        filter_layout.addLayout(ctrl_layout)

        left_vlayout.addLayout(filter_layout)

        # Tabella risultati
        self.table = QtWidgets.QTableWidget()
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        left_vlayout.addWidget(self.table)

        # Controlli inferiori
        bottom_layout = QtWidgets.QHBoxLayout()
        self.export_btn = QtWidgets.QPushButton('Esporta CSV (DB video)')
        self.export_btn.clicked.connect(self.export_csv)
        self.playlist_btn = QtWidgets.QPushButton('Crea Playlist M3U casuale')
        self.playlist_btn.clicked.connect(self.create_random_playlist)
        self.posterlist_btn = QtWidgets.QPushButton('Mostra locandina playlist')
        self.posterlist_btn.clicked.connect(self.show_last_playlist)
        bottom_layout.addWidget(self.export_btn)
        bottom_layout.addWidget(self.playlist_btn)
        bottom_layout.addWidget(self.posterlist_btn)
        left_vlayout.addLayout(bottom_layout)

        main_layout.addLayout(left_vlayout, 3)

        # Pannello destro: poster + dettagli
        right_panel = QtWidgets.QVBoxLayout()
        self.poster_label = QtWidgets.QLabel()
        self.poster_label.setFixedSize(360, 540)
        self.poster_label.setAlignment(QtCore.Qt.AlignCenter)
        self.poster_label.setStyleSheet("border: 1px solid #aaa; background: #222;")
        right_panel.addWidget(self.poster_label)

        self.details = QtWidgets.QTextEdit()
        self.details.setReadOnly(True)
        right_panel.addWidget(self.details)

        main_layout.addLayout(right_panel, 1)

        self.resize(1260, 780)

    # --- Azioni UI ---
    def open_db_management(self):
        dlg = DBManagementDialog(self.db, self)
        dlg.exec_()
        # ricarico eventuali cambiamenti
        self.load_filters()
        self.load_data()

    def browse_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Folder')
        if folder:
            self.folder_edit.setText(folder)

    def scan_videos(self):
        folder = self.folder_edit.text().strip()
        if not folder:
            QtWidgets.QMessageBox.warning(self, 'Info', 'Seleziona una cartella da scansionare.')
            return
        if not os.path.isdir(folder):
            QtWidgets.QMessageBox.warning(self, 'Info', 'Cartella non valida.')
            return

        video_files = []
        for root, _, files in os.walk(folder):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    vpath = os.path.join(root, f)
                    try:
                        vmtime = os.path.getmtime(vpath)
                    except Exception:
                        vmtime = None
                    nfo_path = os.path.splitext(vpath)[0] + '.nfo'
                    genres_s = ''
                    year = ''
                    directors_s = ''
                    plot = ''
                    actors_s = ''
                    duration = ''
                    rating = ''
                    poster = ''
                    if os.path.exists(nfo_path):
                        genres_s, year, directors_s, plot, actors_s, duration, rating, poster = self.parser.parse_video_info(nfo_path)
                    video_files.append((vpath, vmtime, genres_s, year, directors_s, plot, actors_s, duration, rating, poster))

        if not video_files:
            QtWidgets.QMessageBox.information(self, 'Info', 'Nessun file video trovato nella cartella.')
            return

        progress = ProgressDialog(self, maximum=len(video_files))
        progress.cancel_requested.connect(self.request_stop)
        progress.show()

        for i, (vpath, vmtime, genres_s, year, directors_s, plot, actors_s, duration, rating, poster) in enumerate(video_files, 1):
            if self.stop_scan or progress.canceled:
                break
            try:
                self.db.add_or_update_video(vpath, vmtime, genres_s, year, directors_s, plot, actors_s, duration, rating, poster)
            except Exception as e:
                print(f"DB error adding {vpath}: {e}")
            progress.update_progress(i)

        progress.close()
        self.stop_scan = False
        self.load_filters()
        self.load_data()
        QtWidgets.QMessageBox.information(self, 'Done', 'Scansione completata (o interrotta).')

    def request_stop(self):
        self.stop_scan = True

    def load_filters(self):
        self.genre_list.clear()
        self.year_list.clear()
        self.director_list.clear()

        try:
            genres = self.db.get_all_genres()
            for g in genres:
                self.genre_list.addItem(g)

            years = self.db.get_all_years()
            for y in years:
                self.year_list.addItem(str(y))

            directors = self.db.get_all_directors()
            for d in directors:
                self.director_list.addItem(d)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'DB Error', f'Errore caricamento filtri: {e}')

    def load_data(self):
        selected_genres = [i.text() for i in self.genre_list.selectedItems()]
        selected_years = [i.text() for i in self.year_list.selectedItems()]
        selected_directors = [i.text() for i in self.director_list.selectedItems()]

        try:
            rows = self.db.query_videos(genres=selected_genres or None,
                                        years=selected_years or None,
                                        directors=selected_directors or None,
                                        limit=10000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'DB Error', f'Errore query: {e}')
            return

        headers = ['Path', 'Genres', 'Year', 'Directors', 'Plot', 'Actors', 'Duration', 'Rating', 'Poster', 'MTime']
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(row['path']))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(row['genres'] or ''))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(row['year'] or ''))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(row['directors'] or ''))
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(row['plot'] or ''))
            self.table.setItem(r, 5, QtWidgets.QTableWidgetItem(row['actors'] or ''))
            self.table.setItem(r, 6, QtWidgets.QTableWidgetItem(row['duration'] or ''))
            self.table.setItem(r, 7, QtWidgets.QTableWidgetItem(row['rating'] or ''))
            self.table.setItem(r, 8, QtWidgets.QTableWidgetItem(row['poster'] or ''))
            self.table.setItem(r, 9, QtWidgets.QTableWidgetItem(str(row['mtime']) if row['mtime'] is not None else ''))

        self.table.resizeColumnsToContents()

    def export_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Salva CSV', '', 'CSV Files (*.csv)')
        if not path:
            return
        try:
            rows = self.db.query_videos(limit=1000000)
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Path', 'Genres', 'Year', 'Directors', 'Plot', 'Actors', 'Duration', 'Rating', 'Poster', 'MTime'])
                for r in rows:
                    writer.writerow([r['path'], r['genres'], r['year'], r['directors'], r['plot'],
                                     r['actors'], r['duration'], r['rating'], r['poster'], r['mtime']])
            QtWidgets.QMessageBox.information(self, 'Esporta', f'Esportati {len(rows)} record in {path}')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Errore', f'Impossibile esportare: {e}')

    def _items_from_paths(self, paths):
        items = []
        cur = self.db.conn.cursor()
        for p in paths:
            try:
                cur.execute("SELECT path, genres, year, directors, plot, actors, duration, rating, poster FROM videos WHERE path = ?", (p,))
                row = cur.fetchone()
                if row:
                    items.append({k: row[k] for k in row.keys()})
                else:
                    items.append({'path': p, 'genres': '', 'year': '', 'directors': '', 'plot': '', 'actors': '', 'duration': '', 'rating': '', 'poster': ''})
            except Exception:
                items.append({'path': p, 'genres': '', 'year': '', 'directors': '', 'plot': '', 'actors': '', 'duration': '', 'rating': '', 'poster': ''})
        return items

    def show_last_playlist(self):
        if not self.last_playlist_paths:
            QtWidgets.QMessageBox.information(self, 'Playlist', 'Nessuna playlist recente da mostrare.')
            return
        items = self._items_from_paths(self.last_playlist_paths)
        dlg = PlaylistPosterDialog(self, items)
        dlg.exec_()

    def create_random_playlist(self):
        visible_rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                visible_rows.append(item.text())

        if not visible_rows:
            QtWidgets.QMessageBox.warning(self, 'Warning', 'Nessun video visibile da aggiungere alla playlist.')
            return

        num, ok = QtWidgets.QInputDialog.getInt(self, 'Dimensione playlist', 'Numero di file:', 5, 1, len(visible_rows))
        if not ok:
            return

        selection = random.sample(visible_rows, min(num, len(visible_rows)))
        self.last_playlist_paths = selection[:]  # remember

        items = self._items_from_paths(selection)
        dlg = PlaylistPosterDialog(self, items)
        dlg.exec_()

        playlist_path = os.path.join(str(Path.home()), f'random_playlist_{int(time.time())}.m3u')
        try:
            with open(playlist_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write('#EXTM3U\n')
                for path in selection:
                    f.write(path + '\n')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Errore', f'Non posso creare la playlist: {e}')
            return

        try:
            if os.name == 'nt':
                subprocess.call(['taskkill', '/IM', 'vlc.exe', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.call(['pkill', '-f', 'vlc'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        vlc_exec = shutil.which('vlc')
        if not vlc_exec and os.name == 'nt':
            possible = [r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"]
            for p in possible:
                if os.path.exists(p):
                    vlc_exec = p
                    break

        try:
            if vlc_exec:
                subprocess.Popen([vlc_exec, playlist_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                QtWidgets.QMessageBox.information(self, 'Playlist creata', f'Playlist creata e avviata: {playlist_path}')
            else:
                QtWidgets.QMessageBox.information(self, 'Playlist creata', f'Playlist creata: {playlist_path} \nVLC non trovato sul sistema.')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Errore', f'Errore avviando VLC: {e}')

    def _load_image(self, poster):
        if not poster:
            self.poster_label.clear()
            return
        if os.path.exists(poster):
            pix = QtGui.QPixmap(poster)
        else:
            try:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(poster)[1] if '.' in poster else '.img')
                tmp.close()
                urllib.request.urlretrieve(poster, tmp.name)
                self.temp_images.append(tmp.name)
                pix = QtGui.QPixmap(tmp.name)
            except Exception:
                pix = None
        if pix and not pix.isNull():
            scaled = pix.scaled(self.poster_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.poster_label.setPixmap(scaled)
        else:
            self.poster_label.clear()

    def on_selection_changed(self):
        sel = self.table.selectedItems()
        if not sel:
            self.poster_label.clear()
            self.details.clear()
            return
        row = sel[0].row()
        path = self.table.item(row, 0).text()
        genres = self.table.item(row, 1).text()
        year = self.table.item(row, 2).text()
        directors = self.table.item(row, 3).text()
        plot = self.table.item(row, 4).text()
        actors = self.table.item(row, 5).text()
        duration = self.table.item(row, 6).text()
        rating = self.table.item(row, 7).text()
        poster = self.table.item(row, 8).text()

        self._load_image(poster)

        info = []
        info.append(f"Path: {path}")
        if year:
            info.append(f"Year: {year}")
        if directors:
            info.append(f"Directors: {directors}")
        if actors:
            info.append(f"Cast: {actors}")
        if duration:
            info.append(f"Duration: {duration}")
        if rating:
            info.append(f"Rating: {rating}")
        if genres:
            info.append(f"Genres: {genres}")
        if plot:
            info.append('\nPlot:\n' + plot)

        self.details.setPlainText('\n'.join(info))

    def closeEvent(self, event):
        try:
            for t in getattr(self, 'temp_images', []):
                try:
                    os.unlink(t)
                except Exception:
                    pass
            self.db.close()
        finally:
            event.accept()


# --------------------------- Avvio app ---------------------------
if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = VideoBrowser()
    w.show()
    sys.exit(app.exec_())
