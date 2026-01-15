"""MIDI event recording."""

import time
import mido
from typing import List, Dict, Any, Optional


class MidiRecorder:
    """Records MIDI events with timing."""

    def __init__(self):
        self._events: List[Dict[str, Any]] = []
        self._start_time: Optional[float] = None
        self._recording = False
        self._active_notes: Dict[int, int] = {}  # note -> outstanding note_on count
        self._sustain_on = False

    def start(self):
        """Start recording."""
        self._events = []
        self._start_time = time.time()
        self._recording = True
        self._active_notes = {}
        self._sustain_on = False

    def stop(self):
        """Stop recording."""
        if not self._recording or self._start_time is None:
            self._recording = False
            return

        stop_time = time.time() - self._start_time

        # Close any still-held notes so they keep their recorded duration.
        for note, count in sorted(self._active_notes.items()):
            for _ in range(count):
                self._events.append({
                    'type': 'note_off',
                    'note': note,
                    'velocity': 0,
                    'time': stop_time,
                })
        self._active_notes = {}

        # End sustain pedal if it was left on.
        if self._sustain_on:
            self._events.append({
                'type': 'sustain',
                'value': False,
                'time': stop_time,
            })
            self._sustain_on = False

        self._recording = False
        self._start_time = None

    def note_on(self, note: int, velocity: int):
        """Record note on event."""
        if not self._recording or self._start_time is None:
            return
        self._events.append({
            'type': 'note_on',
            'note': note,
            'velocity': velocity,
            'time': time.time() - self._start_time,
        })
        self._active_notes[note] = self._active_notes.get(note, 0) + 1

    def note_off(self, note: int):
        """Record note off event."""
        if not self._recording or self._start_time is None:
            return
        self._events.append({
            'type': 'note_off',
            'note': note,
            'velocity': 0,
            'time': time.time() - self._start_time,
        })
        if note in self._active_notes:
            self._active_notes[note] -= 1
            if self._active_notes[note] <= 0:
                del self._active_notes[note]

    def sustain(self, on: bool):
        """Record sustain pedal event."""
        if not self._recording or self._start_time is None:
            return
        self._events.append({
            'type': 'sustain',
            'value': on,
            'time': time.time() - self._start_time,
        })
        self._sustain_on = on

    def get_events(self) -> List[Dict[str, Any]]:
        """Return recorded events."""
        return self._events.copy()

    def save(self, path: str):
        """Save recording to MIDI file."""
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)

        # Set tempo (120 BPM)
        track.append(mido.MetaMessage('set_tempo', tempo=500000))

        # Convert events to MIDI messages
        last_time = 0.0
        ticks_per_second = mid.ticks_per_beat * 2  # At 120 BPM

        for event in self._events:
            delta_seconds = event['time'] - last_time
            delta_ticks = int(delta_seconds * ticks_per_second)
            last_time = event['time']

            if event['type'] == 'note_on':
                track.append(mido.Message(
                    'note_on',
                    note=event['note'],
                    velocity=event['velocity'],
                    time=delta_ticks
                ))
            elif event['type'] == 'note_off':
                track.append(mido.Message(
                    'note_off',
                    note=event['note'],
                    velocity=0,
                    time=delta_ticks
                ))
            elif event['type'] == 'sustain':
                value = 127 if event['value'] else 0
                track.append(mido.Message(
                    'control_change',
                    control=64,
                    value=value,
                    time=delta_ticks
                ))

        mid.save(path)

    @property
    def is_recording(self) -> bool:
        """Return True if currently recording."""
        return self._recording

    @property
    def duration(self) -> float:
        """Return duration of recording."""
        if not self._events:
            return 0.0
        return self._events[-1]['time']
