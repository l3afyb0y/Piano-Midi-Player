"""Main application window."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QSlider, QLabel, QPushButton, QComboBox,
    QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals for thread-safe communication
    volume_changed = pyqtSignal(float)
    synth_changed = pyqtSignal(str)
    soundfont_loaded = pyqtSignal(str)
    record_toggled = pyqtSignal(bool)
    save_wav = pyqtSignal(str)
    save_midi = pyqtSignal(str)

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

        self._setup_ui()
        self._setup_timer()
        self._apply_dark_mode()

    def _setup_ui(self):
        """Create UI elements."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top row: Audio + Synthesizer
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

        top_row.addWidget(synth_group)

        # Recording group
        record_group = QGroupBox("Recording")
        record_layout = QHBoxLayout(record_group)

        self._record_btn = QPushButton("Record")
        self._record_btn.setCheckable(True)
        self._record_btn.clicked.connect(self._on_record_toggled)
        record_layout.addWidget(self._record_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._on_stop_recording)
        self._stop_btn.setEnabled(False)
        record_layout.addWidget(self._stop_btn)

        self._time_label = QLabel("00:00")
        self._time_label.setMinimumWidth(50)
        record_layout.addWidget(self._time_label)

        self._save_wav_btn = QPushButton("Save WAV")
        self._save_wav_btn.clicked.connect(self._on_save_wav)
        self._save_wav_btn.setEnabled(False)
        record_layout.addWidget(self._save_wav_btn)

        self._save_midi_btn = QPushButton("Save MIDI")
        self._save_midi_btn.clicked.connect(self._on_save_midi)
        self._save_midi_btn.setEnabled(False)
        record_layout.addWidget(self._save_midi_btn)

        layout.addWidget(record_group)

        # Status group
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

        # Add stretch to push everything up
        layout.addStretch()

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

    def _on_record_toggled(self, checked: bool):
        self._recording = checked
        self._record_btn.setText("Recording..." if checked else "Record")
        self._stop_btn.setEnabled(checked)
        if checked:
            self._record_time = 0
            self._timer.start(1000)
        self.record_toggled.emit(checked)

    def _on_stop_recording(self):
        self._record_btn.setChecked(False)
        self._on_record_toggled(False)
        self._timer.stop()
        self._save_wav_btn.setEnabled(True)
        self._save_midi_btn.setEnabled(True)

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

    # Public methods to update status
    def set_midi_status(self, connected: bool, name: str = ""):
        if connected:
            self._midi_status.setText(f"MIDI: {name}")
        else:
            self._midi_status.setText("MIDI: Not connected")

    def set_sustain_status(self, on: bool):
        self._sustain_status.setText(f"Sustain: {'On' if on else 'Off'}")

    def set_notes_count(self, count: int):
        self._notes_status.setText(f"Notes: {count}")
