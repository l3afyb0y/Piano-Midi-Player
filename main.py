#!/usr/bin/env python3
"""Piano Player - MIDI to audio application."""

import sys
import os
import tempfile
import shutil
from pathlib import Path
import mido
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QSettings

from gui.main_window import MainWindow
from gui.falling_notes_widget import NoteEvent, SustainEvent
from audio.engine import AudioEngine
from audio.simple_synth import SimpleSynth
from audio.metronome import Metronome
from midi.input import MidiInputThread, MidiMessage
from midi.recorder import MidiRecorder
from recording.wav_recorder import WavRecorder

PROJECT_DIR = Path(__file__).resolve().parent
SOUNDFONTS_DIR = PROJECT_DIR / "soundfonts"
DEFAULT_SOUNDFONT_LOCATIONS = [
    os.environ.get("PIANO_PLAYER_SOUNDFONT"),
    os.environ.get("SOUNDFONT_PATH"),
    str(SOUNDFONTS_DIR / "default.sf2"),
    str(SOUNDFONTS_DIR / "FluidR3_GM.sf2"),
    "/usr/share/soundfonts/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/TimGM6mb.sf2",
    "/Library/Audio/Sounds/Banks/FluidR3_GM.sf2",
]
DEFAULT_MIDI_DIR = Path.home() / "midi"


def find_default_soundfont() -> str | None:
    """Return a usable SoundFont path if one is available."""
    for candidate in DEFAULT_SOUNDFONT_LOCATIONS:
        if candidate and os.path.exists(candidate):
            return candidate

    if SOUNDFONTS_DIR.is_dir():
        for path in sorted(SOUNDFONTS_DIR.glob("*.sf2")):
            return str(path)

    return None


