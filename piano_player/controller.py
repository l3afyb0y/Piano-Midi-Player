"""Top-level application controller for Piano Player."""

from __future__ import annotations

import os
import shutil
import tempfile

from PyQt6.QtCore import QObject, QSettings, QTimer, pyqtSignal

from audio.engine import AudioEngine
from audio.metronome import Metronome
from audio.simple_synth import SimpleSynth
from gui.falling_notes_widget import NoteEvent, SustainEvent
from gui.main_window import MainWindow
from midi.input import MidiInputThread, MidiMessage
from midi.recorder import MidiRecorder
from piano_player.config import (
    is_valid_soundfont_file,
    list_soundfont_candidates,
    resolve_midi_directory,
)
from piano_player.instruments import (
    DEFAULT_INSTRUMENT,
    SUPPORTED_INSTRUMENTS,
    normalize_instrument,
)
from piano_player.synth_modes import (
    SAMPLED_SYNTHS,
    SYNTH_SF2,
    SYNTH_SFZ,
    SYNTH_SIMPLE,
    normalize_synth_mode,
)
from piano_player.services.midi_files import MidiFileService
from piano_player.services.midi_library import MidiLibraryService
from recording.wav_recorder import WavRecorder


class PianoPlayerController(QObject):
    """Coordinates UI, MIDI input, recording, and audio playback."""

    midi_received = pyqtSignal(object)
    SUPPORTED_INSTRUMENTS = SUPPORTED_INSTRUMENTS
    SYNTH_SIMPLE = SYNTH_SIMPLE
    SYNTH_SF2 = SYNTH_SF2
    SYNTH_SFZ = SYNTH_SFZ
    SAMPLED_SYNTHS = SAMPLED_SYNTHS

    def __init__(self):
        super().__init__()

        self._settings = QSettings()
        if not self._settings.value("sfz_default_migrated", False, type=bool):
            legacy_mode = self._settings.value("synth_preference", "", type=str) or ""
            if legacy_mode == self.SYNTH_SF2:
                self._settings.setValue("synth_preference", self.SYNTH_SFZ)
            self._settings.setValue("sfz_default_migrated", True)
        if self._settings.contains("synth_preference"):
            raw_synth_preference = self._settings.value("synth_preference", self.SYNTH_SFZ, type=str)
        else:
            raw_synth_preference = self.SYNTH_SFZ
        self._preferred_synth = normalize_synth_mode(raw_synth_preference)
        saved_instrument = self._settings.value("instrument_preference", DEFAULT_INSTRUMENT, type=str)
        self._preferred_instrument = self._normalize_instrument(saved_instrument)
        self._soundfont_paths = self._load_soundfont_paths()
        self._migrate_retuned_piano_default()
        self._active_soundfont_path: str | None = None
        self._autoload_sampled = self._preferred_synth in self.SAMPLED_SYNTHS
        self._synth_name = self.SYNTH_SIMPLE
        self._cleanup_synths = []

        saved_midi_dir = self._settings.value("midi_folder", "", type=str)
        self._midi_library = MidiLibraryService(resolve_midi_directory(saved_midi_dir))
        self._ensure_midi_dir()

        self._synth = self._create_default_synth()
        self._engine = AudioEngine()
        self._engine.set_synth(self._synth)

        self._midi_thread = MidiInputThread()
        self._midi_recorder = MidiRecorder()
        self._wav_recorder: WavRecorder | None = None
        self._wav_path: str | None = None
        self._recording_offset = 0.0

        self._metronome = Metronome(sample_rate=self._engine.sample_rate)
        self._metronome_volume = float(self._settings.value("metronome_volume", 0.35, type=float) or 0.35)
        self._metronome.volume = self._metronome_volume
        self._metronome.set_click_callback(self._engine.queue_audio)
        self._metronome.beat.connect(self._on_metronome_beat)
        self._metronome_enabled = False
        self._count_in_enabled = False
        self._count_in_beats = 4
        self._count_in_remaining = 0
        self._count_in_active = False
        self._recording_started_playback = False
        self._metronome.set_meter(self._count_in_beats, self._count_in_beats)

        self._window = MainWindow()
        self._connect_signals()

        self._window.set_synth_selection(self._synth_name)
        self._window.set_instrument_selection(self._preferred_instrument)
        for instrument, path in self._soundfont_paths.items():
            self._window.set_instrument_soundfont_path(instrument, path)
        self._refresh_soundfont_options()
        self._window.set_midi_folder(str(self._midi_library.midi_dir))
        self._window.set_metronome_volume(self._metronome_volume)

        self._midi_thread.add_callback(self._on_midi_message)
        self._window.set_midi_status(False)
        self._window.set_audio_status(True, "Starting audio...")

    @property
    def window(self) -> MainWindow:
        return self._window

    def _create_default_synth(self):
        self._synth_name = self.SYNTH_SIMPLE
        return SimpleSynth(instrument=self._preferred_instrument)

    def _normalize_instrument(self, instrument: str | None) -> str:
        return normalize_instrument(instrument)

    @staticmethod
    def _soundfont_key(instrument: str) -> str:
        return f"soundfont_path_{instrument.lower()}"

    def _load_soundfont_paths(self) -> dict[str, str]:
        paths: dict[str, str] = {}
        for instrument in self.SUPPORTED_INSTRUMENTS:
            path = self._settings.value(self._soundfont_key(instrument), "", type=str) or ""
            if path:
                paths[instrument] = path

        # Backward compatibility for installs that only had one global key.
        legacy = self._settings.value("soundfont_path", "", type=str) or ""
        if legacy:
            for instrument in self.SUPPORTED_INSTRUMENTS:
                paths.setdefault(instrument, legacy)
        return paths

    def _migrate_retuned_piano_default(self):
        """Avoid auto-selecting retuned piano variants as defaults."""
        piano_path = self._soundfont_paths.get("Piano")
        if not piano_path:
            return
        lowered = os.path.basename(piano_path).lower()
        if "retuned" not in lowered:
            return

        parent = os.path.dirname(piano_path)
        filename = os.path.basename(piano_path)
        candidates = [
            filename.replace("Retuned-", "-"),
            filename.replace("Retuned", ""),
            "SalamanderGrandPiano-V3+20200602.sfz",
        ]
        for standard_name in candidates:
            candidate = os.path.join(parent, standard_name)
            if os.path.exists(candidate) and is_valid_soundfont_file(candidate):
                self._soundfont_paths["Piano"] = candidate
                self._settings.setValue(self._soundfont_key("Piano"), candidate)
                self._settings.setValue("soundfont_path", candidate)
                return

    def _set_soundfont_for_instrument(self, instrument: str, path: str):
        selected = self._normalize_instrument(instrument)
        normalized_path = os.path.abspath(path)
        self._soundfont_paths[selected] = normalized_path
        self._settings.setValue(self._soundfont_key(selected), normalized_path)
        # Keep legacy key for compatibility with previous versions.
        self._settings.setValue("soundfont_path", normalized_path)
        self._window.set_instrument_soundfont_path(selected, normalized_path)
        self._refresh_soundfont_options(selected)

    def _clear_soundfont_for_instrument(self, instrument: str):
        selected = self._normalize_instrument(instrument)
        self._soundfont_paths.pop(selected, None)
        self._settings.remove(self._soundfont_key(selected))
        self._window.set_instrument_soundfont_path(selected, None)
        self._refresh_soundfont_options(selected)

    def _refresh_soundfont_options(self, instrument: str | None = None):
        targets = (self._normalize_instrument(instrument),) if instrument else self.SUPPORTED_INSTRUMENTS
        for selected in targets:
            choices: list[tuple[str, str]] = [("Auto (Best Available)", "")]
            candidates = list_soundfont_candidates(selected)
            configured = self._soundfont_paths.get(selected)
            if configured and os.path.exists(configured) and configured not in candidates:
                candidates.insert(0, configured)
            for path in candidates:
                label = os.path.basename(path)
                choices.append((label, path))
            self._window.set_soundfont_options(selected, choices, configured)

    def _mode_matches_path(self, mode: str, path: str) -> bool:
        suffix = os.path.splitext(path)[1].lower()
        if mode == self.SYNTH_SF2:
            return suffix == ".sf2"
        if mode == self.SYNTH_SFZ:
            return suffix == ".sfz"
        return suffix in (".sf2", ".sfz")

    def _mode_for_path(self, path: str) -> str:
        suffix = os.path.splitext(path)[1].lower()
        if suffix == ".sfz":
            return self.SYNTH_SFZ
        return self.SYNTH_SF2

    def _preferred_instrument_file_for_mode(self, instrument: str, mode: str) -> str | None:
        selected = self._normalize_instrument(instrument)
        configured = self._soundfont_paths.get(selected)
        if configured and os.path.exists(configured) and self._mode_matches_path(mode, configured):
            return configured

        for candidate in list_soundfont_candidates(selected):
            if self._mode_matches_path(mode, candidate):
                return candidate
        return None

    def _preferred_sampled_target(self, instrument: str, preferred_mode: str) -> tuple[str, str] | None:
        """Resolve best sampled backend/path with SFZ-first fallback to SF2."""
        selected = self._normalize_instrument(instrument)
        mode_order = [preferred_mode]
        for fallback in (self.SYNTH_SFZ, self.SYNTH_SF2):
            if fallback not in mode_order:
                mode_order.append(fallback)

        for mode in mode_order:
            path = self._preferred_instrument_file_for_mode(selected, mode)
            if path:
                return mode, path
        return None

    def _iter_sampled_targets(self, instrument: str, preferred_mode: str):
        """Yield sampled backend candidates in fallback order."""
        selected = self._normalize_instrument(instrument)
        mode_order = [preferred_mode]
        for fallback in (self.SYNTH_SFZ, self.SYNTH_SF2):
            if fallback not in mode_order:
                mode_order.append(fallback)

        for mode in mode_order:
            path = self._preferred_instrument_file_for_mode(selected, mode)
            if path:
                yield mode, path

    def _apply_instrument(self, instrument: str):
        selected = self._normalize_instrument(instrument)
        self._preferred_instrument = selected
        selected_soundfont = self._soundfont_paths.get(selected)
        self._settings.setValue("instrument_preference", selected)
        if hasattr(self._synth, "set_instrument"):
            try:
                self._synth.set_instrument(selected)
            except Exception as exc:
                print(f"Failed to set instrument '{selected}': {exc}")
        self._window.set_instrument_selection(selected)
        self._window.set_instrument_soundfont_path(selected, selected_soundfont)
        self._refresh_soundfont_options(selected)

    def _set_synth(self, synth, name: str, persist_preference: bool = True):
        if self._synth is not synth and hasattr(self._synth, "cleanup"):
            if self._synth not in self._cleanup_synths:
                self._cleanup_synths.append(self._synth)

        self._synth = synth
        self._engine.set_synth(self._synth)
        self._synth_name = name
        self._autoload_sampled = name in self.SAMPLED_SYNTHS
        if persist_preference:
            self._preferred_synth = name
            self._settings.setValue("synth_preference", name)
        self._apply_instrument(self._preferred_instrument)
        self._window.set_synth_selection(name)

    def _set_simple_synth(self, persist_preference: bool = True):
        self._set_synth(
            SimpleSynth(instrument=self._preferred_instrument),
            self.SYNTH_SIMPLE,
            persist_preference=persist_preference,
        )

    def _load_soundfont(self, path: str, instrument: str | None = None, persist_preference: bool = True) -> bool:
        selected = self._normalize_instrument(instrument or self._preferred_instrument)
        normalized_path = os.path.abspath(path)
        suffix = os.path.splitext(normalized_path)[1].lower()

        synth = None
        loaded = False
        if suffix == ".sf2":
            try:
                from audio.soundfont_synth import SoundFontSynth
            except ImportError:
                print("SF2 support not available (install pyfluidsynth)")
                return False
            try:
                synth = SoundFontSynth(sample_rate=self._engine.sample_rate)
                loaded = bool(synth.load_soundfont(normalized_path))
            except Exception as exc:
                print(f"Failed to initialize/load SF2 backend: {exc}")
                if synth is not None and hasattr(synth, "cleanup"):
                    synth.cleanup()
                return False
        elif suffix == ".sfz":
            try:
                from audio.sfz_synth import SfizzSynth
            except ImportError as exc:
                print(f"SFZ support not available (install sfizz-lib): {exc}")
                return False
            try:
                synth = SfizzSynth(sample_rate=self._engine.sample_rate, block_size=self._engine.buffer_size)
                loaded = bool(synth.load_sfz(normalized_path))
            except Exception as exc:
                print(f"Failed to initialize/load SFZ backend: {exc}")
                if synth is not None and hasattr(synth, "cleanup"):
                    synth.cleanup()
                return False
        else:
            print(f"Unsupported instrument file type: {normalized_path}")
            return False

        if loaded and synth is not None:
            self._set_synth(synth, self._mode_for_path(normalized_path), persist_preference=persist_preference)
            self._active_soundfont_path = normalized_path
            self._set_soundfont_for_instrument(selected, normalized_path)
            self._apply_instrument(selected)
            return True
        if synth is not None and hasattr(synth, "cleanup"):
            synth.cleanup()
        return False

    def _try_load_sampled_target(
        self,
        instrument: str,
        requested_mode: str,
        keep_requested_preference: bool = True,
    ) -> bool:
        """Attempt sampled backend load with mode fallback order."""
        loaded = False
        for candidate_mode, candidate_path in self._iter_sampled_targets(instrument, requested_mode):
            if self._load_soundfont(
                candidate_path,
                instrument=instrument,
                persist_preference=(candidate_mode == requested_mode) if keep_requested_preference else True,
            ):
                loaded = True
                if candidate_mode != requested_mode:
                    print(f"{requested_mode} unavailable; fell back to {candidate_mode}.")
                break
        return loaded

    def _get_active_note_count(self) -> int:
        if hasattr(self._synth, "active_notes_count"):
            try:
                return int(self._synth.active_notes_count())
            except Exception:
                return 0
        if hasattr(self._synth, "_notes"):
            try:
                return len(self._synth._notes)
            except Exception:
                return 0
        return 0

    def _connect_signals(self):
        self._window.volume_changed.connect(self._on_volume_changed)
        self._window.synth_changed.connect(self._on_synth_changed)
        self._window.instrument_changed.connect(self._on_instrument_changed)
        self._window.soundfont_loaded.connect(self._on_soundfont_loaded)
        self._window.soundfont_selected.connect(self._on_soundfont_selected)
        self._window.record_toggled.connect(self._on_record_toggled)
        self._window.save_wav.connect(self._on_save_wav)
        self._window.save_midi.connect(self._on_save_midi)
        self._window.open_midi_file.connect(self._on_open_midi_file)
        self._window.save_midi_file.connect(self._on_save_midi_file)
        self._window.midi_folder_changed.connect(self._on_midi_folder_changed)
        self._window.midi_library_refresh.connect(self._refresh_midi_library)
        self._window.midi_files_dropped.connect(self._on_midi_files_dropped)
        self._window.play_recording.connect(self._on_play_recording)
        self._window.count_in_enabled_changed.connect(self._on_count_in_enabled_changed)
        self._window.count_in_beats_changed.connect(self._on_count_in_beats_changed)
        self._window.midi_input_changed.connect(self._on_midi_input_changed)
        self._window.audio_output_changed.connect(self._on_audio_output_changed)
        self._window.metronome_volume_changed.connect(self._on_metronome_volume_changed)
        self._window.keyboard_note_pressed.connect(self._on_ui_keyboard_note_on)
        self._window.keyboard_note_released.connect(self._on_ui_keyboard_note_off)
        self._window.debug_reset_requested.connect(self._on_debug_reset_requested)

        self._window.falling_notes.note_triggered.connect(self._on_playback_note_on)
        self._window.falling_notes.note_released.connect(self._on_playback_note_off)
        self._window.falling_notes.sustain_triggered.connect(self._on_playback_sustain)
        self._window.falling_notes.playback_finished.connect(self._on_playback_finished)

        self._window.metronome_toggled.connect(self._on_metronome_toggled)
        self._window.metronome_bpm_changed.connect(self._on_metronome_bpm_changed)

        self.midi_received.connect(self._handle_midi_in_main_thread)

    def _on_midi_message(self, msg: MidiMessage):
        if msg.type == "note_on":
            self._synth.note_on(msg.note, msg.velocity)
        elif msg.type == "note_off":
            self._synth.note_off(msg.note)
        elif msg.type == "sustain":
            if msg.value:
                self._synth.sustain_on()
            else:
                self._synth.sustain_off()

        self.midi_received.emit(msg)

    def _refresh_device_lists(self):
        try:
            midi_ports = MidiInputThread.list_ports()
        except Exception:
            midi_ports = []
        self._window.set_midi_inputs(midi_ports, self._midi_thread.connected_port)

        try:
            outputs = AudioEngine.list_output_devices()
        except Exception:
            outputs = []
        selected_output = self._engine.output_device
        self._window.set_audio_outputs(outputs, selected_output)
        if selected_output is None:
            self._window.set_audio_status(True, "Default output")
        else:
            output_lookup = {idx: name for idx, name in outputs}
            self._window.set_audio_status(True, output_lookup.get(selected_output, f"Device {selected_output}"))
        self._update_debug_diagnostics()

    def _handle_midi_in_main_thread(self, msg: MidiMessage):
        if msg.type == "note_on":
            self._window.keyboard_note_on(msg.note, msg.velocity)
            if self._midi_recorder.is_recording:
                self._midi_recorder.note_on(msg.note, msg.velocity)
        elif msg.type == "note_off":
            self._window.keyboard_note_off(msg.note)
            if self._midi_recorder.is_recording:
                self._midi_recorder.note_off(msg.note)
        elif msg.type == "sustain":
            self._window.set_sustain_status(msg.value)
            if self._midi_recorder.is_recording:
                self._midi_recorder.sustain(msg.value)

        self._window.set_notes_count(self._get_active_note_count())

    def _on_volume_changed(self, volume: float):
        self._engine.volume = volume

    def _on_synth_changed(self, name: str):
        mode = normalize_synth_mode(name)
        if mode == self.SYNTH_SIMPLE:
            self._set_simple_synth(persist_preference=True)
            return

        if mode not in self.SAMPLED_SYNTHS:
            return

        # Preserve requested backend as preference even when we temporarily fall back.
        self._preferred_synth = mode
        self._autoload_sampled = True
        self._settings.setValue("synth_preference", mode)

        if self._synth_name == mode:
            return

        if self._try_load_sampled_target(self._preferred_instrument, mode, keep_requested_preference=True):
            return

        print(f"{mode} selected but no compatible sampled backend/file is available for {self._preferred_instrument}.")
        # Keep UI honest with actual active backend.
        self._window.set_synth_selection(self._synth_name)

    def _on_instrument_changed(self, instrument: str):
        self._apply_instrument(instrument)
        if self._synth_name not in self.SAMPLED_SYNTHS:
            return

        preferred_mode = self._preferred_synth if self._preferred_synth in self.SAMPLED_SYNTHS else self._synth_name
        target = self._preferred_sampled_target(self._preferred_instrument, preferred_mode)
        if not target:
            return
        mode, preferred_path = target
        if self._active_soundfont_path and os.path.abspath(preferred_path) == self._active_soundfont_path:
            return
        if not self._load_soundfont(
            preferred_path,
            instrument=self._preferred_instrument,
            persist_preference=(mode == preferred_mode),
        ):
            print(f"Failed to load instrument file for {self._preferred_instrument}: {preferred_path}")
            return

    def _on_soundfont_loaded(self, path: str):
        if not self._load_soundfont(path, instrument=self._preferred_instrument):
            print("Failed to load instrument file.")

    def _on_soundfont_selected(self, path: str):
        selected = self._preferred_instrument
        normalized = os.path.abspath(path) if path else ""
        if not normalized:
            self._clear_soundfont_for_instrument(selected)
            fallback = self._preferred_instrument_file_for_mode(selected, self._synth_name)
            if self._synth_name in self.SAMPLED_SYNTHS:
                if fallback and (not self._active_soundfont_path or os.path.abspath(fallback) != self._active_soundfont_path):
                    if not self._load_soundfont(fallback, instrument=selected):
                        print(f"Failed to load auto instrument file for {selected}.")
                elif not fallback:
                    print(f"No compatible instrument file available for {selected} in {self._synth_name} mode.")
            return

        if not is_valid_soundfont_file(normalized):
            print(f"Invalid instrument file: {normalized}")
            self._refresh_soundfont_options(selected)
            return

        if self._synth_name in self.SAMPLED_SYNTHS:
            if not self._mode_matches_path(self._synth_name, normalized):
                self._set_soundfont_for_instrument(selected, normalized)
                print(f"Selected file is incompatible with {self._synth_name}. Switch synth mode to use it.")
                return
            if self._active_soundfont_path and self._active_soundfont_path == normalized:
                self._set_soundfont_for_instrument(selected, normalized)
                return
            if not self._load_soundfont(normalized, instrument=selected):
                print(f"Failed to load selected instrument file for {selected}: {normalized}")
                self._refresh_soundfont_options(selected)
                return
            return

        self._set_soundfont_for_instrument(selected, normalized)

    def _on_record_toggled(self, recording: bool):
        if recording:
            if self._count_in_active:
                return
            if self._count_in_enabled and self._count_in_beats > 0 and not self._window.falling_notes.is_playing():
                self._start_count_in()
                return
            self._start_recording()
            return

        self._cancel_count_in()
        self._stop_recording()

    def _start_recording(self):
        self._recording_offset = self._window.falling_notes.get_current_time()
        self._midi_recorder.start()

        fd, self._wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        self._wav_recorder = WavRecorder(self._wav_path, sample_rate=self._engine.sample_rate)
        self._wav_recorder.start()
        self._engine.set_audio_callback(self._wav_recorder.write)

        self._recording_started_playback = False
        if self._window.falling_notes.has_events() and not self._window.falling_notes.is_playing():
            self._window.start_playback()
            self._recording_started_playback = True

        self._window.set_recording_state(True)

    def _stop_recording(self):
        self._midi_recorder.stop()
        if self._wav_recorder:
            self._wav_recorder.stop()
            self._engine.set_audio_callback(None)
            self._wav_recorder = None

        if self._recording_started_playback:
            self._window.stop_playback()
        self._recording_started_playback = False

        self._window.set_recording_state(False)

        events = self._midi_recorder.get_events()
        if events:
            note_events = MidiFileService.recorder_events_to_notes(events, self._recording_offset)
            sustain_events = MidiFileService.recorder_events_to_sustain(events, self._recording_offset)
            self._merge_recorded_events(note_events, sustain_events)

    def _on_save_wav(self, path: str):
        if self._wav_path:
            shutil.copy(self._wav_path, path)
            print(f"Saved WAV to: {path}")

    def _on_count_in_enabled_changed(self, enabled: bool):
        self._count_in_enabled = enabled

    def _on_count_in_beats_changed(self, beats: int):
        self._count_in_beats = max(1, beats)
        self._metronome.set_meter(self._count_in_beats, self._count_in_beats)
        self._metronome.reset_counter()

    def _on_midi_input_changed(self, port_name: str):
        requested_port = port_name.strip() if port_name else None
        if requested_port and requested_port == self._midi_thread.connected_port:
            return

        self._midi_thread.stop()
        self._midi_thread = MidiInputThread(port_name=requested_port)
        self._midi_thread.add_callback(self._on_midi_message)
        self._midi_thread.start()

        if self._midi_thread.connected_port:
            self._window.set_midi_status(True, self._midi_thread.connected_port)
        else:
            self._window.set_midi_status(False)
        self._refresh_device_lists()

    def _on_audio_output_changed(self, device_index: int):
        target_device = None if device_index < 0 else device_index
        ok = self._engine.set_output_device(target_device)
        if not ok:
            self._window.set_audio_status(False)
            return
        self._refresh_device_lists()

    def _start_count_in(self):
        self._count_in_active = True
        self._count_in_remaining = self._count_in_beats
        self._metronome.reset_counter()
        self._window.set_count_in_state(True, self._count_in_remaining)
        if not self._metronome.is_running():
            self._metronome.start()

    def _cancel_count_in(self):
        if not self._count_in_active:
            return
        self._count_in_active = False
        self._count_in_remaining = 0
        self._window.set_count_in_state(False, 0)
        if not self._metronome_enabled and self._metronome.is_running():
            self._metronome.stop()

    def _on_metronome_beat(self):
        if not self._count_in_active or self._count_in_remaining <= 0:
            return

        self._window.set_count_in_state(True, self._count_in_remaining)
        self._count_in_remaining -= 1
        if self._count_in_remaining > 0:
            return

        self._count_in_active = False
        self._window.set_count_in_state(False, 0)
        if not self._metronome_enabled and self._metronome.is_running():
            self._metronome.stop()
        self._start_recording()

    def _on_save_midi(self, path: str):
        self._save_roll_midi(path)

    def _on_open_midi_file(self, path: str):
        try:
            note_events, sustain_events = MidiFileService.load(path)
        except Exception as exc:
            print(f"Failed to load MIDI file: {exc}")
            return

        self._window.set_midi_file_info(path)
        self._window.load_recording(note_events, sustain_events)

    def _on_save_midi_file(self, path: str):
        self._save_roll_midi(path)

    def _save_roll_midi(self, path: str):
        note_events = self._window.falling_notes.get_events()
        sustain_events = self._window.falling_notes.get_sustain_events()
        if not note_events and not sustain_events:
            print("No MIDI events to save.")
            return

        try:
            MidiFileService.save(path, note_events, sustain_events)
        except Exception as exc:
            print(f"Failed to save MIDI file: {exc}")
            return

        print(f"Saved MIDI to: {path}")

    def _on_play_recording(self):
        events = self._midi_recorder.get_events()
        if not events:
            print("No recorded MIDI to play.")
            return

        note_events = MidiFileService.recorder_events_to_notes(events)
        sustain_events = MidiFileService.recorder_events_to_sustain(events)
        self._window.load_recording(note_events, sustain_events)
        self._window.start_playback()

    def _merge_recorded_events(self, note_events: list[NoteEvent], sustain_events: list[SustainEvent]):
        if not note_events and not sustain_events:
            return

        existing_notes = self._window.falling_notes.get_events()
        existing_sustain = self._window.falling_notes.get_sustain_events()
        combined_notes = sorted(existing_notes + note_events, key=lambda e: e.start_time)
        combined_sustain = sorted(existing_sustain + sustain_events, key=lambda e: e.time)

        current_time = self._window.falling_notes.get_current_time()
        was_playing = self._window.falling_notes.is_playing()
        if was_playing:
            self._window.falling_notes.stop()

        self._window.falling_notes.load_events(combined_notes, combined_sustain)
        self._window.falling_notes.seek(current_time)

        if was_playing:
            self._window.falling_notes.play()

    def _ensure_midi_dir(self):
        try:
            self._midi_library.ensure_dir()
        except Exception as exc:
            print(f"Failed to create MIDI folder '{self._midi_library.midi_dir}': {exc}")

    def _on_midi_folder_changed(self, path: str):
        if not path:
            return

        self._midi_library.set_midi_dir(path)
        self._ensure_midi_dir()
        self._settings.setValue("midi_folder", str(self._midi_library.midi_dir))
        self._window.set_midi_folder(str(self._midi_library.midi_dir))
        self._refresh_midi_library()

    def _refresh_midi_library(self):
        self._window.set_midi_library(self._midi_library.list_files())

    def _on_midi_files_dropped(self, paths: list[str]):
        if not paths:
            return

        self._ensure_midi_dir()
        self._window.set_midi_folder(str(self._midi_library.midi_dir))
        moved_any = self._midi_library.import_files(paths)
        if moved_any:
            self._refresh_midi_library()

    def _on_playback_note_on(self, note: int, velocity: int):
        self._synth.note_on(note, velocity)
        self._window.keyboard_note_on(note, velocity)

    def _on_playback_note_off(self, note: int):
        self._synth.note_off(note)
        self._window.keyboard_note_off(note)

    def _on_ui_keyboard_note_on(self, note: int, velocity: int):
        self._synth.note_on(note, velocity)
        if self._midi_recorder.is_recording:
            self._midi_recorder.note_on(note, velocity)
        self._window.set_notes_count(self._get_active_note_count())

    def _on_ui_keyboard_note_off(self, note: int):
        self._synth.note_off(note)
        if self._midi_recorder.is_recording:
            self._midi_recorder.note_off(note)
        self._window.set_notes_count(self._get_active_note_count())

    def _on_playback_sustain(self, on: bool):
        if on:
            self._synth.sustain_on()
        else:
            self._synth.sustain_off()
        self._window.set_sustain_status(on)

    def _on_playback_finished(self):
        self._window.stop_playback()

    def _on_metronome_toggled(self, on: bool):
        self._metronome_enabled = on
        if on:
            self._metronome.start()
        elif not self._count_in_active:
            self._metronome.stop()

    def _on_metronome_bpm_changed(self, bpm: int):
        self._metronome.bpm = bpm

    def _on_metronome_volume_changed(self, volume: float):
        clamped = max(0.0, min(1.0, float(volume)))
        self._metronome_volume = clamped
        self._metronome.volume = clamped
        self._settings.setValue("metronome_volume", clamped)

    def _on_debug_reset_requested(self):
        self._engine.reset_runtime_stats()
        self._update_debug_diagnostics()

    def _resolve_output_label(self) -> str:
        selected_output = self._engine.output_device
        if selected_output is None:
            return "Default output"
        try:
            for idx, name in AudioEngine.list_output_devices():
                if int(idx) == int(selected_output):
                    return name
        except Exception:
            pass
        return f"Device {selected_output}"

    def _update_debug_diagnostics(self):
        stats = self._engine.get_runtime_stats()
        stats["backend"] = self._synth_name
        stats["active_notes"] = self._get_active_note_count()
        stats["output"] = self._resolve_output_label()
        self._window.set_diagnostics(stats)

    def start(self):
        self._engine.start()
        self._window.show()
        self._debug_timer = QTimer(self)
        self._debug_timer.setInterval(300)
        self._debug_timer.timeout.connect(self._update_debug_diagnostics)
        self._debug_timer.start()
        self._update_debug_diagnostics()
        QTimer.singleShot(0, self._complete_startup_init)
        if self._autoload_sampled:
            QTimer.singleShot(150, self._autoload_preferred_soundfont)

    def _complete_startup_init(self):
        self._refresh_midi_library()
        try:
            self._midi_thread.start()
        except Exception as exc:
            print(f"Failed to start MIDI input: {exc}")

        if self._midi_thread.connected_port:
            self._window.set_midi_status(True, self._midi_thread.connected_port)
        else:
            self._window.set_midi_status(False)
        self._refresh_device_lists()

    def _autoload_preferred_soundfont(self):
        if not self._autoload_sampled or self._synth_name in self.SAMPLED_SYNTHS:
            return

        try:
            loaded = self._try_load_sampled_target(
                self._preferred_instrument,
                self._preferred_synth,
                keep_requested_preference=True,
            )
        except Exception as exc:
            # Never crash startup because a sampled backend failed to initialize.
            print(f"Failed to auto-load sampled instrument file: {exc}")
            loaded = False
        if not loaded:
            print("No sampled backend/file combination could be auto-loaded; staying on current synth.")

    def stop(self):
        if hasattr(self, "_debug_timer"):
            self._debug_timer.stop()
        self._midi_thread.stop()
        self._metronome.stop()
        self._engine.stop()
        seen = set()
        for synth in self._cleanup_synths + [self._synth]:
            if hasattr(synth, "cleanup") and id(synth) not in seen:
                synth.cleanup()
                seen.add(id(synth))
