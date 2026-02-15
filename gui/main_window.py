"""Main application window."""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QSlider, QLabel, QPushButton, QComboBox,
    QFileDialog, QSpinBox, QListWidget, QListWidgetItem, QAbstractItemView,
    QCheckBox, QSplitter, QAbstractSpinBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from gui.keyboard_widget import KeyboardWidget
from gui.falling_notes_widget import FallingNotesWidget, NoteEvent, SustainEvent
from gui.theme import APP_STYLE


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals for thread-safe communication
    volume_changed = pyqtSignal(float)
    synth_changed = pyqtSignal(str)
    instrument_changed = pyqtSignal(str)
    soundfont_loaded = pyqtSignal(str)
    soundfont_selected = pyqtSignal(str)
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
    count_in_enabled_changed = pyqtSignal(bool)
    count_in_beats_changed = pyqtSignal(int)
    snap_enabled_changed = pyqtSignal(bool)
    grid_enabled_changed = pyqtSignal(bool)
    snap_division_changed = pyqtSignal(int)
    midi_input_changed = pyqtSignal(str)
    audio_output_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Piano Player")
        self.setMinimumSize(900, 680)

        self._recording = False
        self._count_in_active = False
        self._record_time = 0
        self._midi_file_path: str | None = None
        self._midi_dir: str | None = None
        self._instrument_soundfonts: dict[str, str] = {}
        self._instrument_soundfont_options: dict[str, list[tuple[str, str]]] = {}
        self._instrument_selected_soundfont: dict[str, str | None] = {}

        self._setup_ui()
        self._setup_timer()
        self._apply_dark_mode()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        """Create UI elements."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(10)
        splitter.setOpaqueResize(True)
        splitter.setChildrenCollapsible(True)
        layout.addWidget(splitter, stretch=1)
        self._main_splitter = splitter
        self._default_splitter_sizes = [260, 420, 210]

        top_controls = QWidget()
        top_controls.setMinimumHeight(0)
        top_layout = QVBoxLayout(top_controls)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_layout.addLayout(top_row)

        synth_group = QGroupBox("Synthesizer")
        synth_layout = QVBoxLayout(synth_group)

        self._synth_combo = QComboBox()
        self._synth_combo.addItems(["Simple Synth", "SoundFont"])
        self._synth_combo.currentTextChanged.connect(self._on_synth_changed)
        synth_layout.addWidget(self._synth_combo)

        instrument_row = QHBoxLayout()
        instrument_row.addWidget(QLabel("Instrument:"))
        self._instrument_combo = QComboBox()
        self._instrument_combo.addItems(["Piano", "Guitar"])
        self._instrument_combo.currentTextChanged.connect(self._on_instrument_changed)
        instrument_row.addWidget(self._instrument_combo)
        synth_layout.addLayout(instrument_row)

        soundfont_row = QHBoxLayout()
        soundfont_row.addWidget(QLabel("SoundFont:"))
        self._soundfont_combo = QComboBox()
        self._soundfont_combo.currentIndexChanged.connect(self._on_soundfont_selected)
        soundfont_row.addWidget(self._soundfont_combo)
        synth_layout.addLayout(soundfont_row)

        self._soundfont_btn = QPushButton("Load SoundFont...")
        self._soundfont_btn.clicked.connect(self._on_load_soundfont)
        self._soundfont_btn.setEnabled(False)
        synth_layout.addWidget(self._soundfont_btn)
        self._soundfont_path_label = QLabel("Piano SF2: auto/default")
        self._soundfont_path_label.setWordWrap(True)
        synth_layout.addWidget(self._soundfont_path_label)

        metro_layout = QHBoxLayout()
        self._metro_btn = QPushButton("Metronome")
        self._metro_btn.setCheckable(True)
        self._metro_btn.clicked.connect(self._on_metronome_toggled)
        metro_layout.addWidget(self._metro_btn)

        self._bpm_spin = QSpinBox()
        self._bpm_spin.setRange(20, 300)
        self._bpm_spin.setValue(120)
        self._bpm_spin.setSuffix(" BPM")
        self._bpm_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self._bpm_spin.valueChanged.connect(self._on_bpm_changed)
        metro_layout.addWidget(self._bpm_spin)
        synth_layout.addLayout(metro_layout)

        count_in_layout = QHBoxLayout()
        self._count_in_check = QCheckBox("Count-in")
        self._count_in_check.toggled.connect(self._on_count_in_toggled)
        count_in_layout.addWidget(self._count_in_check)

        self._count_in_spin = QSpinBox()
        self._count_in_spin.setRange(1, 8)
        self._count_in_spin.setValue(4)
        self._count_in_spin.setSuffix(" beats")
        self._count_in_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self._count_in_spin.setEnabled(False)
        self._count_in_spin.valueChanged.connect(self._on_count_in_beats_changed)
        count_in_layout.addWidget(self._count_in_spin)
        count_in_layout.addStretch(1)
        synth_layout.addLayout(count_in_layout)

        top_row.addWidget(synth_group)

        midi_file_group = QGroupBox("MIDI Editor")
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
        top_row.setStretch(0, 2)
        top_row.setStretch(1, 2)

        library_group = QGroupBox("MIDI Library")
        library_layout = QVBoxLayout(library_group)

        library_controls = QHBoxLayout()
        self._midi_folder_btn = QPushButton("Set MIDI Folder...")
        self._midi_folder_btn.clicked.connect(self._on_set_midi_folder)
        library_controls.addWidget(self._midi_folder_btn)

        self._midi_refresh_btn = QPushButton("Refresh")
        self._midi_refresh_btn.clicked.connect(self._on_refresh_library)
        library_controls.addWidget(self._midi_refresh_btn)
        library_controls.addStretch(1)
        library_layout.addLayout(library_controls)

        self._midi_folder_label = QLabel("Folder: Not set")
        self._midi_folder_label.setWordWrap(True)
        library_layout.addWidget(self._midi_folder_label)

        self._midi_list = QListWidget()
        self._midi_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._midi_list.itemDoubleClicked.connect(self._on_midi_item_activated)
        self._midi_list.setMinimumHeight(0)
        library_layout.addWidget(self._midi_list)

        top_layout.addWidget(library_group)
        splitter.addWidget(top_controls)

        notes_group = QGroupBox("Piano Roll Editor")
        notes_layout = QVBoxLayout(notes_group)
        notes_layout.setContentsMargins(8, 16, 8, 0)
        notes_layout.setSpacing(6)

        roll_controls = QHBoxLayout()
        self._grid_check = QCheckBox("Grid")
        self._grid_check.setChecked(True)
        self._grid_check.toggled.connect(self._on_grid_toggled)
        roll_controls.addWidget(self._grid_check)

        self._snap_check = QCheckBox("Snap")
        self._snap_check.setChecked(True)
        self._snap_check.toggled.connect(self._on_snap_toggled)
        roll_controls.addWidget(self._snap_check)

        self._snap_combo = QComboBox()
        snap_options = [("1/4", 1), ("1/8", 2), ("1/16", 4), ("1/32", 8)]
        for label, value in snap_options:
            self._snap_combo.addItem(label, value)
        self._snap_combo.setCurrentIndex(2)
        self._snap_combo.currentIndexChanged.connect(self._on_snap_division_changed)
        roll_controls.addWidget(self._snap_combo)
        roll_controls.addStretch(1)
        notes_layout.addLayout(roll_controls)

        self._falling_notes = FallingNotesWidget()
        self._falling_notes.setMinimumHeight(140)
        self._falling_notes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._falling_notes.set_bpm(self._bpm_spin.value())
        self._falling_notes.set_snap_enabled(self._snap_check.isChecked())
        self._falling_notes.set_grid_enabled(self._grid_check.isChecked())
        self._falling_notes.set_snap_division(self._snap_combo.currentData())
        notes_layout.addWidget(self._falling_notes)

        roll_container = QWidget()
        roll_container.setMinimumHeight(180)
        roll_layout = QVBoxLayout(roll_container)
        roll_layout.setContentsMargins(0, 0, 0, 0)
        roll_layout.setSpacing(0)
        roll_layout.addWidget(notes_group, stretch=1)
        self._keyboard = KeyboardWidget()
        self._keyboard.setMinimumHeight(72)
        self._keyboard.setMaximumHeight(112)
        roll_layout.addWidget(self._keyboard)
        splitter.addWidget(roll_container)

        lower_panel = QWidget()
        lower_panel.setMinimumHeight(0)
        lower_layout = QVBoxLayout(lower_panel)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(10)

        record_group = QGroupBox("Transport / Recording")
        record_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        record_main_layout = QVBoxLayout(record_group)

        record_controls = QHBoxLayout()
        record_main_layout.addLayout(record_controls)

        self._record_btn = QPushButton("Record")
        self._record_btn.setCheckable(True)
        self._record_btn.toggled.connect(self._on_record_toggled)
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
        lower_layout.addWidget(record_group)

        status_group = QGroupBox("Status")
        status_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(8)

        status_row = QHBoxLayout()
        self._midi_status = QLabel("Input: Not connected")
        status_row.addWidget(self._midi_status)
        self._audio_status = QLabel("Audio: Default output")
        status_row.addWidget(self._audio_status)
        self._sustain_status = QLabel("Sustain: Off")
        status_row.addWidget(self._sustain_status)
        self._notes_status = QLabel("Notes: 0")
        status_row.addWidget(self._notes_status)

        self._reset_layout_btn = QPushButton("Reset Layout")
        self._reset_layout_btn.clicked.connect(self._on_reset_layout_clicked)
        status_row.addWidget(self._reset_layout_btn)
        status_row.addStretch(1)
        status_layout.addLayout(status_row)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("MIDI Input:"))
        self._midi_input_combo = QComboBox()
        self._midi_input_combo.currentIndexChanged.connect(self._on_midi_input_selected)
        selector_row.addWidget(self._midi_input_combo)

        selector_row.addWidget(QLabel("Audio Output:"))
        self._audio_output_combo = QComboBox()
        self._audio_output_combo.currentIndexChanged.connect(self._on_audio_output_selected)
        selector_row.addWidget(self._audio_output_combo)
        status_layout.addLayout(selector_row)

        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("Volume:"))
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_row.addWidget(self._volume_slider)
        self._volume_label = QLabel("80%")
        self._volume_label.setMinimumWidth(40)
        volume_row.addWidget(self._volume_label)
        status_layout.addLayout(volume_row)

        lower_layout.addWidget(status_group)
        splitter.addWidget(lower_panel)
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, True)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes(self._default_splitter_sizes)

        # Connect falling notes time updates and keyboard visualization
        self._falling_notes.time_changed.connect(self._on_time_changed)
        self._falling_notes.note_triggered.connect(self._keyboard.note_on)
        self._falling_notes.note_released.connect(self._keyboard.note_off)
        self._falling_notes.events_changed.connect(self._on_events_changed)
        self._slider_dragging = False

    def _refresh_soundfont_ui(self):
        instrument = self._instrument_combo.currentText() or "Piano"
        self._soundfont_btn.setText(f"Load {instrument} SoundFont...")

        options = self._instrument_soundfont_options.get(instrument, [("Auto (Best Available)", "")])
        selected = self._instrument_selected_soundfont.get(instrument)
        self._soundfont_combo.blockSignals(True)
        self._soundfont_combo.clear()
        for label, value in options:
            self._soundfont_combo.addItem(label, value)
        if selected:
            selected_idx = self._soundfont_combo.findData(selected)
            self._soundfont_combo.setCurrentIndex(selected_idx if selected_idx >= 0 else 0)
        else:
            self._soundfont_combo.setCurrentIndex(0)
        self._soundfont_combo.blockSignals(False)

        self._soundfont_combo.setEnabled(self._synth_combo.currentText() == "SoundFont")
        path = selected or self._instrument_soundfonts.get(instrument)
        if path:
            self._soundfont_path_label.setText(f"{instrument} SF2: {os.path.basename(path)}")
            self._soundfont_path_label.setToolTip(path)
        else:
            self._soundfont_path_label.setText(f"{instrument} SF2: auto/default")
            self._soundfont_path_label.setToolTip("")

    def _setup_timer(self):
        """Setup timer for recording time display."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_time)

    def _apply_dark_mode(self):
        """Apply dark mode stylesheet."""
        self.setStyleSheet(APP_STYLE)

    def _on_volume_changed(self, value: int):
        self._volume_label.setText(f"{value}%")
        self.volume_changed.emit(value / 100.0)

    def _on_reset_layout_clicked(self):
        if hasattr(self, "_main_splitter"):
            self._main_splitter.setSizes(self._default_splitter_sizes)

    def _on_synth_changed(self, text: str):
        self._soundfont_btn.setEnabled(text == "SoundFont")
        self._refresh_soundfont_ui()
        self.synth_changed.emit(text)

    def _on_instrument_changed(self, text: str):
        self._refresh_soundfont_ui()
        self.instrument_changed.emit(text)

    def _on_load_soundfont(self):
        current_instrument = self._instrument_combo.currentText() or "Piano"
        configured = self._instrument_selected_soundfont.get(current_instrument) or self._instrument_soundfonts.get(current_instrument, "")
        start_dir = os.path.dirname(configured) if configured else ""
        path, _ = QFileDialog.getOpenFileName(
            self, f"Load {current_instrument} SoundFont", start_dir, "SoundFont Files (*.sf2)"
        )
        if path:
            self.soundfont_loaded.emit(path)

    def _on_soundfont_selected(self, _index: int):
        instrument = self._instrument_combo.currentText() or "Piano"
        data = self._soundfont_combo.currentData()
        path = str(data) if data else ""
        if path:
            self._instrument_selected_soundfont[instrument] = path
            self._instrument_soundfonts[instrument] = path
        else:
            self._instrument_selected_soundfont[instrument] = None
            self._instrument_soundfonts.pop(instrument, None)
        self._refresh_soundfont_ui()
        self.soundfont_selected.emit(path)

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
        self._falling_notes.set_bpm(value)
        self.metronome_bpm_changed.emit(value)

    def _on_count_in_toggled(self, checked: bool):
        self._count_in_spin.setEnabled(checked)
        self.count_in_enabled_changed.emit(checked)

    def _on_count_in_beats_changed(self, value: int):
        self.count_in_beats_changed.emit(value)

    def _on_midi_input_selected(self, _index: int):
        port_name = self._midi_input_combo.currentData()
        self.midi_input_changed.emit(str(port_name or ""))

    def _on_audio_output_selected(self, _index: int):
        value = self._audio_output_combo.currentData()
        try:
            self.audio_output_changed.emit(int(value))
        except (TypeError, ValueError):
            self.audio_output_changed.emit(-1)

    def _on_snap_toggled(self, checked: bool):
        self._falling_notes.set_snap_enabled(checked)
        self.snap_enabled_changed.emit(checked)

    def _on_grid_toggled(self, checked: bool):
        self._falling_notes.set_grid_enabled(checked)
        self.grid_enabled_changed.emit(checked)

    def _on_snap_division_changed(self, _index: int):
        division = self._snap_combo.currentData()
        if division:
            self._falling_notes.set_snap_division(int(division))
            self.snap_division_changed.emit(int(division))

    def _on_record_toggled(self, checked: bool):
        self.record_toggled.emit(checked)

    def _on_stop_recording(self):
        if self._record_btn.isChecked():
            self._record_btn.blockSignals(True)
            self._record_btn.setChecked(False)
            self._record_btn.blockSignals(False)
        self.set_count_in_state(False, 0)
        self.set_recording_state(False)
        self.record_toggled.emit(False)

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

    def set_recording_state(self, recording: bool):
        self._count_in_active = False
        self._record_btn.blockSignals(True)
        self._record_btn.setChecked(recording)
        self._record_btn.blockSignals(False)
        self._set_recording_state(recording)

    def set_count_in_state(self, active: bool, beats_left: int):
        self._count_in_active = active
        if active:
            self._record_btn.blockSignals(True)
            self._record_btn.setChecked(True)
            self._record_btn.blockSignals(False)
            self._record_btn.setText(f"Count-in {beats_left}")
            self._stop_btn.setEnabled(True)
            self._time_label.setText(f"Count-in {beats_left}")
            self._timer.stop()
            self._save_wav_btn.setEnabled(False)
            self._save_midi_btn.setEnabled(False)
            self._play_btn.setEnabled(False)
        else:
            if not self._recording:
                self._record_btn.setText("Record")
                self._stop_btn.setEnabled(False)
                if self._record_time == 0:
                    self._time_label.setText("00:00")

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
        self._refresh_soundfont_ui()

    def set_instrument_selection(self, name: str):
        index = self._instrument_combo.findText(name)
        if index < 0:
            return
        self._instrument_combo.blockSignals(True)
        self._instrument_combo.setCurrentIndex(index)
        self._instrument_combo.blockSignals(False)
        self._refresh_soundfont_ui()

    def set_soundfont_options(self, instrument: str, options: list[tuple[str, str]], selected_path: str | None):
        self._instrument_soundfont_options[instrument] = options
        self._instrument_selected_soundfont[instrument] = selected_path
        if selected_path:
            self._instrument_soundfonts[instrument] = selected_path
        else:
            self._instrument_soundfonts.pop(instrument, None)
        self._refresh_soundfont_ui()

    def set_instrument_soundfont_path(self, instrument: str, path: str | None):
        if path:
            self._instrument_soundfonts[instrument] = path
            self._instrument_selected_soundfont[instrument] = path
        else:
            self._instrument_soundfonts.pop(instrument, None)
            self._instrument_selected_soundfont[instrument] = None
        self._refresh_soundfont_ui()

    def set_midi_status(self, connected: bool, name: str = ""):
        if connected:
            self._midi_status.setText(f"Input: {name}")
        else:
            self._midi_status.setText("Input: Not connected")

    def set_audio_status(self, ready: bool, device_name: str = ""):
        if ready:
            if device_name:
                self._audio_status.setText(f"Audio: {device_name}")
            else:
                self._audio_status.setText("Audio: Ready")
        else:
            self._audio_status.setText("Audio: Unavailable")

    def set_midi_inputs(self, ports: list[str], selected: str | None):
        self._midi_input_combo.blockSignals(True)
        self._midi_input_combo.clear()
        self._midi_input_combo.addItem("Auto-select", "")
        for port in ports:
            self._midi_input_combo.addItem(port, port)

        if selected:
            index = self._midi_input_combo.findData(selected)
            if index < 0:
                index = self._midi_input_combo.findText(selected)
            if index < 0:
                index = 0
        else:
            index = 0
        self._midi_input_combo.setCurrentIndex(index)
        self._midi_input_combo.blockSignals(False)

    def set_audio_outputs(self, outputs: list[tuple[int, str]], selected: int | None):
        self._audio_output_combo.blockSignals(True)
        self._audio_output_combo.clear()
        self._audio_output_combo.addItem("Default", -1)
        for device_index, device_name in outputs:
            self._audio_output_combo.addItem(device_name, int(device_index))

        if selected is None:
            index = 0
        else:
            index = self._audio_output_combo.findData(int(selected))
            if index < 0:
                index = 0
        self._audio_output_combo.setCurrentIndex(index)
        self._audio_output_combo.blockSignals(False)

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