class PianoPlayer(QObject):
    """Main application controller."""

    # Signal to update UI from MIDI thread
    midi_received = pyqtSignal(object)

    def __init__(self):
        super().__init__()

        self._soundfont_path = None
        self._synth_name = "Simple Synth"
        self._cleanup_synths = []
        self._loaded_midi_path: str | None = None
        self._settings = QSettings()
        self._midi_dir = self._load_midi_dir()
        self._ensure_midi_dir()

        # Create components - try SoundFont first, fall back to simple synth
        self._synth = self._create_default_synth()
        self._engine = AudioEngine()
        self._engine.set_synth(self._synth)

        self._midi_thread = MidiInputThread()
        self._midi_recorder = MidiRecorder()
        self._wav_recorder = None
        self._wav_path = None
        self._recording_offset = 0.0

        # Metronome
        self._metronome = Metronome()
        self._metronome.set_click_callback(self._engine.queue_audio)
        self._metronome.beat.connect(self._on_metronome_beat)
        self._metronome_enabled = False
        self._count_in_enabled = False
        self._count_in_beats = 4
        self._count_in_remaining = 0
        self._count_in_active = False
        self._recording_started_playback = False

        # Create window
        self._window = MainWindow()

        # Connect signals
        self._connect_signals()

        # Sync UI with active synth
        self._window.set_synth_selection(self._synth_name)
        self._window.set_midi_folder(str(self._midi_dir))
        self._refresh_midi_library()

        # Start MIDI input
        self._midi_thread.add_callback(self._on_midi_message)
        self._midi_thread.start()

        # Wait briefly for MIDI thread to connect
        import time
        time.sleep(0.1)

        # Update MIDI status
        if self._midi_thread.connected_port:
            self._window.set_midi_status(True, self._midi_thread.connected_port)

    def _create_default_synth(self):
        """Create default synthesizer - SoundFont if available, else simple synth."""
        default_soundfont = find_default_soundfont()
        if default_soundfont:
            try:
                from audio.soundfont_synth import SoundFontSynth
                sf_synth = SoundFontSynth()
                if sf_synth.load_soundfont(default_soundfont):
                    self._soundfont_path = default_soundfont
                    self._synth_name = "SoundFont"
                    print(f"Using SoundFont: {default_soundfont}")
                    return sf_synth
            except Exception as e:
                print(f"Could not load SoundFont: {e}")

        self._synth_name = "Simple Synth"
        print("Using simple synthesizer")
        return SimpleSynth()

    def _set_synth(self, synth, name: str, soundfont_path: str | None = None):
        """Swap synthesizers and keep UI in sync."""
        if self._synth is not synth and hasattr(self._synth, "cleanup"):
            if self._synth not in self._cleanup_synths:
                self._cleanup_synths.append(self._synth)

        self._synth = synth
        self._engine.set_synth(self._synth)
        self._synth_name = name
        if soundfont_path is not None:
            self._soundfont_path = soundfont_path
        if hasattr(self, "_window"):
            self._window.set_synth_selection(name)

    def _load_soundfont(self, path: str) -> bool:
        """Load a SoundFont and swap synths. Returns True on success."""
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
        """Return active note count for the current synth."""
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
        """Connect UI signals to handlers."""
        self._window.volume_changed.connect(self._on_volume_changed)
        self._window.synth_changed.connect(self._on_synth_changed)
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

        # Falling notes playback signals
        self._window.falling_notes.note_triggered.connect(self._on_playback_note_on)
        self._window.falling_notes.note_released.connect(self._on_playback_note_off)
        self._window.falling_notes.sustain_triggered.connect(self._on_playback_sustain)
        self._window.falling_notes.playback_finished.connect(self._on_playback_finished)

        # Metronome signals
        self._window.metronome_toggled.connect(self._on_metronome_toggled)
        self._window.metronome_bpm_changed.connect(self._on_metronome_bpm_changed)

        # Thread-safe MIDI handling
        self.midi_received.connect(self._handle_midi_in_main_thread)

    def _on_midi_message(self, msg: MidiMessage):
        """Called from MIDI thread - handle audio immediately, UI via signal."""
        # Audio: call synth directly for lowest latency (thread-safe in FluidSynth)
        if msg.type == "note_on":
            self._synth.note_on(msg.note, msg.velocity)
        elif msg.type == "note_off":
            self._synth.note_off(msg.note)
        elif msg.type == "sustain":
            if msg.value:
                self._synth.sustain_on()
            else:
                self._synth.sustain_off()

        # UI updates: route through Qt event loop (can tolerate latency)
        self.midi_received.emit(msg)

    def _handle_midi_in_main_thread(self, msg: MidiMessage):
        """Handle MIDI message in main thread - UI updates only."""
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

        # Update note count
        self._window.set_notes_count(self._get_active_note_count())

    def _on_volume_changed(self, volume: float):
        self._engine.volume = volume

    def _on_synth_changed(self, name: str):
        if name == "Simple Synth":
            self._set_synth(SimpleSynth(), "Simple Synth")
        elif name == "SoundFont":
            if hasattr(self._synth, "_fs"):
                return
            soundfont_path = self._soundfont_path
            if soundfont_path is None:
                soundfont_path = find_default_soundfont()
            if soundfont_path and self._load_soundfont(soundfont_path):
                return
            print("SoundFont selected but no file is loaded yet.")

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
        else:
            self._cancel_count_in()
            self._stop_recording()

    def _start_recording(self):
        self._recording_offset = self._window.falling_notes.get_current_time()
        self._midi_recorder.start()
        # Create temp WAV file
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
            note_events = self._convert_to_note_events(events, self._recording_offset)
            sustain_events = self._convert_to_sustain_events(events, self._recording_offset)
            self._merge_recorded_events(note_events, sustain_events)

    def _on_save_wav(self, path: str):
        if self._wav_path:
            shutil.copy(self._wav_path, path)
            print(f"Saved WAV to: {path}")

    def _on_count_in_enabled_changed(self, enabled: bool):
        self._count_in_enabled = enabled

    def _on_count_in_beats_changed(self, beats: int):
        self._count_in_beats = max(1, beats)

    def _start_count_in(self):
        self._count_in_active = True
        self._count_in_remaining = self._count_in_beats
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
        if not self._count_in_active:
            return
        if self._count_in_remaining <= 0:
            return
        self._window.set_count_in_state(True, self._count_in_remaining)
        self._count_in_remaining -= 1
        if self._count_in_remaining <= 0:
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
            self._save_midi_file(path, note_events, sustain_events)
        except Exception as e:
            print(f"Failed to save MIDI file: {e}")
            return
        print(f"Saved MIDI to: {path}")

    def _on_open_midi_file(self, path: str):
        try:
            note_events, sustain_events = self._load_midi_file(path)
        except Exception as e:
            print(f"Failed to load MIDI file: {e}")
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
            self._save_midi_file(path, note_events, sustain_events)
        except Exception as e:
            print(f"Failed to save MIDI file: {e}")
            return
        print(f"Saved MIDI to: {path}")

    def _on_play_recording(self):
        """Convert recorded events to NoteEvents and start playback."""
        events = self._midi_recorder.get_events()
        if not events:
            print("No recorded MIDI to play.")
            return
        note_events = self._convert_to_note_events(events)
        sustain_events = self._convert_to_sustain_events(events)
        self._window.load_recording(note_events, sustain_events)
        self._window.start_playback()

    def _convert_to_note_events(self, events: list, offset: float = 0.0) -> list[NoteEvent]:
        """Convert MIDI recorder events to NoteEvent objects."""
        # Track note_on events to pair with note_off
        active_notes: dict[int, tuple[float, int]] = {}  # note -> (start_time, velocity)
        note_events = []

        for event in events:
            if event['type'] == 'note_on':
                active_notes[event['note']] = (event['time'], event['velocity'])
            elif event['type'] == 'note_off':
                if event['note'] in active_notes:
                    start_time, velocity = active_notes.pop(event['note'])
                    duration = max(0.0, event['time'] - start_time)
                    note_events.append(NoteEvent(
                        note=event['note'],
                        start_time=offset + start_time,
                        duration=duration,
                        velocity=velocity
                    ))

        return note_events

    def _convert_to_sustain_events(self, events: list, offset: float = 0.0) -> list[SustainEvent]:
        """Convert MIDI recorder events to SustainEvent objects."""
        sustain_events = []
        for event in events:
            if event['type'] == 'sustain':
                sustain_events.append(SustainEvent(
                    time=offset + event['time'],
                    on=event['value']
                ))
        return sustain_events

    def _merge_recorded_events(
        self,
        note_events: list[NoteEvent],
        sustain_events: list[SustainEvent],
    ):
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

    def _load_midi_dir(self) -> Path:
        saved = self._settings.value("midi_folder", "", type=str)
        if saved:
            return Path(saved).expanduser()
        return DEFAULT_MIDI_DIR

    def _ensure_midi_dir(self):
        try:
            self._midi_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Failed to create MIDI folder '{self._midi_dir}': {e}")

    def _on_midi_folder_changed(self, path: str):
        if not path:
            return
        self._midi_dir = Path(path).expanduser()
        self._ensure_midi_dir()
        self._settings.setValue("midi_folder", str(self._midi_dir))
        self._window.set_midi_folder(str(self._midi_dir))
        self._refresh_midi_library()

    def _refresh_midi_library(self):
        if not self._midi_dir or not self._midi_dir.exists():
            self._window.set_midi_library([])
            return
        midi_files = [
            str(path)
            for path in sorted(self._midi_dir.iterdir())
            if path.is_file() and path.suffix.lower() in (".mid", ".midi")
        ]
        self._window.set_midi_library(midi_files)

    @staticmethod
    def _unique_destination(directory: Path, filename: str) -> Path:
        candidate = directory / filename
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        for idx in range(1, 1000):
            alt = directory / f"{stem}-{idx}{suffix}"
            if not alt.exists():
                return alt
        raise FileExistsError(f"Could not find unique filename for {filename}")

    def _on_midi_files_dropped(self, paths: list[str]):
        if not paths:
            return
        if not self._midi_dir:
            self._midi_dir = DEFAULT_MIDI_DIR
            self._ensure_midi_dir()
            self._window.set_midi_folder(str(self._midi_dir))

        moved_any = False
        dest_dir = self._midi_dir
        for path in paths:
            src = Path(path)
            if not src.exists() or src.suffix.lower() not in (".mid", ".midi"):
                continue
            try:
                if src.resolve().parent == dest_dir.resolve():
                    moved_any = True
                    continue
            except Exception:
                pass

            dest = self._unique_destination(dest_dir, src.name)
            try:
                shutil.move(str(src), str(dest))
                moved_any = True
            except Exception as e:
                print(f"Failed to move '{src}' to '{dest}': {e}")

        if moved_any:
            self._refresh_midi_library()

    @staticmethod
    def _load_midi_file(path: str) -> tuple[list[NoteEvent], list[SustainEvent]]:
        """Load a MIDI file and convert to NoteEvent/SustainEvent lists."""
        midi_file = mido.MidiFile(path)
        tempo = 500000  # Default 120 BPM
        current_time = 0.0
        active_notes: dict[tuple[int, int], list[tuple[float, int]]] = {}
        note_events: list[NoteEvent] = []
        sustain_events: list[SustainEvent] = []

        for msg in mido.merge_tracks(midi_file.tracks):
            current_time += mido.tick2second(msg.time, midi_file.ticks_per_beat, tempo)
            if msg.type == "set_tempo":
                tempo = msg.tempo
                continue

            if msg.type == "note_on" and msg.velocity > 0:
                key = (getattr(msg, "channel", 0), msg.note)
                active_notes.setdefault(key, []).append((current_time, msg.velocity))
            elif msg.type in ("note_off", "note_on"):
                if msg.type == "note_on" and msg.velocity > 0:
                    continue
                key = (getattr(msg, "channel", 0), msg.note)
                if key in active_notes and active_notes[key]:
                    start_time, velocity = active_notes[key].pop(0)
                    duration = max(0.0, current_time - start_time)
                    note_events.append(NoteEvent(
                        note=msg.note,
                        start_time=start_time,
                        duration=duration,
                        velocity=velocity,
                    ))
            elif msg.type == "control_change" and msg.control == 64:
                sustain_events.append(SustainEvent(
                    time=current_time,
                    on=msg.value >= 64,
                ))

        return note_events, sustain_events

    @staticmethod
    def _save_midi_file(
        path: str,
        note_events: list[NoteEvent],
        sustain_events: list[SustainEvent],
        tempo: int = 500000,
    ):
        """Save NoteEvent/SustainEvent lists to a MIDI file."""
        midi_file = mido.MidiFile()
        track = mido.MidiTrack()
        midi_file.tracks.append(track)

        track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

        events: list[tuple[float, int, mido.Message]] = []
        for note_event in note_events:
            start_time = max(0.0, note_event.start_time)
            end_time = max(start_time, note_event.start_time + max(0.0, note_event.duration))
            events.append((
                start_time,
                0,
                mido.Message(
                    "note_on",
                    note=note_event.note,
                    velocity=max(0, min(127, note_event.velocity)),
                    time=0,
                ),
            ))
            events.append((
                end_time,
                1,
                mido.Message("note_off", note=note_event.note, velocity=0, time=0),
            ))

        for sustain_event in sustain_events:
            events.append((
                max(0.0, sustain_event.time),
                2,
                mido.Message(
                    "control_change",
                    control=64,
                    value=127 if sustain_event.on else 0,
                    time=0,
                ),
            ))

        events.sort(key=lambda item: (item[0], item[1]))

        last_time = 0.0
        for event_time, _order, message in events:
            delta_seconds = max(0.0, event_time - last_time)
            delta_ticks = int(mido.second2tick(
                delta_seconds,
                midi_file.ticks_per_beat,
                tempo,
            ))
            message.time = delta_ticks
            track.append(message)
            last_time = event_time

        midi_file.save(path)

    def _on_playback_note_on(self, note: int, velocity: int):
        """Handle note triggered during playback."""
        self._synth.note_on(note, velocity)
        self._window.keyboard_note_on(note, velocity)

    def _on_playback_note_off(self, note: int):
        """Handle note released during playback."""
        self._synth.note_off(note)
        self._window.keyboard_note_off(note)

    def _on_playback_sustain(self, on: bool):
        """Handle sustain pedal during playback."""
        if on:
            self._synth.sustain_on()
        else:
            self._synth.sustain_off()
        self._window.set_sustain_status(on)

    def _on_playback_finished(self):
        """Handle playback finished."""
        self._window.stop_playback()

    def _on_metronome_toggled(self, on: bool):
        """Handle metronome on/off."""
        self._metronome_enabled = on
        if on:
            self._metronome.start()
        elif not self._count_in_active:
            self._metronome.stop()

    def _on_metronome_bpm_changed(self, bpm: int):
        """Handle BPM change."""
        self._metronome.bpm = bpm

    def start(self):
        """Start the application."""
        self._engine.start()
        self._window.show()

    def stop(self):
        """Stop the application."""
        self._midi_thread.stop()
        self._engine.stop()
        seen = set()
        for synth in self._cleanup_synths + [self._synth]:
            if hasattr(synth, "cleanup") and id(synth) not in seen:
                synth.cleanup()
                seen.add(id(synth))


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("PianoPlayer")
    app.setApplicationName("Piano Player")
    player = PianoPlayer()
    player.start()

    result = app.exec()

    player.stop()
    return result


if __name__ == "__main__":
    sys.exit(main())
