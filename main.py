#!/usr/bin/env python3
"""Piano Player - MIDI to audio application."""

import sys
import os
import tempfile
import shutil
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal

from gui.main_window import MainWindow
from audio.engine import AudioEngine
from audio.simple_synth import SimpleSynth
from midi.input import MidiInputThread, MidiMessage
from midi.recorder import MidiRecorder
from recording.wav_recorder import WavRecorder

# Default SoundFont path
DEFAULT_SOUNDFONT = "/usr/share/soundfonts/FluidR3_GM.sf2"


class PianoPlayer(QObject):
    """Main application controller."""

    # Signal to update UI from MIDI thread
    midi_received = pyqtSignal(object)

    def __init__(self):
        super().__init__()

        # Create components - try SoundFont first, fall back to simple synth
        self._synth = self._create_default_synth()
        self._engine = AudioEngine()
        self._engine.set_synth(self._synth)

        self._midi_thread = MidiInputThread()
        self._midi_recorder = MidiRecorder()
        self._wav_recorder = None
        self._wav_path = None

        # Create window
        self._window = MainWindow()

        # Connect signals
        self._connect_signals()

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
        if os.path.exists(DEFAULT_SOUNDFONT):
            try:
                from audio.soundfont_synth import SoundFontSynth
                sf_synth = SoundFontSynth()
                if sf_synth.load_soundfont(DEFAULT_SOUNDFONT):
                    print(f"Using SoundFont: {DEFAULT_SOUNDFONT}")
                    return sf_synth
            except Exception as e:
                print(f"Could not load SoundFont: {e}")

        print("Using simple synthesizer")
        return SimpleSynth()

    def _connect_signals(self):
        """Connect UI signals to handlers."""
        self._window.volume_changed.connect(self._on_volume_changed)
        self._window.synth_changed.connect(self._on_synth_changed)
        self._window.soundfont_loaded.connect(self._on_soundfont_loaded)
        self._window.record_toggled.connect(self._on_record_toggled)
        self._window.save_wav.connect(self._on_save_wav)
        self._window.save_midi.connect(self._on_save_midi)

        # Thread-safe MIDI handling
        self.midi_received.connect(self._handle_midi_in_main_thread)

    def _on_midi_message(self, msg: MidiMessage):
        """Called from MIDI thread - emit signal for main thread."""
        self.midi_received.emit(msg)

    def _handle_midi_in_main_thread(self, msg: MidiMessage):
        """Handle MIDI message in main thread."""
        if msg.type == "note_on":
            self._synth.note_on(msg.note, msg.velocity)
            if self._midi_recorder.is_recording:
                self._midi_recorder.note_on(msg.note, msg.velocity)
        elif msg.type == "note_off":
            self._synth.note_off(msg.note)
            if self._midi_recorder.is_recording:
                self._midi_recorder.note_off(msg.note)
        elif msg.type == "sustain":
            if msg.value:
                self._synth.sustain_on()
            else:
                self._synth.sustain_off()
            self._window.set_sustain_status(msg.value)
            if self._midi_recorder.is_recording:
                self._midi_recorder.sustain(msg.value)

        # Update note count
        self._window.set_notes_count(len(self._synth._notes))

    def _on_volume_changed(self, volume: float):
        self._engine.volume = volume

    def _on_synth_changed(self, name: str):
        if name == "Simple Synth":
            self._synth = SimpleSynth()
            self._engine.set_synth(self._synth)

    def _on_soundfont_loaded(self, path: str):
        try:
            from audio.soundfont_synth import SoundFontSynth
            sf_synth = SoundFontSynth()
            if sf_synth.load_soundfont(path):
                self._synth = sf_synth
                self._engine.set_synth(self._synth)
        except ImportError:
            print("SoundFont support not available (install pyfluidsynth)")

    def _on_record_toggled(self, recording: bool):
        if recording:
            self._midi_recorder.start()
            # Create temp WAV file
            self._wav_path = tempfile.mktemp(suffix=".wav")
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

    def start(self):
        """Start the application."""
        self._engine.start()
        self._window.show()

    def stop(self):
        """Stop the application."""
        self._midi_thread.stop()
        self._engine.stop()


def main():
    app = QApplication(sys.argv)
    player = PianoPlayer()
    player.start()

    result = app.exec()

    player.stop()
    return result


if __name__ == "__main__":
    sys.exit(main())
