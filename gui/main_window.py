"""Main application window."""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QSlider, QLabel, QPushButton, QComboBox,
    QFileDialog, QSpinBox, QListWidget, QListWidgetItem, QAbstractItemView,
    QCheckBox, QSplitter, QAbstractSpinBox, QSizePolicy, QLineEdit, QStyle,
    QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSettings, QEvent, QPoint, QObject
from PyQt6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut, QPainter, QColor, QPen

from gui.falling_notes_widget import FallingNotesWidget, NoteEvent, SustainEvent
from gui.keyboard_widget import KeyboardWidget
from gui.theme import APP_STYLE
from gui.workspace import WORKSPACE_PRESETS, PRESET_BY_KEY
from piano_player.instruments import DEFAULT_INSTRUMENT, INSTRUMENT_LABELS as DEFAULT_INSTRUMENT_LABELS
from piano_player.synth_modes import SYNTH_SIMPLE, SYNTH_SF2, SYNTH_SFZ


class _SectionGripWidget(QWidget):
    """Small centered grip marker drawn at the top of each resizable section."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setFixedSize(22, 10)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#5f7590"), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        y = 2
        for _ in range(3):
            painter.drawLine(5, y, self.width() - 5, y)
            y += 3
        painter.end()


class _SectionResizeSplitter(QSplitter):
    """Vertical splitter that resizes sections by dragging the top edge of each section."""

    def __init__(self, orientation: Qt.Orientation, parent: QWidget | None = None):
        super().__init__(orientation, parent)
        self._drag_zone_height = 10
        self._active_handle_index: int | None = None
        self._grips: dict[QWidget, _SectionGripWidget] = {}
        self.setHandleWidth(1)
        self.setOpaqueResize(False)
        self.setChildrenCollapsible(True)

    def register_drag_section(self, section: QWidget):
        section.installEventFilter(self)
        section.setMouseTracking(True)
        grip = _SectionGripWidget(section)
        grip.show()
        self._grips[section] = grip
        self._position_grip(section)

    def _position_grip(self, section: QWidget):
        grip = self._grips.get(section)
        if grip is None:
            return
        x = max(0, (section.width() - grip.width()) // 2)
        y = max(1, (self._drag_zone_height - grip.height()) // 2 + 1)
        grip.move(x, y)
        grip.raise_()

    def _event_pos(self, event) -> QPoint | None:
        if hasattr(event, "position"):
            return event.position().toPoint()
        return None

    def _can_drag_from(self, section: QWidget, event) -> bool:
        section_index = self.indexOf(section)
        if section_index < 0 or self.count() < 2:
            return False
        pos = self._event_pos(event)
        if pos is None:
            return False
        return 0 <= pos.y() <= self._drag_zone_height

    def _handle_index_for_section(self, section: QWidget) -> int | None:
        section_index = self.indexOf(section)
        if section_index < 0:
            return None
        if section_index == 0:
            return 1 if self.count() > 1 else None
        return section_index

    def _move_handle_from_event(self, section: QWidget, event):
        if self._active_handle_index is None:
            return
        pos = self._event_pos(event)
        if pos is None:
            return
        in_splitter = section.mapTo(self, pos)
        self.moveSplitter(in_splitter.y(), self._active_handle_index)

    def eventFilter(self, watched: QObject, event: QEvent):
        if watched in self._grips:
            section = watched
            et = event.type()

            if et in (QEvent.Type.Resize, QEvent.Type.Show):
                self._position_grip(section)
            elif et == QEvent.Type.Leave and self._active_handle_index is None:
                section.unsetCursor()
            elif et == QEvent.Type.MouseButtonPress:
                if getattr(event, "button", lambda: None)() == Qt.MouseButton.LeftButton and self._can_drag_from(section, event):
                    self._active_handle_index = self._handle_index_for_section(section)
                    if self._active_handle_index is None:
                        return super().eventFilter(watched, event)
                    section.setCursor(Qt.CursorShape.SizeVerCursor)
                    self._move_handle_from_event(section, event)
                    return True
            elif et == QEvent.Type.MouseMove:
                if self._active_handle_index is not None:
                    self._move_handle_from_event(section, event)
                    return True
                if self._can_drag_from(section, event):
                    section.setCursor(Qt.CursorShape.SizeVerCursor)
                else:
                    section.unsetCursor()
            elif et == QEvent.Type.MouseButtonRelease:
                if self._active_handle_index is not None and getattr(event, "button", lambda: None)() == Qt.MouseButton.LeftButton:
                    self._move_handle_from_event(section, event)
                    self._active_handle_index = None
                    section.unsetCursor()
                    return True

        return super().eventFilter(watched, event)


class MainWindow(QMainWindow):
    """Main application window."""

    INSTRUMENT_LABELS = DEFAULT_INSTRUMENT_LABELS
    SYNTH_SIMPLE = SYNTH_SIMPLE
    SYNTH_SF2 = SYNTH_SF2
    SYNTH_SFZ = SYNTH_SFZ

    @staticmethod
    def _mode_matches_path(mode: str, path: str) -> bool:
        if not path:
            return True
        suffix = os.path.splitext(path)[1].lower()
        if mode == MainWindow.SYNTH_SF2:
            return suffix == ".sf2"
        if mode == MainWindow.SYNTH_SFZ:
            return suffix == ".sfz"
        return suffix in (".sf2", ".sfz")

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
    metronome_volume_changed = pyqtSignal(float)
    count_in_enabled_changed = pyqtSignal(bool)
    count_in_beats_changed = pyqtSignal(int)
    snap_enabled_changed = pyqtSignal(bool)
    grid_enabled_changed = pyqtSignal(bool)
    snap_division_changed = pyqtSignal(int)
    midi_input_changed = pyqtSignal(str)
    audio_output_changed = pyqtSignal(int)
    keyboard_note_pressed = pyqtSignal(int, int)
    keyboard_note_released = pyqtSignal(int)
    debug_reset_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Piano Player")
        self.setMinimumSize(1000, 640)
        self._ui_settings = QSettings()

        self._recording = False
        self._count_in_active = False
        self._record_time = 0
        self._midi_file_path: str | None = None
        self._midi_dir: str | None = None
        self._instrument_soundfonts: dict[str, str] = {}
        self._instrument_soundfont_options: dict[str, list[tuple[str, str]]] = {}
        self._instrument_selected_soundfont: dict[str, str | None] = {}
        self._midi_library_paths: list[str] = []
        self._workspace_key = "balanced"

        self._setup_ui()
        self._setup_timer()
        self._setup_shortcuts()
        self._apply_dark_mode()
        self._restore_ui_state()
        self.setAcceptDrops(True)

    def _current_instrument_key(self) -> str:
        data = self._instrument_combo.currentData()
        if isinstance(data, str) and data in self.INSTRUMENT_LABELS:
            return data
        return DEFAULT_INSTRUMENT

    def _instrument_label(self, key: str | None) -> str:
        return self.INSTRUMENT_LABELS.get(key or "", self.INSTRUMENT_LABELS[DEFAULT_INSTRUMENT])

    def _setup_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        self._file_menu = file_menu
        open_action = QAction("Open MIDI...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_midi)
        file_menu.addAction(open_action)

        save_action = QAction("Save MIDI...", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_midi_file)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        save_recording_midi_action = QAction("Save Recording as MIDI...", self)
        save_recording_midi_action.triggered.connect(self._on_save_midi)
        file_menu.addAction(save_recording_midi_action)

        save_recording_wav_action = QAction("Save Recording as WAV...", self)
        save_recording_wav_action.triggered.connect(self._on_save_wav)
        file_menu.addAction(save_recording_wav_action)
        file_menu.addSeparator()
        refresh_library_action = QAction("Refresh MIDI Library", self)
        refresh_library_action.triggered.connect(self._on_refresh_library)
        file_menu.addAction(refresh_library_action)

        synth_menu = menu.addMenu("Synth")
        self._synth_menu = synth_menu
        self._synth_backend_menu = synth_menu.addMenu("Backend")
        self._synth_backend_group = QActionGroup(self)
        self._synth_backend_group.setExclusive(True)
        self._synth_backend_actions: dict[str, QAction] = {}
        for mode in (self.SYNTH_SIMPLE, self.SYNTH_SF2, self.SYNTH_SFZ):
            action = QAction(mode, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, value=mode: self._set_synth_mode_from_menu(value))
            self._synth_backend_menu.addAction(action)
            self._synth_backend_group.addAction(action)
            self._synth_backend_actions[mode] = action

        self._synth_instrument_menu = synth_menu.addMenu("Instrument")
        self._synth_instrument_group = QActionGroup(self)
        self._synth_instrument_group.setExclusive(True)
        self._synth_instrument_actions: dict[str, QAction] = {}
        for key, label in self.INSTRUMENT_LABELS.items():
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, value=key: self._set_instrument_from_menu(value))
            self._synth_instrument_menu.addAction(action)
            self._synth_instrument_group.addAction(action)
            self._synth_instrument_actions[key] = action

        synth_menu.addSeparator()
        self._synth_load_action = QAction("Load Instrument File...", self)
        self._synth_load_action.triggered.connect(self._on_load_soundfont)
        synth_menu.addAction(self._synth_load_action)

        self._synth_reset_file_action = QAction("Use Auto Instrument File", self)
        self._synth_reset_file_action.triggered.connect(self._clear_selected_instrument_file_from_menu)
        synth_menu.addAction(self._synth_reset_file_action)

        self._metronome_menu = menu.addMenu("Metronome")
        self._metronome_toggle_action = QAction("Enabled", self)
        self._metronome_toggle_action.setCheckable(True)
        self._metronome_toggle_action.triggered.connect(self._set_metronome_enabled_from_menu)
        self._metronome_menu.addAction(self._metronome_toggle_action)
        self._metronome_menu.addSeparator()
        self._metronome_bpm_menu = self._metronome_menu.addMenu("BPM")
        self._metronome_bpm_menu.addAction("−1 BPM", lambda: self._adjust_bpm_from_menu(-1))
        self._metronome_bpm_menu.addAction("+1 BPM", lambda: self._adjust_bpm_from_menu(1))
        self._metronome_bpm_menu.addSeparator()
        for bpm in (60, 80, 100, 120, 140, 160, 180):
            self._metronome_bpm_menu.addAction(f"{bpm} BPM", lambda checked=False, value=bpm: self._set_bpm_from_menu(value))

        self._metronome_menu.addSeparator()
        self._count_in_toggle_action = QAction("Count-in Enabled", self)
        self._count_in_toggle_action.setCheckable(True)
        self._count_in_toggle_action.triggered.connect(self._set_count_in_enabled_from_menu)
        self._metronome_menu.addAction(self._count_in_toggle_action)
        self._count_in_beats_menu = self._metronome_menu.addMenu("Count-in Beats")
        self._count_in_beats_group = QActionGroup(self)
        self._count_in_beats_group.setExclusive(True)
        self._count_in_beats_actions: dict[int, QAction] = {}
        for beats in range(1, 9):
            action = QAction(f"{beats} Beats", self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, value=beats: self._set_count_in_beats_from_menu(value))
            self._count_in_beats_menu.addAction(action)
            self._count_in_beats_group.addAction(action)
            self._count_in_beats_actions[beats] = action

        settings_menu = menu.addMenu("Settings")
        self._settings_menu = settings_menu
        self._settings_set_folder_action = QAction("Set MIDI Folder...", self)
        self._settings_set_folder_action.triggered.connect(self._on_set_midi_folder)
        settings_menu.addAction(self._settings_set_folder_action)
        settings_menu.addSeparator()
        self._settings_midi_input_menu = settings_menu.addMenu("MIDI Input")
        self._settings_audio_output_menu = settings_menu.addMenu("Audio Output")
        settings_menu.addSeparator()
        self._settings_volume_menu = settings_menu.addMenu("Volume")
        self._settings_volume_menu.addAction("−5%", lambda: self._adjust_volume_from_menu(-5))
        self._settings_volume_menu.addAction("+5%", lambda: self._adjust_volume_from_menu(5))
        self._settings_volume_menu.addSeparator()
        for pct in (25, 50, 75, 100):
            self._settings_volume_menu.addAction(f"{pct}%", lambda checked=False, value=pct: self._set_volume_from_menu(value))

        view_menu = menu.addMenu("View")
        self._workspace_actions: dict[str, QAction] = {}
        for preset in WORKSPACE_PRESETS:
            action = QAction(preset.label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, key=preset.key: self._set_workspace_preset(key))
            view_menu.addAction(action)
            self._workspace_actions[preset.key] = action

        view_menu.addSeparator()
        reset_action = QAction("Reset Layout", self)
        reset_action.triggered.connect(self._on_reset_layout_clicked)
        view_menu.addAction(reset_action)

        debug_menu = menu.addMenu("Debug")
        self._debug_menu = debug_menu
        self._debug_show_diagnostics_action = QAction("Show Diagnostics Panel", self)
        self._debug_show_diagnostics_action.setCheckable(True)
        self._debug_show_diagnostics_action.triggered.connect(self._on_toggle_diagnostics_panel)
        debug_menu.addAction(self._debug_show_diagnostics_action)
        debug_menu.addSeparator()
        self._debug_reset_stats_action = QAction("Reset Audio Counters", self)
        self._debug_reset_stats_action.triggered.connect(self.debug_reset_requested.emit)
        debug_menu.addAction(self._debug_reset_stats_action)

    def _setup_ui(self):
        """Create UI elements."""
        self._setup_menu()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        splitter = _SectionResizeSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, stretch=1)
        self._main_splitter = splitter
        self._default_splitter_sizes = list(PRESET_BY_KEY["balanced"].sizes)

        top_controls = QWidget()
        top_controls.setMinimumHeight(0)
        top_layout = QVBoxLayout(top_controls)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        top_layout.addLayout(top_row)

        synth_group = QGroupBox("Synthesizer")
        synth_layout = QVBoxLayout(synth_group)

        self._synth_combo = QComboBox()
        self._synth_combo.addItems([self.SYNTH_SIMPLE, self.SYNTH_SF2, self.SYNTH_SFZ])
        self._synth_combo.currentTextChanged.connect(self._on_synth_changed)
        synth_layout.addWidget(self._synth_combo)
        self._synth_help_label = QLabel("Mode guide: SF2 = FluidSynth, SFZ = sfizz, Simple = built-in synth.")
        self._synth_help_label.setWordWrap(True)
        synth_layout.addWidget(self._synth_help_label)

        instrument_row = QHBoxLayout()
        instrument_row.addWidget(QLabel("Instrument:"))
        self._instrument_combo = QComboBox()
        self._instrument_combo.addItem(self.INSTRUMENT_LABELS["Piano"], "Piano")
        self._instrument_combo.addItem(self.INSTRUMENT_LABELS["Guitar"], "Guitar")
        self._instrument_combo.currentIndexChanged.connect(self._on_instrument_changed)
        instrument_row.addWidget(self._instrument_combo)
        synth_layout.addLayout(instrument_row)

        soundfont_row = QHBoxLayout()
        soundfont_row.addWidget(QLabel("Instrument File:"))
        self._soundfont_combo = QComboBox()
        self._soundfont_combo.currentIndexChanged.connect(self._on_soundfont_selected)
        soundfont_row.addWidget(self._soundfont_combo)
        synth_layout.addLayout(soundfont_row)

        self._soundfont_btn = QPushButton("Load Instrument File...")
        self._soundfont_btn.clicked.connect(self._on_load_soundfont)
        self._soundfont_btn.setEnabled(False)
        synth_layout.addWidget(self._soundfont_btn)
        self._soundfont_path_label = QLabel("Acoustic Grand Piano File: auto/default")
        self._soundfont_path_label.setWordWrap(True)
        synth_layout.addWidget(self._soundfont_path_label)

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
        synth_group.setVisible(False)
        midi_file_group.setVisible(False)

        library_group = QGroupBox("MIDI Library")
        library_layout = QVBoxLayout(library_group)
        library_layout.setContentsMargins(10, 8, 10, 8)
        library_layout.setSpacing(6)

        self._midi_folder_label = QLabel("Folder: Not set")
        self._midi_folder_label.setWordWrap(True)
        library_layout.addWidget(self._midi_folder_label)

        self._midi_search = QLineEdit()
        self._midi_search.setPlaceholderText("Filter library...")
        self._midi_search.setClearButtonEnabled(True)
        self._midi_search.textChanged.connect(self._apply_midi_library_filter)
        library_layout.addWidget(self._midi_search)

        library_sort_row = QHBoxLayout()
        library_sort_row.setContentsMargins(0, 0, 0, 0)
        library_sort_row.setSpacing(8)
        library_sort_row.addWidget(QLabel("Sort:"))
        self._midi_sort_combo = QComboBox()
        self._midi_sort_combo.addItem("Name (A-Z)", "name_asc")
        self._midi_sort_combo.addItem("Name (Z-A)", "name_desc")
        self._midi_sort_combo.addItem("Recently Modified", "mtime_desc")
        self._midi_sort_combo.currentIndexChanged.connect(self._apply_midi_library_filter)
        self._midi_sort_combo.setToolTip("Sort files by name or recent edits")
        library_sort_row.addWidget(self._midi_sort_combo)

        self._midi_refresh_btn = QPushButton("Refresh")
        self._midi_refresh_btn.clicked.connect(self._on_refresh_library)
        self._midi_refresh_btn.setProperty("compact", "true")
        self._midi_refresh_btn.setMaximumWidth(88)
        library_sort_row.addWidget(self._midi_refresh_btn)

        library_sort_row.addStretch(1)
        library_layout.addLayout(library_sort_row)

        self._midi_list = QListWidget()
        self._midi_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._midi_list.itemDoubleClicked.connect(self._on_midi_item_activated)
        self._midi_list.setMinimumHeight(0)
        library_layout.addWidget(self._midi_list)

        diagnostics_group = QGroupBox("Diagnostics")
        diagnostics_layout = QVBoxLayout(diagnostics_group)
        diagnostics_layout.setContentsMargins(10, 8, 10, 8)
        diagnostics_layout.setSpacing(6)

        self._diag_hint = QLabel("Live realtime diagnostics for audio callback stability.")
        self._diag_hint.setObjectName("hintLabel")
        diagnostics_layout.addWidget(self._diag_hint)

        self._diag_backend = QLabel("Backend: -")
        diagnostics_layout.addWidget(self._diag_backend)
        self._diag_sample_rate = QLabel("Sample rate: -")
        diagnostics_layout.addWidget(self._diag_sample_rate)
        self._diag_buffer = QLabel("Buffer: -")
        diagnostics_layout.addWidget(self._diag_buffer)
        self._diag_output = QLabel("Output: -")
        diagnostics_layout.addWidget(self._diag_output)
        self._diag_notes = QLabel("Active notes: 0")
        diagnostics_layout.addWidget(self._diag_notes)
        self._diag_callbacks = QLabel("Callbacks: 0")
        diagnostics_layout.addWidget(self._diag_callbacks)
        self._diag_xruns = QLabel("XRUNs: 0")
        diagnostics_layout.addWidget(self._diag_xruns)
        self._diag_xrun_ratio = QLabel("XRUN ratio: 0.00%")
        diagnostics_layout.addWidget(self._diag_xrun_ratio)
        self._diag_peak = QLabel("Peak: 0.000")
        diagnostics_layout.addWidget(self._diag_peak)
        self._diag_master_gain = QLabel("Master gain: 1.000")
        diagnostics_layout.addWidget(self._diag_master_gain)
        self._diag_clip_samples = QLabel("Clip samples: 0")
        diagnostics_layout.addWidget(self._diag_clip_samples)
        self._diag_non_finite = QLabel("Non-finite blocks: 0")
        diagnostics_layout.addWidget(self._diag_non_finite)
        self._diag_over_budget = QLabel("Over-budget callbacks: 0")
        diagnostics_layout.addWidget(self._diag_over_budget)
        self._diag_avg_callback = QLabel("Avg callback: 0.000 ms")
        diagnostics_layout.addWidget(self._diag_avg_callback)
        self._diag_max_callback = QLabel("Max callback: 0.000 ms")
        diagnostics_layout.addWidget(self._diag_max_callback)
        diagnostics_layout.addStretch(1)

        self._top_content_stack = QStackedWidget()
        self._top_content_stack.addWidget(library_group)
        self._top_content_stack.addWidget(diagnostics_group)
        self._top_content_stack.setCurrentWidget(library_group)
        top_layout.addWidget(self._top_content_stack)
        splitter.addWidget(top_controls)

        notes_group = QGroupBox("Piano Roll Editor")
        notes_layout = QVBoxLayout(notes_group)
        notes_layout.setContentsMargins(8, 8, 8, 8)
        notes_layout.setSpacing(6)

        roll_controls = QHBoxLayout()
        roll_controls.setContentsMargins(0, 0, 0, 0)
        roll_controls.setSpacing(8)
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

        roll_controls.addWidget(QLabel("View:"))
        self._roll_zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._roll_zoom_slider.setRange(20, 120)
        self._roll_zoom_slider.setValue(50)
        self._roll_zoom_slider.setFixedWidth(140)
        self._roll_zoom_slider.valueChanged.connect(self._on_roll_zoom_changed)
        self._roll_zoom_slider.setToolTip("Adjust visible time window of the piano roll")
        roll_controls.addWidget(self._roll_zoom_slider)
        self._roll_zoom_label = QLabel("6.0s")
        self._roll_zoom_label.setMinimumWidth(38)
        roll_controls.addWidget(self._roll_zoom_label)

        roll_controls.addWidget(QLabel("Vol:"))
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.setFixedWidth(110)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        roll_controls.addWidget(self._volume_slider)
        self._volume_label = QLabel("80%")
        self._volume_label.setMinimumWidth(38)
        roll_controls.addWidget(self._volume_label)

        self._roll_hint_label = QLabel("Ctrl+Wheel: zoom")
        self._roll_hint_label.setObjectName("hintLabel")
        roll_controls.addWidget(self._roll_hint_label)

        roll_controls.addStretch(1)

        self._metro_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._metro_volume_slider.setRange(0, 100)
        self._metro_volume_slider.setValue(35)
        self._metro_volume_slider.setFixedWidth(92)
        self._metro_volume_slider.valueChanged.connect(self._on_metronome_volume_changed)
        roll_controls.addWidget(self._metro_volume_slider)

        self._metro_btn = QPushButton("Metro")
        self._metro_btn.setCheckable(True)
        self._metro_btn.setProperty("variant", "toggle")
        self._metro_btn.setProperty("compact", "true")
        self._metro_btn.clicked.connect(self._on_metronome_toggled)
        self._metro_btn.setMaximumWidth(74)
        roll_controls.addWidget(self._metro_btn)

        self._bpm_spin = QSpinBox()
        self._bpm_spin.setRange(20, 300)
        self._bpm_spin.setValue(120)
        self._bpm_spin.setSuffix(" BPM")
        self._bpm_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self._bpm_spin.valueChanged.connect(self._on_bpm_changed)
        self._bpm_spin.setToolTip("Metronome tempo in beats per minute")
        self._bpm_spin.setMaximumWidth(108)
        roll_controls.addWidget(self._bpm_spin)

        self._count_in_check = QCheckBox("Count-in")
        self._count_in_check.toggled.connect(self._on_count_in_toggled)
        roll_controls.addWidget(self._count_in_check)

        self._count_in_spin = QSpinBox()
        self._count_in_spin.setRange(1, 8)
        self._count_in_spin.setValue(4)
        self._count_in_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self._count_in_spin.setEnabled(False)
        self._count_in_spin.valueChanged.connect(self._on_count_in_beats_changed)
        self._count_in_spin.setToolTip("Accent every Nth beat during count-in")
        self._count_in_spin.setMaximumWidth(62)
        roll_controls.addWidget(self._count_in_spin)

        notes_layout.addLayout(roll_controls)

        self._falling_notes = FallingNotesWidget()
        self._falling_notes.setMinimumHeight(140)
        self._falling_notes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._falling_notes.set_bpm(self._bpm_spin.value())
        self._falling_notes.set_snap_enabled(self._snap_check.isChecked())
        self._falling_notes.set_grid_enabled(self._grid_check.isChecked())
        self._falling_notes.set_snap_division(self._snap_combo.currentData())
        self._falling_notes.set_visible_seconds(self._roll_zoom_slider.value() / 10.0 + 1.0)
        self._falling_notes.view_window_changed.connect(self._sync_roll_zoom_from_view)
        self._roll_zoom_label.setText(f"{self._falling_notes.get_visible_seconds():.1f}s")
        notes_layout.addWidget(self._falling_notes)

        self._keyboard = KeyboardWidget()
        self._keyboard.note_pressed.connect(self._on_keyboard_note_pressed)
        self._keyboard.note_released.connect(self._on_keyboard_note_released)
        self._keyboard.setMinimumHeight(72)
        self._keyboard.setMaximumHeight(112)
        notes_layout.addWidget(self._keyboard)
        splitter.addWidget(notes_group)

        lower_panel = QWidget()
        lower_panel.setMinimumHeight(0)
        lower_layout = QVBoxLayout(lower_panel)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(8)

        record_group = QGroupBox("Transport / Recording")
        record_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        record_main_layout = QVBoxLayout(record_group)
        record_main_layout.setContentsMargins(8, 8, 8, 6)
        record_main_layout.setSpacing(6)

        record_controls = QHBoxLayout()
        record_controls.setContentsMargins(0, 0, 0, 0)
        record_controls.setSpacing(8)
        record_main_layout.addLayout(record_controls)

        self._play_btn = QPushButton("Play")
        self._play_btn.clicked.connect(self._on_play_recording)
        self._play_btn.setEnabled(False)
        self._play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self._play_btn.setToolTip("Play/Stop (Space)")
        self._play_btn.setProperty("variant", "transport")
        record_controls.addWidget(self._play_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._on_stop_recording)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self._stop_btn.setToolTip("Stop transport")
        self._stop_btn.setProperty("variant", "transport")
        record_controls.addWidget(self._stop_btn)

        self._record_btn = QPushButton("● Record")
        self._record_btn.setCheckable(True)
        self._record_btn.toggled.connect(self._on_record_toggled)
        self._record_btn.setToolTip("Record toggle (R)")
        self._record_btn.setProperty("variant", "record")
        record_controls.addWidget(self._record_btn)

        self._time_label = QLabel("00:00")
        self._time_label.setMinimumWidth(50)
        self._time_label.setObjectName("timeCode")
        record_controls.addWidget(self._time_label)

        self._save_wav_btn = QPushButton("Save WAV")
        self._save_wav_btn.clicked.connect(self._on_save_wav)
        self._save_wav_btn.setEnabled(False)
        record_controls.addWidget(self._save_wav_btn)

        self._save_midi_btn = QPushButton("Save MIDI")
        self._save_midi_btn.clicked.connect(self._on_save_midi)
        self._save_midi_btn.setEnabled(False)
        self._save_midi_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        record_controls.addWidget(self._save_midi_btn)

        timeline_layout = QHBoxLayout()
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(8)
        self._timeline_label = QLabel("0:00")
        self._timeline_label.setMinimumWidth(40)
        self._timeline_label.setObjectName("timeCode")
        timeline_layout.addWidget(self._timeline_label)

        self._timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self._timeline_slider.setRange(0, 1000)
        self._timeline_slider.setValue(0)
        self._timeline_slider.setFixedHeight(18)
        self._timeline_slider.sliderMoved.connect(self._on_timeline_seek)
        self._timeline_slider.sliderPressed.connect(self._on_timeline_pressed)
        self._timeline_slider.sliderReleased.connect(self._on_timeline_released)
        timeline_layout.addWidget(self._timeline_slider)

        self._duration_label = QLabel("0:00")
        self._duration_label.setMinimumWidth(40)
        self._duration_label.setObjectName("timeCode")
        timeline_layout.addWidget(self._duration_label)

        record_main_layout.addLayout(timeline_layout)
        lower_layout.addWidget(record_group)

        status_group = QGroupBox("Status")
        status_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(8)

        status_row = QHBoxLayout()
        self._midi_status = QLabel("Input: Not connected")
        self._midi_status.setObjectName("statusBadge")
        status_row.addWidget(self._midi_status)
        self._audio_status = QLabel("Audio: Default output")
        self._audio_status.setObjectName("statusBadge")
        status_row.addWidget(self._audio_status)
        self._sustain_status = QLabel("Sustain: Off")
        self._sustain_status.setObjectName("statusBadge")
        status_row.addWidget(self._sustain_status)
        self._notes_status = QLabel("Notes: 0")
        self._notes_status.setObjectName("statusBadge")
        status_row.addWidget(self._notes_status)
        self._transport_status = QLabel("Transport: Idle")
        self._transport_status.setObjectName("statusBadge")
        status_row.addWidget(self._transport_status)

        self._reset_layout_btn = QPushButton("Reset Layout")
        self._reset_layout_btn.clicked.connect(self._on_reset_layout_clicked)
        status_row.addWidget(self._reset_layout_btn)
        status_row.addStretch(1)
        status_layout.addLayout(status_row)
        self._set_badge_state(self._midi_status, False)
        self._set_badge_state(self._audio_status, True)
        self._set_badge_state(self._sustain_status, False)
        self._set_badge_state(self._notes_status, False)
        self._set_badge_state(self._transport_status, False)

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

        lower_layout.addWidget(status_group)
        status_group.setVisible(False)
        splitter.addWidget(lower_panel)
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, True)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes(self._default_splitter_sizes)
        splitter.register_drag_section(top_controls)
        splitter.register_drag_section(notes_group)
        splitter.register_drag_section(lower_panel)

        # Connect falling notes time updates and keyboard visualization
        self._falling_notes.time_changed.connect(self._on_time_changed)
        self._falling_notes.note_triggered.connect(self._keyboard.note_on)
        self._falling_notes.note_released.connect(self._keyboard.note_off)
        self._falling_notes.events_changed.connect(self._on_events_changed)
        self._slider_dragging = False
        self._rebuild_settings_device_menus()
        self._sync_menu_state_from_controls()
        self._on_toggle_diagnostics_panel(False)

    def _refresh_soundfont_ui(self):
        instrument = self._current_instrument_key()
        instrument_label = self._instrument_label(instrument)
        self._soundfont_btn.setText(f"Load {instrument_label} Instrument File...")
        if hasattr(self, "_synth_load_action"):
            self._synth_load_action.setText(f"Load {instrument_label} Instrument File...")

        synth_mode = self._synth_combo.currentText()
        options = self._instrument_soundfont_options.get(instrument, [("Auto (Best Available)", "")])
        options = [
            (label, value)
            for label, value in options
            if self._mode_matches_path(synth_mode, str(value or ""))
        ]
        if not options:
            options = [("Auto (Best Available)", "")]

        selected = self._instrument_selected_soundfont.get(instrument)
        if selected and not self._mode_matches_path(synth_mode, selected):
            selected = None

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

        sampled_mode = synth_mode != self.SYNTH_SIMPLE
        self._soundfont_combo.setEnabled(sampled_mode)
        path = selected
        if not path:
            current_path = self._instrument_soundfonts.get(instrument)
            if current_path and self._mode_matches_path(synth_mode, current_path):
                path = current_path
        auto_path = ""
        for _label, value in options:
            if value:
                auto_path = str(value)
                break
        if path:
            suffix = os.path.splitext(path)[1].lower()
            kind = "SFZ" if suffix == ".sfz" else "SF2"
            self._soundfont_path_label.setText(f"{instrument_label} {kind}: {os.path.basename(path)}")
            self._soundfont_path_label.setToolTip(path)
        elif auto_path:
            suffix = os.path.splitext(auto_path)[1].lower()
            kind = "SFZ" if suffix == ".sfz" else "SF2"
            self._soundfont_path_label.setText(f"{instrument_label} Auto {kind}: {os.path.basename(auto_path)}")
            self._soundfont_path_label.setToolTip(auto_path)
        else:
            self._soundfont_path_label.setText(f"{instrument_label} File: auto/default")
            self._soundfont_path_label.setToolTip("")

    def _setup_timer(self):
        """Setup timer for recording time display."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_time)

    def _setup_shortcuts(self):
        """Keyboard shortcuts inspired by common DAW workflows."""
        self._shortcuts: list[QShortcut] = []

        space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space.activated.connect(self._on_play_recording)
        self._shortcuts.append(space)

        record = QShortcut(QKeySequence("R"), self)
        record.activated.connect(self._toggle_record_shortcut)
        self._shortcuts.append(record)

        open_midi = QShortcut(QKeySequence.StandardKey.Open, self)
        open_midi.activated.connect(self._on_open_midi)
        self._shortcuts.append(open_midi)

        save_midi = QShortcut(QKeySequence.StandardKey.Save, self)
        save_midi.activated.connect(self._on_save_midi_file)
        self._shortcuts.append(save_midi)

        metro = QShortcut(QKeySequence("M"), self)
        metro.activated.connect(self._metro_btn.toggle)
        self._shortcuts.append(metro)

    def _set_synth_mode_from_menu(self, mode: str):
        index = self._synth_combo.findText(mode)
        if index >= 0:
            self._synth_combo.setCurrentIndex(index)

    def _set_instrument_from_menu(self, instrument_key: str):
        index = self._instrument_combo.findData(instrument_key)
        if index >= 0:
            self._instrument_combo.setCurrentIndex(index)

    def _clear_selected_instrument_file_from_menu(self):
        self._soundfont_combo.setCurrentIndex(0)

    def _set_metronome_enabled_from_menu(self, enabled: bool):
        if self._metro_btn.isChecked() != enabled:
            self._metro_btn.setChecked(enabled)
            self._on_metronome_toggled(enabled)

    def _set_bpm_from_menu(self, bpm: int):
        self._bpm_spin.setValue(max(self._bpm_spin.minimum(), min(self._bpm_spin.maximum(), int(bpm))))

    def _adjust_bpm_from_menu(self, delta: int):
        self._set_bpm_from_menu(self._bpm_spin.value() + int(delta))

    def _set_count_in_enabled_from_menu(self, enabled: bool):
        if self._count_in_check.isChecked() != enabled:
            self._count_in_check.setChecked(enabled)

    def _set_count_in_beats_from_menu(self, beats: int):
        self._count_in_spin.setValue(max(self._count_in_spin.minimum(), min(self._count_in_spin.maximum(), int(beats))))

    def _set_volume_from_menu(self, percent: int):
        self._volume_slider.setValue(max(self._volume_slider.minimum(), min(self._volume_slider.maximum(), int(percent))))

    def _adjust_volume_from_menu(self, delta: int):
        self._set_volume_from_menu(self._volume_slider.value() + int(delta))

    def _set_combo_to_data(self, combo: QComboBox, value):
        idx = combo.findData(value)
        if idx < 0 and isinstance(value, str):
            idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _rebuild_settings_device_menus(self):
        self._settings_midi_input_menu.clear()
        for idx in range(self._midi_input_combo.count()):
            text = self._midi_input_combo.itemText(idx)
            data = self._midi_input_combo.itemData(idx)
            action = QAction(text, self)
            action.setCheckable(True)
            action.setData(data)
            action.triggered.connect(lambda checked, target=data: self._set_combo_to_data(self._midi_input_combo, target))
            self._settings_midi_input_menu.addAction(action)

        self._settings_audio_output_menu.clear()
        for idx in range(self._audio_output_combo.count()):
            text = self._audio_output_combo.itemText(idx)
            data = self._audio_output_combo.itemData(idx)
            action = QAction(text, self)
            action.setCheckable(True)
            action.setData(data)
            action.triggered.connect(lambda checked, target=data: self._set_combo_to_data(self._audio_output_combo, target))
            self._settings_audio_output_menu.addAction(action)

        self._sync_menu_state_from_controls()

    def _sync_menu_state_from_controls(self):
        mode = self._synth_combo.currentText()
        for key, action in self._synth_backend_actions.items():
            action.setChecked(key == mode)

        instrument = self._current_instrument_key()
        for key, action in self._synth_instrument_actions.items():
            action.setChecked(key == instrument)

        self._metronome_toggle_action.setChecked(self._metro_btn.isChecked())
        self._count_in_toggle_action.setChecked(self._count_in_check.isChecked())
        for beats, action in self._count_in_beats_actions.items():
            action.setChecked(beats == self._count_in_spin.value())

        selected_midi = self._midi_input_combo.currentData()
        for action in self._settings_midi_input_menu.actions():
            action.setChecked(action.data() == selected_midi)

        selected_audio = self._audio_output_combo.currentData()
        for action in self._settings_audio_output_menu.actions():
            action.setChecked(action.data() == selected_audio)

        for key, action in self._workspace_actions.items():
            action.setChecked(key == self._workspace_key)

    def _apply_dark_mode(self):
        """Apply dark mode stylesheet."""
        self.setStyleSheet(APP_STYLE)

    def _on_volume_changed(self, value: int):
        self._volume_label.setText(f"{value}%")
        self.volume_changed.emit(value / 100.0)

    def _on_reset_layout_clicked(self):
        self._set_workspace_preset("balanced")

    def _set_workspace_preset(self, key: str):
        preset = PRESET_BY_KEY.get(key, PRESET_BY_KEY["balanced"])
        self._workspace_key = preset.key
        if hasattr(self, "_main_splitter"):
            self._main_splitter.setSizes(list(preset.sizes))
        self._default_splitter_sizes = list(preset.sizes)

        for action_key, action in getattr(self, "_workspace_actions", {}).items():
            action.setChecked(action_key == preset.key)

    def _on_synth_changed(self, text: str):
        self._soundfont_btn.setEnabled(text != self.SYNTH_SIMPLE)
        self._refresh_soundfont_ui()
        self._sync_menu_state_from_controls()
        self.synth_changed.emit(text)

    def _on_instrument_changed(self, _index: int):
        key = self._current_instrument_key()
        self._refresh_soundfont_ui()
        self._sync_menu_state_from_controls()
        self.instrument_changed.emit(key)

    def _on_load_soundfont(self):
        synth_mode = self._synth_combo.currentText()
        current_instrument = self._current_instrument_key()
        current_instrument_label = self._instrument_label(current_instrument)
        configured = self._instrument_selected_soundfont.get(current_instrument) or self._instrument_soundfonts.get(current_instrument, "")
        start_dir = os.path.dirname(configured) if configured else ""
        if not start_dir or not os.path.isdir(start_dir):
            options = self._instrument_soundfont_options.get(current_instrument, [])
            for _label, value in options:
                if value and os.path.exists(value):
                    start_dir = os.path.dirname(value)
                    break
        if not start_dir:
            fallback_dir = os.path.expanduser("~/.config/piano-player/soundfonts")
            os.makedirs(fallback_dir, exist_ok=True)
            start_dir = fallback_dir
        file_filter = "Instrument Files (*.sf2 *.sfz)"
        if synth_mode == self.SYNTH_SF2:
            file_filter = "SF2 Files (*.sf2)"
        elif synth_mode == self.SYNTH_SFZ:
            file_filter = "SFZ Files (*.sfz)"
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Load {current_instrument_label} Instrument File",
            start_dir,
            file_filter,
        )
        if path:
            self.soundfont_loaded.emit(path)

    def _on_soundfont_selected(self, _index: int):
        instrument = self._current_instrument_key()
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
        self._metro_btn.setText("Metro On" if checked else "Metro")
        self._sync_menu_state_from_controls()
        self.metronome_toggled.emit(checked)

    def _on_bpm_changed(self, value: int):
        self._falling_notes.set_bpm(value)
        self.metronome_bpm_changed.emit(value)

    def _on_count_in_toggled(self, checked: bool):
        self._count_in_spin.setEnabled(checked)
        self._sync_menu_state_from_controls()
        self.count_in_enabled_changed.emit(checked)

    def _on_count_in_beats_changed(self, value: int):
        self._sync_menu_state_from_controls()
        self.count_in_beats_changed.emit(value)

    def _on_metronome_volume_changed(self, value: int):
        self.metronome_volume_changed.emit(max(0.0, min(1.0, value / 100.0)))

    def _on_midi_input_selected(self, _index: int):
        port_name = self._midi_input_combo.currentData()
        self._sync_menu_state_from_controls()
        self.midi_input_changed.emit(str(port_name or ""))

    def _on_audio_output_selected(self, _index: int):
        value = self._audio_output_combo.currentData()
        self._sync_menu_state_from_controls()
        try:
            self.audio_output_changed.emit(int(value))
        except (TypeError, ValueError):
            self.audio_output_changed.emit(-1)

    def _on_keyboard_note_pressed(self, note: int, velocity: int):
        self.keyboard_note_pressed.emit(int(note), int(velocity))

    def _on_keyboard_note_released(self, note: int):
        self.keyboard_note_released.emit(int(note))

    def _on_snap_toggled(self, checked: bool):
        self._falling_notes.set_snap_enabled(checked)
        self.snap_enabled_changed.emit(checked)

    def _on_toggle_diagnostics_panel(self, checked: bool):
        if checked:
            self._top_content_stack.setCurrentIndex(1)
        else:
            self._top_content_stack.setCurrentIndex(0)
        self._debug_show_diagnostics_action.blockSignals(True)
        self._debug_show_diagnostics_action.setChecked(bool(checked))
        self._debug_show_diagnostics_action.blockSignals(False)

    def _on_grid_toggled(self, checked: bool):
        self._falling_notes.set_grid_enabled(checked)
        self.grid_enabled_changed.emit(checked)

    def _on_snap_division_changed(self, _index: int):
        division = self._snap_combo.currentData()
        if division:
            self._falling_notes.set_snap_division(int(division))
            self.snap_division_changed.emit(int(division))

    def _on_roll_zoom_changed(self, value: int):
        seconds = (value / 10.0) + 1.0
        self._falling_notes.set_visible_seconds(seconds)
        self._roll_zoom_label.setText(f"{self._falling_notes.get_visible_seconds():.1f}s")

    def _sync_roll_zoom_from_view(self, seconds: float):
        slider_value = int(round((seconds - 1.0) * 10.0))
        slider_value = max(self._roll_zoom_slider.minimum(), min(self._roll_zoom_slider.maximum(), slider_value))
        self._roll_zoom_slider.blockSignals(True)
        self._roll_zoom_slider.setValue(slider_value)
        self._roll_zoom_slider.blockSignals(False)
        self._roll_zoom_label.setText(f"{seconds:.1f}s")

    @staticmethod
    def _set_badge_state(label: QLabel, ok: bool):
        label.setProperty("ok", "true" if ok else "false")
        style = label.style()
        if style is not None:
            style.unpolish(label)
            style.polish(label)

    def _on_record_toggled(self, checked: bool):
        self.record_toggled.emit(checked)

    def _toggle_record_shortcut(self):
        if self._record_btn.isEnabled():
            self._record_btn.toggle()

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

    def _set_transport_state(self, state: str):
        label = state.strip().title() if state else "Idle"
        self._transport_status.setText(f"Transport: {label}")
        active = label.lower() not in ("idle", "stopped")
        self._set_badge_state(self._transport_status, active)

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
        self._record_btn.setText("● Recording..." if recording else "● Record")
        self._stop_btn.setEnabled(recording)
        if recording:
            self._record_time = 0
            self._time_label.setText("00:00")
            self._timer.start(1000)
            self._save_wav_btn.setEnabled(False)
            self._save_midi_btn.setEnabled(False)
            self._play_btn.setEnabled(False)
            self._set_transport_state("recording")
        else:
            self._timer.stop()
            self._save_wav_btn.setEnabled(True)
            self._save_midi_btn.setEnabled(True)
            self._play_btn.setEnabled(True)
            if not self._falling_notes.is_playing():
                self._set_transport_state("idle")

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
            self._record_btn.setText(f"● Count-in {beats_left}")
            self._stop_btn.setEnabled(True)
            self._time_label.setText(f"Count-in {beats_left}")
            self._timer.stop()
            self._save_wav_btn.setEnabled(False)
            self._save_midi_btn.setEnabled(False)
            self._play_btn.setEnabled(False)
            self._set_transport_state(f"count-in ({beats_left})")
        else:
            if not self._recording:
                self._record_btn.setText("● Record")
                self._stop_btn.setEnabled(False)
                if self._record_time == 0:
                    self._time_label.setText("00:00")
                if not self._falling_notes.is_playing():
                    self._set_transport_state("idle")

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

    def _restore_ui_state(self):
        saved_workspace = self._ui_settings.value("ui/workspace", "balanced", type=str)
        self._set_workspace_preset(saved_workspace)

        saved_sizes = self._ui_settings.value("ui/splitter_sizes")
        if isinstance(saved_sizes, list) and len(saved_sizes) == 3:
            try:
                sizes = [max(0, int(value)) for value in saved_sizes]
                self._main_splitter.setSizes(sizes)
            except (TypeError, ValueError):
                pass

        filter_text = self._ui_settings.value("ui/midi_filter", "", type=str) or ""
        self._midi_search.setText(filter_text)
        sort_mode = self._ui_settings.value("ui/midi_sort", "name_asc", type=str) or "name_asc"
        sort_idx = self._midi_sort_combo.findData(sort_mode)
        if sort_idx >= 0:
            self._midi_sort_combo.setCurrentIndex(sort_idx)

        roll_zoom = self._ui_settings.value("ui/roll_zoom", 50, type=int)
        self._roll_zoom_slider.setValue(max(self._roll_zoom_slider.minimum(), min(self._roll_zoom_slider.maximum(), int(roll_zoom))))

    def _save_ui_state(self):
        if hasattr(self, "_main_splitter"):
            self._ui_settings.setValue("ui/splitter_sizes", self._main_splitter.sizes())
        self._ui_settings.setValue("ui/workspace", self._workspace_key)
        if hasattr(self, "_midi_search"):
            self._ui_settings.setValue("ui/midi_filter", self._midi_search.text())
        if hasattr(self, "_midi_sort_combo"):
            self._ui_settings.setValue("ui/midi_sort", self._midi_sort_combo.currentData())
        if hasattr(self, "_roll_zoom_slider"):
            self._ui_settings.setValue("ui/roll_zoom", int(self._roll_zoom_slider.value()))

    def closeEvent(self, event):
        self._save_ui_state()
        super().closeEvent(event)

    # Public methods to update status
    def set_synth_selection(self, name: str):
        """Set synth selection without emitting change signals."""
        index = self._synth_combo.findText(name)
        if index < 0:
            return
        self._synth_combo.blockSignals(True)
        self._synth_combo.setCurrentIndex(index)
        self._synth_combo.blockSignals(False)
        self._soundfont_btn.setEnabled(name != self.SYNTH_SIMPLE)
        self._refresh_soundfont_ui()
        self._sync_menu_state_from_controls()

    def set_instrument_selection(self, name: str):
        index = self._instrument_combo.findData(name)
        if index < 0:
            index = self._instrument_combo.findText(name)
        if index < 0:
            return
        self._instrument_combo.blockSignals(True)
        self._instrument_combo.setCurrentIndex(index)
        self._instrument_combo.blockSignals(False)
        self._refresh_soundfont_ui()
        self._sync_menu_state_from_controls()

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
        self._set_badge_state(self._midi_status, connected)

    def set_audio_status(self, ready: bool, device_name: str = ""):
        if ready:
            if device_name:
                self._audio_status.setText(f"Audio: {device_name}")
            else:
                self._audio_status.setText("Audio: Ready")
        else:
            self._audio_status.setText("Audio: Unavailable")
        self._set_badge_state(self._audio_status, ready)

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
        self._rebuild_settings_device_menus()

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
        self._rebuild_settings_device_menus()

    def set_metronome_volume(self, volume: float):
        clamped = max(0.0, min(1.0, float(volume)))
        value = int(round(clamped * 100.0))
        self._metro_volume_slider.blockSignals(True)
        self._metro_volume_slider.setValue(value)
        self._metro_volume_slider.blockSignals(False)

    def set_sustain_status(self, on: bool):
        self._sustain_status.setText(f"Sustain: {'On' if on else 'Off'}")
        self._set_badge_state(self._sustain_status, on)

    def set_notes_count(self, count: int):
        self._notes_status.setText(f"Notes: {count}")
        self._set_badge_state(self._notes_status, count > 0)

    def set_midi_file_info(self, path: str | None):
        self._midi_file_path = path
        if path:
            name = os.path.basename(path)
            self._midi_file_label.setText(f"Loaded: {name}")
            self.setWindowTitle(f"Piano Player - {name}")
        else:
            self._midi_file_label.setText("No MIDI loaded")
            self.setWindowTitle("Piano Player")

    def set_midi_folder(self, path: str | None):
        self._midi_dir = path
        if path:
            self._midi_folder_label.setText(f"Folder: {path}")
        else:
            self._midi_folder_label.setText("Folder: Not set")

    def set_diagnostics(self, values: dict[str, str | int | float]):
        backend = str(values.get("backend", "-"))
        sample_rate = int(values.get("sample_rate", 0) or 0)
        buffer_size = int(values.get("buffer_size", 0) or 0)
        output = str(values.get("output", "-"))
        notes = int(values.get("active_notes", 0) or 0)
        callbacks = int(values.get("callbacks", 0) or 0)
        xruns = int(values.get("xruns", 0) or 0)
        xrun_ratio = float(values.get("xrun_ratio", 0.0) or 0.0)
        peak = float(values.get("peak", 0.0) or 0.0)
        master_gain = float(values.get("master_gain", 1.0) or 1.0)
        clip_samples = int(values.get("clip_samples", 0) or 0)
        non_finite_blocks = int(values.get("non_finite_blocks", 0) or 0)
        over_budget = int(values.get("over_budget_callbacks", 0) or 0)
        avg_callback_ms = float(values.get("avg_callback_ms", 0.0) or 0.0)
        max_callback_ms = float(values.get("max_callback_ms", 0.0) or 0.0)

        self._diag_backend.setText(f"Backend: {backend}")
        if sample_rate > 0:
            self._diag_sample_rate.setText(f"Sample rate: {sample_rate} Hz")
        else:
            self._diag_sample_rate.setText("Sample rate: -")
        if buffer_size > 0:
            self._diag_buffer.setText(f"Buffer: {buffer_size} frames")
        else:
            self._diag_buffer.setText("Buffer: -")
        self._diag_output.setText(f"Output: {output}")
        self._diag_notes.setText(f"Active notes: {notes}")
        self._diag_callbacks.setText(f"Callbacks: {callbacks}")
        self._diag_xruns.setText(f"XRUNs: {xruns}")
        self._diag_xrun_ratio.setText(f"XRUN ratio: {xrun_ratio * 100.0:.2f}%")
        self._diag_peak.setText(f"Peak: {peak:.3f}")
        self._diag_master_gain.setText(f"Master gain: {master_gain:.3f}")
        self._diag_clip_samples.setText(f"Clip samples: {clip_samples}")
        self._diag_non_finite.setText(f"Non-finite blocks: {non_finite_blocks}")
        self._diag_over_budget.setText(f"Over-budget callbacks: {over_budget}")
        self._diag_avg_callback.setText(f"Avg callback: {avg_callback_ms:.3f} ms")
        self._diag_max_callback.setText(f"Max callback: {max_callback_ms:.3f} ms")

    def set_midi_library(self, paths: list[str]):
        self._midi_library_paths = list(paths)
        self._apply_midi_library_filter()

    def _apply_midi_library_filter(self):
        query = self._midi_search.text().strip().lower() if hasattr(self, "_midi_search") else ""
        sort_mode = self._midi_sort_combo.currentData() if hasattr(self, "_midi_sort_combo") else "name_asc"
        selected_path = None
        current = self._midi_list.currentItem()
        if current:
            selected_path = current.data(Qt.ItemDataRole.UserRole)

        paths = list(self._midi_library_paths)
        if sort_mode == "name_desc":
            paths.sort(key=lambda value: os.path.basename(value).lower(), reverse=True)
        elif sort_mode == "mtime_desc":
            paths.sort(key=lambda value: os.path.getmtime(value) if os.path.exists(value) else 0, reverse=True)
        else:
            paths.sort(key=lambda value: os.path.basename(value).lower())

        self._midi_list.clear()
        added = 0
        for path in paths:
            name = os.path.basename(path)
            if query and query not in name.lower() and query not in path.lower():
                continue
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self._midi_list.addItem(item)
            added += 1
            if selected_path and selected_path == path:
                self._midi_list.setCurrentItem(item)
        if added == 0:
            empty_text = "No MIDI files match filter." if query else "No MIDI files found in library."
            item = QListWidgetItem(empty_text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsEnabled)
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
        if self._falling_notes.is_playing():
            self._play_btn.setText("Stop")
            self._play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
            if not self._recording:
                self._set_transport_state("playing")
        else:
            self._play_btn.setText("Play")
            self._play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def stop_playback(self):
        """Stop falling notes playback."""
        self._falling_notes.stop()
        self._play_btn.setText("Play")
        self._play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        if not self._recording:
            self._set_transport_state("idle")

    @property
    def falling_notes(self) -> FallingNotesWidget:
        """Access to falling notes widget for signal connections."""
        return self._falling_notes
