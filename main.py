#!/usr/bin/env python3
"""Piano Player - MIDI to audio application."""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal

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

        # Create components - try SoundFont first, fall back to simple synth
        self._synth = self._create_default_synth()
        self._engine = AudioEngine()
        self._engine.set_synth(self._synth)

        self._midi_thread = MidiInputThread()
        self._midi_recorder = MidiRecorder()
        self._wav_recorder = None
        self._wav_path = None

        # Metronome
        self._metronome = Metronome()
        self._metronome.set_click_callback(self._engine.queue_audio)

        # Create window
        self._window = MainWindow()

        # Connect signals
        self._connect_signals()

        # Sync UI with active synth
        self._window.set_synth_selection(self._synth_name)

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
        self._window.play_recording.connect(self._on_play_recording)

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
            self._midi_recorder.start()
            # Create temp WAV file
            fd, self._wav_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            self._wav_recorder = WavRecorder(self._wav_path)
            self._wav_recorder.start()
            self._engine.set_audio_callback(self._wav_recorder.write)
        else:
            self._midi_recorder.stop()
            if self._wav_recorder:
                self._wav_recorder.stop()
                self._engine.set_audio_callback(None)

    def _on_save_wav(self, path: str):
        if self._wav_path:
            shutil.copy(self._wav_path, path)
            print(f"Saved WAV to: {path}")

    def _on_save_midi(self, path: str):
        self._midi_recorder.save(path)
        print(f"Saved MIDI to: {path}")

    def _on_play_recording(self):
        """Convert recorded events to NoteEvents and start playback."""
        events = self._midi_recorder.get_events()
        note_events = self._convert_to_note_events(events)
        sustain_events = self._convert_to_sustain_events(events)
        self._window.load_recording(note_events, sustain_events)
        self._window.start_playback()

    def _convert_to_note_events(self, events: list) -> list[NoteEvent]:
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
                    duration = event['time'] - start_time
                    note_events.append(NoteEvent(
                        note=event['note'],
                        start_time=start_time,
                        duration=duration,
                        velocity=velocity
                    ))

        return note_events

    def _convert_to_sustain_events(self, events: list) -> list[SustainEvent]:
        """Convert MIDI recorder events to SustainEvent objects."""
        sustain_events = []
        for event in events:
            if event['type'] == 'sustain':
                sustain_events.append(SustainEvent(
                    time=event['time'],
                    on=event['value']
                ))
        return sustain_events

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
        if on:
            self._metronome.start()
        else:
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
    player = PianoPlayer()
    player.start()

    result = app.exec()

    player.stop()
    return result


if __name__ == "__main__":
    sys.exit(main())
