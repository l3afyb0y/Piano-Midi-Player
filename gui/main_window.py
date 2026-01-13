"""Main application window."""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QSlider, QLabel, QPushButton, QComboBox,
    QFileDialog, QSpinBox, QListWidget, QListWidgetItem, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from gui.keyboard_widget import KeyboardWidget
from gui.falling_notes_widget import FallingNotesWidget, NoteEvent, SustainEvent


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals for thread-safe communication
    volume_changed = pyqtSignal(float)
    synth_changed = pyqtSignal(str)
    soundfont_loaded = pyqtSignal(str)
    record_toggled = pyqtSignal(bool)
    save_wav = pyqtSignal(str)
    save_midi = pyqtSignal(str)
    open_midi_file = pyqtSignal(str)
    save_midi_file = pyqtSignal(str)
    midi_folder_changed = pyqtSignal(str)
    midi_library_refresh = pyqtSignal()
    midi_files_dropped = pyqtSignal(list)
    play_recording = pyqtSignal()  # Request to play back the recording
    metronome_toggled = pyqtSignal(bool)  # Metronome on/off
    metronome_bpm_changed = pyqtSignal(int)  # BPM changed

    # Dark mode stylesheet
    DARK_STYLE = """
        QMainWindow, QWidget {
            background-color: #1e1e1e;
            color: #e0e0e0;
        }
        QGroupBox {
            border: 1px solid #3a3a3a;
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 8px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: #a0a0a0;
        }
        QPushButton {
            background-color: #2d2d2d;
            border: 1px solid #3a3a3a;
            border-radius: 4px;
            padding: 6px 12px;
            color: #e0e0e0;
        }
        QPushButton:hover {
            background-color: #3a3a3a;
        }
        QPushButton:pressed {
            background-color: #4a4a4a;
        }
        QPushButton:checked {
            background-color: #c0392b;
            border-color: #e74c3c;
        }
        QPushButton:disabled {
            background-color: #1a1a1a;
            color: #606060;
        }
        QSlider::groove:horizontal {
            border: 1px solid #3a3a3a;
            height: 6px;
            background: #2d2d2d;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #5dade2;
            border: 1px solid #3498db;
            width: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }
        QSlider::sub-page:horizontal {
            background: #3498db;
            border-radius: 3px;
        }
        QComboBox {
            background-color: #2d2d2d;
            border: 1px solid #3a3a3a;
            border-radius: 4px;
            padding: 4px 8px;
            color: #e0e0e0;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox QAbstractItemView {
            background-color: #2d2d2d;
            selection-background-color: #3498db;
        }
        QLabel {
            color: #e0e0e0;
        }
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Piano Player")
        self.setMinimumSize(500, 300)

        self._recording = False
        self._record_time = 0
        self._midi_file_path: str | None = None
        self._midi_dir: str | None = None

        self._setup_ui()
        self._setup_timer()
        self._apply_dark_mode()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        """Create UI elements."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Status bar at top
        status_group = QGroupBox("Status")
        status_layout = QHBoxLayout(status_group)

        self._midi_status = QLabel("MIDI: Not connected")
        status_layout.addWidget(self._midi_status)

        self._audio_status = QLabel("Audio: Ready")
        status_layout.addWidget(self._audio_status)

        self._sustain_status = QLabel("Sustain: Off")
        status_layout.addWidget(self._sustain_status)

        self._notes_status = QLabel("Notes: 0")
        status_layout.addWidget(self._notes_status)

        layout.addWidget(status_group)

        # Controls row: Audio + Synthesizer
        top_row = QHBoxLayout()
        layout.addLayout(top_row)

        # Audio group
        audio_group = QGroupBox("Audio")
        audio_layout = QHBoxLayout(audio_group)

        audio_layout.addWidget(QLabel("Volume:"))
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        audio_layout.addWidget(self._volume_slider)

        self._volume_label = QLabel("80%")
        self._volume_label.setMinimumWidth(40)
        audio_layout.addWidget(self._volume_label)

        top_row.addWidget(audio_group)

        # Synthesizer group
        synth_group = QGroupBox("Synthesizer")
        synth_layout = QVBoxLayout(synth_group)

        self._synth_combo = QComboBox()
        self._synth_combo.addItems(["Simple Synth", "SoundFont"])
        self._synth_combo.currentTextChanged.connect(self._on_synth_changed)
        synth_layout.addWidget(self._synth_combo)

        self._soundfont_btn = QPushButton("Load SoundFont...")
        self._soundfont_btn.clicked.connect(self._on_load_soundfont)
        self._soundfont_btn.setEnabled(False)
        synth_layout.addWidget(self._soundfont_btn)

        # Metronome controls
        metro_layout = QHBoxLayout()
        self._metro_btn = QPushButton("Metronome")
        self._metro_btn.setCheckable(True)
        self._metro_btn.clicked.connect(self._on_metronome_toggled)
        metro_layout.addWidget(self._metro_btn)

        self._bpm_spin = QSpinBox()
        self._bpm_spin.setRange(20, 300)
        self._bpm_spin.setValue(120)
        self._bpm_spin.setSuffix(" BPM")
        self._bpm_spin.valueChanged.connect(self._on_bpm_changed)
        metro_layout.addWidget(self._bpm_spin)

        synth_layout.addLayout(metro_layout)

        top_row.addWidget(synth_group)

        # MIDI file group
        midi_file_group = QGroupBox("MIDI File")
        midi_file_layout = QVBoxLayout(midi_file_group)

        self._open_midi_btn = QPushButton("Open MIDI...")
        self._open_midi_btn.clicked.connect(self._on_open_midi)
        midi_file_layout.addWidget(self._open_midi_btn)

        self._save_midi_file_btn = QPushButton("Save MIDI...")
        self._save_midi_file_btn.clicked.connect(self._on_save_midi_file)
        self._save_midi_file_btn.setEnabled(False)
        midi_file_layout.addWidget(self._save_midi_file_btn)

        self._midi_file_label = QLabel("No MIDI loaded")
        self._midi_file_label.setMinimumWidth(120)
        self._midi_file_label.setWordWrap(True)
        midi_file_layout.addWidget(self._midi_file_label)

        top_row.addWidget(midi_file_group)

        # MIDI library group
        library_group = QGroupBox("MIDI Library")
        library_layout = QVBoxLayout(library_group)

        library_controls = QHBoxLayout()
        self._midi_folder_btn = QPushButton("Set MIDI Folder...")
        self._midi_folder_btn.clicked.connect(self._on_set_midi_folder)
        library_controls.addWidget(self._midi_folder_btn)

        self._midi_refresh_btn = QPushButton("Refresh")
        self._midi_refresh_btn.clicked.connect(self._on_refresh_library)
        library_controls.addWidget(self._midi_refresh_btn)
        library_layout.addLayout(library_controls)

        self._midi_folder_label = QLabel("Folder: Not set")
        self._midi_folder_label.setWordWrap(True)
        library_layout.addWidget(self._midi_folder_label)

        self._midi_list = QListWidget()
        self._midi_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._midi_list.itemDoubleClicked.connect(self._on_midi_item_activated)
        self._midi_list.setMinimumHeight(100)
        library_layout.addWidget(self._midi_list)

        layout.addWidget(library_group)

        # Recording group
        record_group = QGroupBox("Recording")
        record_main_layout = QVBoxLayout(record_group)

        # Controls row
        record_controls = QHBoxLayout()
        record_main_layout.addLayout(record_controls)

        self._record_btn = QPushButton("Record")
        self._record_btn.setCheckable(True)
        self._record_btn.clicked.connect(self._on_record_toggled)
        record_controls.addWidget(self._record_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._on_stop_recording)
        self._stop_btn.setEnabled(False)
        record_controls.addWidget(self._stop_btn)

        self._time_label = QLabel("00:00")
        self._time_label.setMinimumWidth(50)
        record_controls.addWidget(self._time_label)

        self._save_wav_btn = QPushButton("Save WAV")
        self._save_wav_btn.clicked.connect(self._on_save_wav)
        self._save_wav_btn.setEnabled(False)
        record_controls.addWidget(self._save_wav_btn)

        self._save_midi_btn = QPushButton("Save MIDI")
        self._save_midi_btn.clicked.connect(self._on_save_midi)
        self._save_midi_btn.setEnabled(False)
        record_controls.addWidget(self._save_midi_btn)

        self._play_btn = QPushButton("Play")
        self._play_btn.clicked.connect(self._on_play_recording)
        self._play_btn.setEnabled(False)
        record_controls.addWidget(self._play_btn)

        # Timeline slider row
        timeline_layout = QHBoxLayout()
        self._timeline_label = QLabel("0:00")
        self._timeline_label.setMinimumWidth(40)
        timeline_layout.addWidget(self._timeline_label)

        self._timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self._timeline_slider.setRange(0, 1000)
        self._timeline_slider.setValue(0)
        self._timeline_slider.sliderMoved.connect(self._on_timeline_seek)
        self._timeline_slider.sliderPressed.connect(self._on_timeline_pressed)
        self._timeline_slider.sliderReleased.connect(self._on_timeline_released)
        timeline_layout.addWidget(self._timeline_slider)

        self._duration_label = QLabel("0:00")
        self._duration_label.setMinimumWidth(40)
        timeline_layout.addWidget(self._duration_label)

        record_main_layout.addLayout(timeline_layout)

        layout.addWidget(record_group)

        # Falling notes visualization (above keyboard for visual flow)
        notes_group = QGroupBox("Piano Roll")
        notes_layout = QVBoxLayout(notes_group)
        self._falling_notes = FallingNotesWidget()
        notes_layout.addWidget(self._falling_notes)
        layout.addWidget(notes_group, stretch=1)  # Let this expand

        # Keyboard visualization (below falling notes)
        keyboard_group = QGroupBox("Keyboard")
        keyboard_layout = QVBoxLayout(keyboard_group)
        self._keyboard = KeyboardWidget()
        keyboard_layout.addWidget(self._keyboard)
        layout.addWidget(keyboard_group)

        # Connect falling notes time updates and keyboard visualization
        self._falling_notes.time_changed.connect(self._on_time_changed)
        self._falling_notes.note_triggered.connect(self._keyboard.note_on)
        self._falling_notes.note_released.connect(self._keyboard.note_off)
        self._falling_notes.events_changed.connect(self._on_events_changed)
        self._slider_dragging = False

    def _setup_timer(self):
        """Setup timer for recording time display."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_time)

    def _apply_dark_mode(self):
        """Apply dark mode stylesheet."""
        self.setStyleSheet(self.DARK_STYLE)

    def _on_volume_changed(self, value: int):
        self._volume_label.setText(f"{value}%")
        self.volume_changed.emit(value / 100.0)

    def _on_synth_changed(self, text: str):
        self._soundfont_btn.setEnabled(text == "SoundFont")
        self.synth_changed.emit(text)

    def _on_load_soundfont(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load SoundFont", "", "SoundFont Files (*.sf2)"
        )
        if path:
            self.soundfont_loaded.emit(path)

    def _on_open_midi(self):
        start_dir = self._midi_dir or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open MIDI", start_dir, "MIDI Files (*.mid *.midi)"
        )
        if path:
            self.open_midi_file.emit(path)

    def _on_set_midi_folder(self):
        start_dir = self._midi_dir or ""
        path = QFileDialog.getExistingDirectory(self, "Select MIDI Folder", start_dir)
        if path:
            self.midi_folder_changed.emit(path)

    def _on_refresh_library(self):
        self.midi_library_refresh.emit()

    def _on_midi_item_activated(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.open_midi_file.emit(path)

    def _on_save_midi_file(self):
        default_name = "edited.mid"
        if self._midi_file_path:
            base = os.path.splitext(os.path.basename(self._midi_file_path))[0]
            default_name = f"{base}-edited.mid"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save MIDI", default_name, "MIDI Files (*.mid *.midi)"
        )
        if path:
            self.save_midi_file.emit(path)

    def _on_metronome_toggled(self, checked: bool):
        self._metro_btn.setText("Metronome On" if checked else "Metronome")
        self.metronome_toggled.emit(checked)

    def _on_bpm_changed(self, value: int):
        self.metronome_bpm_changed.emit(value)

    def _on_record_toggled(self, checked: bool):
        self._set_recording_state(checked)
        self.record_toggled.emit(checked)

    def _on_stop_recording(self):
        self._record_btn.setChecked(False)

    def _on_play_recording(self):
        if self._falling_notes.is_playing():
            self.stop_playback()
            return

        if self._falling_notes.has_events():
            self.start_playback()
            return

        self.play_recording.emit()

    def _on_save_wav(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save WAV", "recording.wav", "WAV Files (*.wav)"
        )
        if path:
            self.save_wav.emit(path)

    def _on_save_midi(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save MIDI", "recording.mid", "MIDI Files (*.mid)"
        )
        if path:
            self.save_midi.emit(path)

    def _update_time(self):
        self._record_time += 1
        mins = self._record_time // 60
        secs = self._record_time % 60
        self._time_label.setText(f"{mins:02d}:{secs:02d}")

    def _set_recording_state(self, recording: bool):
        """Update recording UI state."""
        self._recording = recording
        self._record_btn.setText("Recording..." if recording else "Record")
        self._stop_btn.setEnabled(recording)
        if recording:
            self._record_time = 0
            self._time_label.setText("00:00")
            self._timer.start(1000)
            self._save_wav_btn.setEnabled(False)
            self._save_midi_btn.setEnabled(False)
            self._play_btn.setEnabled(False)
        else:
            self._timer.stop()
            self._save_wav_btn.setEnabled(True)
            self._save_midi_btn.setEnabled(True)
            self._play_btn.setEnabled(True)

    def _on_timeline_seek(self, value: int):
        """Handle timeline slider drag."""
        duration = self._falling_notes.get_duration()
        if duration > 0:
            time_seconds = (value / 1000.0) * duration
            self._falling_notes.seek(time_seconds)

    def _on_timeline_pressed(self):
        """Handle slider press - pause updates."""
        self._slider_dragging = True

    def _on_timeline_released(self):
        """Handle slider release - resume updates."""
        self._slider_dragging = False
        self._on_time_changed(self._falling_notes.get_current_time())

    def _on_time_changed(self, time_seconds: float):
        """Update slider and label when playback time changes."""
        if self._slider_dragging:
            return  # Don't update while user is dragging

        duration = self._falling_notes.get_duration()
        if duration > 0:
            slider_value = int((time_seconds / duration) * 1000)
            self._timeline_slider.setValue(slider_value)

        mins = int(time_seconds) // 60
        secs = int(time_seconds) % 60
        self._timeline_label.setText(f"{mins}:{secs:02d}")

    def _on_events_changed(self):
        duration = self._falling_notes.get_duration()
        self._duration_label.setText(self._format_time(duration))
        has_events = duration > 0
        self._play_btn.setEnabled(has_events)
        self._save_midi_file_btn.setEnabled(has_events)
        if not has_events:
            self._timeline_slider.setValue(0)
            self._timeline_label.setText("0:00")

    @staticmethod
    def _is_midi_file(path: str) -> bool:
        return path.lower().endswith((".mid", ".midi"))

    def _midi_paths_from_urls(self, urls) -> list[str]:
        paths: list[str] = []
        for url in urls:
            if url.isLocalFile():
                path = url.toLocalFile()
                if path and self._is_midi_file(path):
                    paths.append(path)
        return paths

    def _format_time(self, seconds: float) -> str:
        """Format seconds as M:SS."""
        mins = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{mins}:{secs:02d}"

    # Public methods to update status
    def set_synth_selection(self, name: str):
        """Set synth selection without emitting change signals."""
        index = self._synth_combo.findText(name)
        if index < 0:
            return
        self._synth_combo.blockSignals(True)
        self._synth_combo.setCurrentIndex(index)
        self._synth_combo.blockSignals(False)
        self._soundfont_btn.setEnabled(name == "SoundFont")

    def set_midi_status(self, connected: bool, name: str = ""):
        if connected:
            self._midi_status.setText(f"MIDI: {name}")
        else:
            self._midi_status.setText("MIDI: Not connected")

    def set_sustain_status(self, on: bool):
        self._sustain_status.setText(f"Sustain: {'On' if on else 'Off'}")

    def set_notes_count(self, count: int):
        self._notes_status.setText(f"Notes: {count}")

    def set_midi_file_info(self, path: str | None):
        self._midi_file_path = path
        if path:
            name = os.path.basename(path)
            self._midi_file_label.setText(f"Loaded: {name}")
        else:
            self._midi_file_label.setText("No MIDI loaded")

    def set_midi_folder(self, path: str | None):
        self._midi_dir = path
        if path:
            self._midi_folder_label.setText(f"Folder: {path}")
        else:
            self._midi_folder_label.setText("Folder: Not set")

    def set_midi_library(self, paths: list[str]):
        self._midi_list.clear()
        for path in paths:
            name = os.path.basename(path)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self._midi_list.addItem(item)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            paths = self._midi_paths_from_urls(event.mimeData().urls())
            if paths:
                event.acceptProposedAction()
                return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            paths = self._midi_paths_from_urls(event.mimeData().urls())
            if paths:
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        paths = self._midi_paths_from_urls(event.mimeData().urls())
        if not paths:
            event.ignore()
            return
        self.midi_files_dropped.emit(paths)
        event.acceptProposedAction()

    def keyboard_note_on(self, note: int, velocity: int):
        """Update keyboard visualization on note press."""
        self._keyboard.note_on(note, velocity)

    def keyboard_note_off(self, note: int):
        """Update keyboard visualization on note release."""
        self._keyboard.note_off(note)

    def load_recording(self, events: list[NoteEvent], sustain_events: list[SustainEvent] | None = None):
        """Load recorded notes into the falling notes display."""
        self._falling_notes.load_events(events, sustain_events)
        self._timeline_slider.setValue(0)
        self._timeline_label.setText("0:00")
        self._on_events_changed()

    def start_playback(self):
        """Start falling notes playback."""
        self._falling_notes.play()
        self._play_btn.setText("Stop" if self._falling_notes.is_playing() else "Play")

    def stop_playback(self):
        """Stop falling notes playback."""
        self._falling_notes.stop()
        self._play_btn.setText("Play")

    @property
    def falling_notes(self) -> FallingNotesWidget:
        """Access to falling notes widget for signal connections."""
        return self._falling_notes
