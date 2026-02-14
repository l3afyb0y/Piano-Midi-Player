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
from piano_player.config import find_default_soundfont, resolve_midi_directory
from piano_player.services.midi_files import MidiFileService
from piano_player.services.midi_library import MidiLibraryService
from recording.wav_recorder import WavRecorder


class PianoPlayerController(QObject):
    """Coordinates UI, MIDI input, recording, and audio playback."""

    midi_received = pyqtSignal(object)

    def __init__(self):
        super().__init__()

        self._settings = QSettings()
        self._soundfont_path = self._settings.value("soundfont_path", "", type=str) or None
        self._preferred_synth = self._settings.value("synth_preference", "Simple Synth", type=str)
        self._preferred_instrument = self._settings.value("instrument_preference", "Piano", type=str)
        self._autoload_soundfont = self._preferred_synth == "SoundFont"
        self._synth_name = "Simple Synth"
        self._cleanup_synths = []
        self._loaded_midi_path: str | None = None

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

        self._metronome = Metronome()
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
        self._window.set_midi_folder(str(self._midi_library.midi_dir))

        self._midi_thread.add_callback(self._on_midi_message)
        self._window.set_midi_status(False)
        self._window.set_audio_status(True, "Starting audio...")

    @property
    def window(self) -> MainWindow:
        return self._window

    def _create_default_synth(self):
        self._synth_name = "Simple Synth"
        print("Using simple synthesizer")
        return SimpleSynth(instrument=self._preferred_instrument)

    def _apply_instrument(self, instrument: str):
        selected = instrument if instrument in ("Piano", "Guitar") else "Piano"
        self._preferred_instrument = selected
        self._settings.setValue("instrument_preference", selected)
        if hasattr(self._synth, "set_instrument"):
            try:
                self._synth.set_instrument(selected)
            except Exception as exc:
                print(f"Failed to set instrument '{selected}': {exc}")
        self._window.set_instrument_selection(selected)

    def _set_synth(self, synth, name: str, soundfont_path: str | None = None):
        if self._synth is not synth and hasattr(self._synth, "cleanup"):
            if self._synth not in self._cleanup_synths:
                self._cleanup_synths.append(self._synth)

        self._synth = synth
        self._engine.set_synth(self._synth)
        self._synth_name = name
        self._preferred_synth = name
        self._autoload_soundfont = name == "SoundFont"
        self._settings.setValue("synth_preference", name)
        if soundfont_path is not None:
            self._soundfont_path = soundfont_path
            self._settings.setValue("soundfont_path", soundfont_path)
        self._apply_instrument(self._preferred_instrument)
        self._window.set_synth_selection(name)

    def _load_soundfont(self, path: str) -> bool:
        try:
            from audio.soundfont_synth import SoundFontSynth
        except ImportError:
            print("SoundFont support not available (install pyfluidsynth)")
            return False

        sf_synth = SoundFontSynth()
        if sf_synth.load_soundfont(path):
            self._set_synth(sf_synth, "SoundFont", soundfont_path=path)
            return True
        return False

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
        if name == "Simple Synth":
            self._set_synth(SimpleSynth(instrument=self._preferred_instrument), "Simple Synth")
            return

        if name != "SoundFont":
            return

        if hasattr(self._synth, "_fs"):
            return

        soundfont_path = self._soundfont_path or find_default_soundfont()
        if soundfont_path and self._load_soundfont(soundfont_path):
            return

        print("SoundFont selected but no file is loaded yet.")

    def _on_instrument_changed(self, instrument: str):
        self._apply_instrument(instrument)

    def _on_soundfont_loaded(self, path: str):
        if not self._load_soundfont(path):
            print("Failed to load SoundFont.")

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
        self._wav_recorder = WavRecorder(self._wav_path)
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

    def _on_open_midi_file(self, path: str):
        try:
            note_events, sustain_events = MidiFileService.load(path)
        except Exception as exc:
            print(f"Failed to load MIDI file: {exc}")
            return

        self._loaded_midi_path = path
        self._window.set_midi_file_info(path)
        self._window.load_recording(note_events, sustain_events)

    def _on_save_midi_file(self, path: str):
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

    def start(self):
        self._engine.start()
        self._window.show()
        QTimer.singleShot(0, self._complete_startup_init)
        if self._autoload_soundfont:
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
        if not self._autoload_soundfont or self._synth_name == "SoundFont":
            return

        path = self._soundfont_path or find_default_soundfont()
        if not path:
            return

        if self._load_soundfont(path):
            print(f"Auto-loaded preferred SoundFont: {path}")

    def stop(self):
        self._midi_thread.stop()
        self._metronome.stop()
        self._engine.stop()
        seen = set()
        for synth in self._cleanup_synths + [self._synth]:
            if hasattr(synth, "cleanup") and id(synth) not in seen:
                synth.cleanup()
                seen.add(id(synth))
