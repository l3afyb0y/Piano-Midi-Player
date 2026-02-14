"""MIDI file import/export and event conversion helpers."""

from __future__ import annotations

import mido

from gui.falling_notes_widget import NoteEvent, SustainEvent


class MidiFileService:
    """Translate between raw MIDI and UI/editor event models."""

    @staticmethod
    def load(path: str) -> tuple[list[NoteEvent], list[SustainEvent]]:
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
                    note_events.append(
                        NoteEvent(
                            note=msg.note,
                            start_time=start_time,
                            duration=duration,
                            velocity=velocity,
                        )
                    )
            elif msg.type == "control_change" and msg.control == 64:
                sustain_events.append(
                    SustainEvent(
                        time=current_time,
                        on=msg.value >= 64,
                    )
                )

        return note_events, sustain_events

    @staticmethod
    def save(
        path: str,
        note_events: list[NoteEvent],
        sustain_events: list[SustainEvent],
        tempo: int = 500000,
    ):
        midi_file = mido.MidiFile()
        track = mido.MidiTrack()
        midi_file.tracks.append(track)

        track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

        events: list[tuple[float, int, mido.Message]] = []
        for note_event in note_events:
            start_time = max(0.0, note_event.start_time)
            end_time = max(start_time, note_event.start_time + max(0.0, note_event.duration))
            events.append(
                (
                    start_time,
                    0,
                    mido.Message(
                        "note_on",
                        note=note_event.note,
                        velocity=max(0, min(127, note_event.velocity)),
                        time=0,
                    ),
                )
            )
            events.append(
                (
                    end_time,
                    1,
                    mido.Message("note_off", note=note_event.note, velocity=0, time=0),
                )
            )

        for sustain_event in sustain_events:
            events.append(
                (
                    max(0.0, sustain_event.time),
                    2,
                    mido.Message(
                        "control_change",
                        control=64,
                        value=127 if sustain_event.on else 0,
                        time=0,
                    ),
                )
            )

        events.sort(key=lambda item: (item[0], item[1]))

        last_time = 0.0
        for event_time, _order, message in events:
            delta_seconds = max(0.0, event_time - last_time)
            delta_ticks = int(
                mido.second2tick(
                    delta_seconds,
                    midi_file.ticks_per_beat,
                    tempo,
                )
            )
            message.time = delta_ticks
            track.append(message)
            last_time = event_time

        midi_file.save(path)

    @staticmethod
    def recorder_events_to_notes(events: list[dict], offset: float = 0.0) -> list[NoteEvent]:
        active_notes: dict[int, tuple[float, int]] = {}  # note -> (start_time, velocity)
        note_events: list[NoteEvent] = []

        for event in events:
            if event["type"] == "note_on":
                active_notes[event["note"]] = (event["time"], event["velocity"])
            elif event["type"] == "note_off" and event["note"] in active_notes:
                start_time, velocity = active_notes.pop(event["note"])
                duration = max(0.0, event["time"] - start_time)
                note_events.append(
                    NoteEvent(
                        note=event["note"],
                        start_time=offset + start_time,
                        duration=duration,
                        velocity=velocity,
                    )
                )

        return note_events

    @staticmethod
    def recorder_events_to_sustain(events: list[dict], offset: float = 0.0) -> list[SustainEvent]:
        sustain_events: list[SustainEvent] = []
        for event in events:
            if event["type"] == "sustain":
                sustain_events.append(
                    SustainEvent(
                        time=offset + event["time"],
                        on=event["value"],
                    )
                )
        return sustain_events
