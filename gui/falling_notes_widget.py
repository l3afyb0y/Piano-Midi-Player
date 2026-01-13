"""Falling notes visualization for MIDI playback."""

from dataclasses import dataclass
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen


@dataclass
class NoteEvent:
    """A note with start time, duration, and velocity."""
    note: int
    start_time: float  # seconds
    duration: float    # seconds
    velocity: int


@dataclass
class SustainEvent:
    """A sustain pedal event."""
    time: float  # seconds
    on: bool     # True = pedal down, False = pedal up


class FallingNotesWidget(QWidget):
    """Visualizes MIDI notes as falling rectangles."""

    # Signal emitted when playback reaches a note
    note_triggered = pyqtSignal(int, int)  # note, velocity
    note_released = pyqtSignal(int)        # note
    sustain_triggered = pyqtSignal(bool)   # True = on, False = off
    playback_finished = pyqtSignal()
    time_changed = pyqtSignal(float)       # current time for slider sync
    events_changed = pyqtSignal()

    # Piano range
    MIN_NOTE = 21  # A0
    MAX_NOTE = 108  # C8
    BLACK_KEYS = {1, 3, 6, 8, 10}
    DEFAULT_NOTE_DURATION = 0.5
    DEFAULT_VELOCITY = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notes: list[NoteEvent] = []
        self._sustain_events: list[SustainEvent] = []
        self._current_time = 0.0
        self._playing = False
        self._visible_seconds = 4.0  # How many seconds visible in window
        self._total_duration = 0.0
        self._selected_ids: set[int] = set()
        self._primary_id: int | None = None
        self._editing_enabled = True
        self._drag_mode: str | None = None
        self._drag_start_pos: tuple[float, float] | None = None
        self._drag_anchor_id: int | None = None
        self._drag_originals: list[tuple[NoteEvent, float, float, int]] = []
        self._selection_rect: tuple[float, float, float, float] | None = None
        self._selection_additive = False

        self._snap_enabled = True
        self._grid_enabled = True
        self._snap_division = 4
        self._bpm = 120

        # Animation timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)

        # Track which notes are currently sounding (for keyboard)
        self._active_notes: set[int] = set()
        # Track which specific events are currently active (for visualization)
        self._active_events: set[int] = set()  # indices into self._notes
        # Track which sustain events have been triggered
        self._triggered_sustain_indices: set[int] = set()

        self.setMinimumHeight(200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def load_events(self, events: list[NoteEvent], sustain_events: list[SustainEvent] | None = None):
        """Load note and sustain events for visualization."""
        self._notes = sorted(events, key=lambda e: e.start_time)
        self._sustain_events = sorted(sustain_events or [], key=lambda e: e.time)
        self._recalculate_total_duration()
        self._current_time = 0.0
        self._active_notes.clear()
        self._active_events.clear()
        self._triggered_sustain_indices.clear()
        self._selected_ids.clear()
        self._primary_id = None
        self.update()
        self.events_changed.emit()

    def play(self):
        """Start playback."""
        if not self._notes:
            return
        self._playing = True
        self._current_time = max(0.0, min(self._current_time, self._total_duration))
        self._reset_active_state(emit_audio=True)
        self._rebuild_active_state(emit_audio=True)
        self._timer.start(16)  # ~60 FPS

    def stop(self):
        """Stop playback."""
        self._playing = False
        self._timer.stop()
        # Release all active notes and sustain
        for note in list(self._active_notes):
            self.note_released.emit(note)
        self.sustain_triggered.emit(False)  # Release sustain on stop
        self._active_notes.clear()
        self._active_events.clear()
        self._triggered_sustain_indices.clear()
        self.update()

    def is_playing(self) -> bool:
        return self._playing

    def seek(self, time_seconds: float):
        """Seek to a specific time in the recording."""
        self._reset_active_state(emit_audio=self._playing)
        self._current_time = max(0.0, min(time_seconds, self._total_duration))
        self._rebuild_active_state(emit_audio=self._playing)
        self.time_changed.emit(self._current_time)
        self.update()

    def get_duration(self) -> float:
        """Get total duration of the recording."""
        return self._total_duration

    def has_events(self) -> bool:
        return bool(self._notes)

    def get_events(self) -> list[NoteEvent]:
        return list(self._notes)

    def get_sustain_events(self) -> list[SustainEvent]:
        return list(self._sustain_events)

    def clear_events(self):
        """Clear all loaded events."""
        self._notes = []
        self._sustain_events = []
        self._current_time = 0.0
        self._active_notes.clear()
        self._active_events.clear()
        self._triggered_sustain_indices.clear()
        self._selected_ids.clear()
        self._primary_id = None
        self._total_duration = 0.0
        self.update()
        self.events_changed.emit()

    def get_current_time(self) -> float:
        """Get current playback time."""
        return self._current_time

    def set_bpm(self, bpm: int):
        self._bpm = max(20, min(300, bpm))
        self.update()

    def set_snap_enabled(self, enabled: bool):
        self._snap_enabled = enabled
        self.update()

    def set_grid_enabled(self, enabled: bool):
        self._grid_enabled = enabled
        self.update()

    def set_snap_division(self, division: int):
        self._snap_division = max(1, division)
        self.update()

    def set_editing_enabled(self, enabled: bool):
        self._editing_enabled = enabled

    def _reset_active_state(self, emit_audio: bool):
        """Clear active state and optionally emit note-off/sustain-off signals."""
        if emit_audio:
            for note in list(self._active_notes):
                self.note_released.emit(note)
            self.sustain_triggered.emit(False)
        self._active_notes.clear()
        self._active_events.clear()
        self._triggered_sustain_indices.clear()

    def _rebuild_active_state(self, emit_audio: bool):
        """Rebuild active notes/events based on current time."""
        sustain_on = False
        for idx, sustain_event in enumerate(self._sustain_events):
            if sustain_event.time <= self._current_time:
                self._triggered_sustain_indices.add(idx)
                sustain_on = sustain_event.on

        for idx, note_event in enumerate(self._notes):
            if note_event.start_time <= self._current_time < note_event.start_time + note_event.duration:
                self._active_events.add(idx)
                if emit_audio and note_event.note not in self._active_notes:
                    self._active_notes.add(note_event.note)
                    self.note_triggered.emit(note_event.note, note_event.velocity)

        if emit_audio and sustain_on:
            self.sustain_triggered.emit(True)

    def _recalculate_total_duration(self):
        if self._notes:
            self._total_duration = max(e.start_time + e.duration for e in self._notes)
            if self._current_time > self._total_duration:
                self._current_time = self._total_duration
        else:
            self._total_duration = 0.0
            self._current_time = 0.0

    def _tick(self):
        """Animation tick - advance time and trigger notes."""
        dt = 0.016  # ~60 FPS
        self._current_time += dt
        self.time_changed.emit(self._current_time)

        # Check which notes should start/stop
        for idx, event in enumerate(self._notes):
            note_end = event.start_time + event.duration

            # Event should start
            if (event.start_time <= self._current_time < event.start_time + dt
                    and idx not in self._active_events):
                self._active_events.add(idx)
                # Only trigger keyboard note if not already sounding
                if event.note not in self._active_notes:
                    self._active_notes.add(event.note)
                    self.note_triggered.emit(event.note, event.velocity)

            # Event should end
            if (note_end <= self._current_time < note_end + dt
                    and idx in self._active_events):
                self._active_events.discard(idx)
                # Only release keyboard note if no other active events use it
                note_still_active = any(
                    i in self._active_events and self._notes[i].note == event.note
                    for i in self._active_events
                )
                if not note_still_active:
                    self._active_notes.discard(event.note)
                    self.note_released.emit(event.note)

        # Check which sustain events should trigger
        for idx, sustain_event in enumerate(self._sustain_events):
            if (sustain_event.time <= self._current_time < sustain_event.time + dt
                    and idx not in self._triggered_sustain_indices):
                self._triggered_sustain_indices.add(idx)
                self.sustain_triggered.emit(sustain_event.on)

        self.update()

        # Check if playback finished
        if self._current_time > self._total_duration + 0.5:
            self.stop()
            self.playback_finished.emit()

    def _pixels_per_second(self, height: int) -> float:
        if self._visible_seconds <= 0:
            return 1.0
        return max(1.0, (height - 20) / self._visible_seconds)

    def _now_y(self, height: int) -> float:
        return max(0.0, height - 1)

    def _time_to_y(self, time_value: float, height: int) -> float:
        pixels_per_second = self._pixels_per_second(height)
        now_y = self._now_y(height)
        return now_y - (time_value - self._current_time) * pixels_per_second

    def _is_black_key(self, note: int) -> bool:
        return (note % 12) in self.BLACK_KEYS

    def _snap_time(self, time_value: float) -> float:
        if not self._snap_enabled:
            return time_value
        beat_duration = 60.0 / max(1, self._bpm)
        step = beat_duration / max(1, self._snap_division)
        if step <= 0:
            return time_value
        return round(time_value / step) * step

    def _is_selected(self, note_event: NoteEvent) -> bool:
        return id(note_event) in self._selected_ids

    def _note_at_x(self, x: float, width: int) -> int | None:
        """Return the MIDI note at the given x coordinate."""
        # Prefer black keys for correct overlap behavior.
        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if not self._is_black_key(note):
                continue
            note_x, note_width = self._get_note_x(note, width)
            if note_x <= x <= note_x + note_width:
                return note

        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if self._is_black_key(note):
                continue
            note_x, note_width = self._get_note_x(note, width)
            if note_x <= x <= note_x + note_width:
                return note

        return None

    def _time_at_y(self, y: float, height: int) -> float:
        pixels_per_second = self._pixels_per_second(height)
        now_y = self._now_y(height)
        return self._current_time + ((now_y - y) / pixels_per_second)

    def _get_note_x(self, note: int, width: float) -> tuple[float, float]:
        """Get x position and width for a note."""
        # Count white keys up to this note
        num_white_total = sum(1 for n in range(self.MIN_NOTE, self.MAX_NOTE + 1)
                              if not self._is_black_key(n))
        white_width = width / num_white_total

        if self._is_black_key(note):
            # Black key position based on adjacent white keys
            white_count = sum(1 for n in range(self.MIN_NOTE, note)
                              if not self._is_black_key(n))
            x = white_count * white_width - white_width * 0.3
            return x, white_width * 0.6
        else:
            white_count = sum(1 for n in range(self.MIN_NOTE, note)
                              if not self._is_black_key(n))
            return white_count * white_width, white_width

    def _note_rect(self, note_event: NoteEvent, width: int, height: int) -> tuple[float, float, float, float]:
        pixels_per_second = self._pixels_per_second(height)
        now_y = self._now_y(height)
        time_until_hit = note_event.start_time - self._current_time
        y_bottom = now_y - (time_until_hit * pixels_per_second)
        y_top = y_bottom - (note_event.duration * pixels_per_second)
        x, note_width = self._get_note_x(note_event.note, width)
        return x, y_top, note_width, y_bottom - y_top

    def _hit_test_note_index(self, x: float, y: float) -> int | None:
        width = self.width()
        height = self.height()
        for idx in range(len(self._notes) - 1, -1, -1):
            note_event = self._notes[idx]
            rect_x, rect_y, rect_w, rect_h = self._note_rect(note_event, width, height)
            if rect_x <= x <= rect_x + rect_w and rect_y <= y <= rect_y + rect_h:
                return idx
        return None

    def _delete_note_index(self, idx: int):
        if idx < 0 or idx >= len(self._notes):
            return
        removed = self._notes.pop(idx)
        self._selected_ids.discard(id(removed))
        if self._primary_id == id(removed):
            self._primary_id = None
        self._reset_active_state(emit_audio=False)
        self._recalculate_total_duration()
        self.events_changed.emit()
        self.update()

    def _delete_selected(self):
        if not self._selected_ids:
            return
        self._notes = [note for note in self._notes if id(note) not in self._selected_ids]
        self._selected_ids.clear()
        self._primary_id = None
        self._reset_active_state(emit_audio=False)
        self._recalculate_total_duration()
        self.events_changed.emit()
        self.update()

    def _start_drag(self, mode: str, x: float, y: float, anchor_id: int | None = None):
        self._drag_mode = mode
        self._drag_start_pos = (x, y)
        self._drag_anchor_id = anchor_id
        self._drag_originals = [
            (note, note.start_time, note.duration, note.note)
            for note in self._notes
            if id(note) in self._selected_ids
        ]

    def _apply_drag_move(self, x: float, y: float):
        if not self._drag_start_pos or not self._drag_originals:
            return
        width = self.width()
        height = self.height()
        pixels_per_second = self._pixels_per_second(height)
        if pixels_per_second <= 0:
            return

        start_x, start_y = self._drag_start_pos
        delta_time = -(y - start_y) / pixels_per_second

        start_note = self._note_at_x(start_x, width)
        current_note = self._note_at_x(x, width)
        delta_pitch = 0
        if start_note is not None and current_note is not None:
            delta_pitch = current_note - start_note

        anchor_start = None
        for note_event, start_time, _duration, _note in self._drag_originals:
            if id(note_event) == self._drag_anchor_id:
                anchor_start = start_time
                break
        if anchor_start is None and self._drag_originals:
            anchor_start = self._drag_originals[0][1]

        if anchor_start is not None and self._snap_enabled:
            snapped_anchor = self._snap_time(anchor_start + delta_time)
            delta_time = snapped_anchor - anchor_start

        for note_event, start_time, _duration, note_value in self._drag_originals:
            new_start = max(0.0, start_time + delta_time)
            new_note = min(self.MAX_NOTE, max(self.MIN_NOTE, note_value + delta_pitch))
            note_event.start_time = new_start
            note_event.note = new_note

        self.update()

    def _apply_drag_resize(self, x: float, y: float):
        if not self._drag_start_pos or not self._drag_originals:
            return
        height = self.height()
        pixels_per_second = self._pixels_per_second(height)
        if pixels_per_second <= 0:
            return

        _start_x, start_y = self._drag_start_pos
        delta_time = -(y - start_y) / pixels_per_second

        anchor_end = None
        for note_event, start_time, duration, _note in self._drag_originals:
            if id(note_event) == self._drag_anchor_id:
                anchor_end = start_time + duration
                break
        if anchor_end is None and self._drag_originals:
            start_time, duration = self._drag_originals[0][1:3]
            anchor_end = start_time + duration

        if anchor_end is not None and self._snap_enabled:
            snapped_end = self._snap_time(anchor_end + delta_time)
            delta_time = snapped_end - anchor_end

        min_duration = 0.05
        for note_event, _start_time, duration, _note in self._drag_originals:
            note_event.duration = max(min_duration, duration + delta_time)

        self.update()

    def _finalize_drag(self):
        if self._drag_mode in ("move", "resize"):
            self._notes.sort(key=lambda e: e.start_time)
            self._reset_active_state(emit_audio=False)
            self._recalculate_total_duration()
            self.events_changed.emit()
        self._drag_mode = None
        self._drag_start_pos = None
        self._drag_anchor_id = None
        self._drag_originals = []
        self._selection_rect = None
        self.update()

    def mousePressEvent(self, event):
        if not self._editing_enabled or self._playing:
            return super().mousePressEvent(event)

        self.setFocus()
        pos = event.position()
        x = pos.x()
        y = pos.y()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._hit_test_note_index(x, y)
            if idx is not None:
                note_event = self._notes[idx]
                note_id = id(note_event)
                if shift:
                    if note_id not in self._selected_ids:
                        self._selected_ids.add(note_id)
                else:
                    if note_id not in self._selected_ids or len(self._selected_ids) > 1:
                        self._selected_ids = {note_id}
                self._primary_id = note_id

                rect_x, rect_y, rect_w, rect_h = self._note_rect(note_event, self.width(), self.height())
                handle_size = 6
                if rect_x <= x <= rect_x + rect_w and rect_y <= y <= rect_y + min(handle_size, rect_h):
                    self._start_drag("resize", x, y, anchor_id=note_id)
                else:
                    self._start_drag("move", x, y, anchor_id=note_id)
                self.update()
                return

            if not shift:
                self._selected_ids.clear()
                self._primary_id = None
            self._selection_additive = shift
            self._selection_rect = (x, y, x, y)
            self._start_drag("select", x, y, anchor_id=None)
            self.update()
            return

        if event.button() == Qt.MouseButton.RightButton:
            idx = self._hit_test_note_index(x, y)
            if idx is not None:
                self._delete_note_index(idx)
                return

        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._editing_enabled or self._playing:
            return super().mouseMoveEvent(event)
        if not self._drag_mode:
            return super().mouseMoveEvent(event)

        pos = event.position()
        x = pos.x()
        y = pos.y()

        if self._drag_mode == "select":
            if self._selection_rect:
                x0, y0, _x1, _y1 = self._selection_rect
                self._selection_rect = (x0, y0, x, y)
                self.update()
            return
        if self._drag_mode == "move":
            self._apply_drag_move(x, y)
            return
        if self._drag_mode == "resize":
            self._apply_drag_resize(x, y)
            return

        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self._editing_enabled or self._playing:
            return super().mouseReleaseEvent(event)

        if self._drag_mode == "select" and self._selection_rect:
            x0, y0, x1, y1 = self._selection_rect
            left, right = sorted((x0, x1))
            top, bottom = sorted((y0, y1))
            selected = set() if not self._selection_additive else set(self._selected_ids)
            for note_event in self._notes:
                rect_x, rect_y, rect_w, rect_h = self._note_rect(note_event, self.width(), self.height())
                if rect_x <= right and rect_x + rect_w >= left and rect_y <= bottom and rect_y + rect_h >= top:
                    selected.add(id(note_event))
            self._selected_ids = selected
            if self._selected_ids:
                self._primary_id = next(iter(self._selected_ids))
            else:
                self._primary_id = None

        self._finalize_drag()
        return super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if not self._editing_enabled or self._playing:
            return super().mouseDoubleClickEvent(event)

        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseDoubleClickEvent(event)

        pos = event.position()
        note = self._note_at_x(pos.x(), self.width())
        if note is None:
            return super().mouseDoubleClickEvent(event)

        start_time = self._time_at_y(pos.y(), self.height())
        start_time = max(0.0, start_time)
        start_time = self._snap_time(start_time)
        default_duration = self.DEFAULT_NOTE_DURATION
        if self._snap_enabled:
            beat_duration = 60.0 / max(1, self._bpm)
            step = beat_duration / max(1, self._snap_division)
            if step > 0:
                default_duration = max(default_duration, step)
        note_event = NoteEvent(
            note=note,
            start_time=start_time,
            duration=default_duration,
            velocity=self.DEFAULT_VELOCITY,
        )
        self._notes.append(note_event)
        self._notes.sort(key=lambda e: e.start_time)
        self._selected_ids = {id(note_event)}
        self._primary_id = id(note_event)
        self._reset_active_state(emit_audio=False)
        self._recalculate_total_duration()
        self.events_changed.emit()
        self.update()
        return super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if not self._editing_enabled or self._playing:
            return super().keyPressEvent(event)

        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected_ids:
                self._delete_selected()
                return

        return super().keyPressEvent(event)

    def wheelEvent(self, event):
        if not self._notes:
            return super().wheelEvent(event)

        delta_y = event.pixelDelta().y()
        if delta_y == 0:
            delta_y = event.angleDelta().y()
            if delta_y == 0:
                return super().wheelEvent(event)
            step_seconds = self._visible_seconds / 10.0
            delta_seconds = (delta_y / 120.0) * step_seconds
        else:
            pixels_per_second = self._pixels_per_second(self.height())
            if pixels_per_second <= 0:
                return super().wheelEvent(event)
            delta_seconds = delta_y / pixels_per_second

        self.seek(self._current_time - delta_seconds)
        event.accept()

    def paintEvent(self, event):
        """Draw the falling notes."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Dark background
        painter.fillRect(0, 0, width, height, QColor(20, 20, 25))

        # Draw grid lines for white keys
        num_white = sum(1 for n in range(self.MIN_NOTE, self.MAX_NOTE + 1)
                        if not self._is_black_key(n))
        white_width = width / num_white
        painter.setPen(QPen(QColor(40, 40, 45), 1))
        white_idx = 0
        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if not self._is_black_key(note):
                x = white_idx * white_width
                painter.drawLine(int(x), 0, int(x), height)
                white_idx += 1

        pixels_per_second = self._pixels_per_second(height)
        now_y = self._now_y(height)

        if self._grid_enabled and pixels_per_second > 0:
            beat_duration = 60.0 / max(1, self._bpm)
            step_duration = beat_duration / max(1, self._snap_division)
            time_top = self._current_time + ((now_y - 0) / pixels_per_second)
            time_bottom = self._current_time + ((now_y - height) / pixels_per_second)
            time_start = min(time_top, time_bottom)
            time_end = max(time_top, time_bottom)

            if step_duration > 0:
                first_step = math.floor(time_start / step_duration) * step_duration
                t = first_step
                while t <= time_end:
                    y = self._time_to_y(t, height)
                    if 0 <= y <= height:
                        is_beat = beat_duration > 0 and abs((t / beat_duration) - round(t / beat_duration)) < 1e-6
                        color = QColor(50, 50, 60) if is_beat else QColor(35, 35, 45)
                        painter.setPen(QPen(color, 1))
                        painter.drawLine(0, int(y), width, int(y))
                    t += step_duration

        # Draw "now" line at bottom
        painter.setPen(QPen(QColor(100, 100, 120), 2))
        painter.drawLine(0, now_y, width, now_y)

        for idx, note_event in enumerate(self._notes):
            # Calculate y position (notes fall from top)
            time_until_hit = note_event.start_time - self._current_time
            y_bottom = now_y - (time_until_hit * pixels_per_second)
            y_top = y_bottom - (note_event.duration * pixels_per_second)

            # Skip if not visible
            if y_bottom < 0 or y_top > height:
                continue

            x, note_width = self._get_note_x(note_event.note, width)

            # Color based on velocity and whether THIS specific event is playing
            is_active = idx in self._active_events
            vel_factor = note_event.velocity / 127

            if is_active:
                # Bright color when playing
                color = QColor(
                    int(80 + vel_factor * 175),
                    int(150 + vel_factor * 105),
                    int(220)
                )
            else:
                # Dimmer when not yet played
                if self._is_black_key(note_event.note):
                    color = QColor(
                        int(60 + vel_factor * 80),
                        int(80 + vel_factor * 60),
                        int(140 + vel_factor * 60)
                    )
                else:
                    color = QColor(
                        int(70 + vel_factor * 100),
                        int(100 + vel_factor * 80),
                        int(180 + vel_factor * 75)
                    )

            # Draw the note rectangle
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(120), 1))
            painter.drawRoundedRect(
                int(x + 1), int(y_top),
                int(note_width - 2), int(y_bottom - y_top),
                3, 3
            )
            if self._is_selected(note_event):
                painter.setBrush(Qt.BrushStyle.NoBrush)
                highlight = QColor(240, 220, 120) if id(note_event) == self._primary_id else QColor(200, 190, 110)
                painter.setPen(QPen(highlight, 2))
                painter.drawRoundedRect(
                    int(x + 1), int(y_top),
                    int(note_width - 2), int(y_bottom - y_top),
                    3, 3
                )

        # Draw current time
        if self._total_duration > 0:
            time_text = f"{self._current_time:.1f}s / {self._total_duration:.1f}s"
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(10, 20, time_text)

        if self._selection_rect:
            x0, y0, x1, y1 = self._selection_rect
            left, right = sorted((x0, x1))
            top, bottom = sorted((y0, y1))
            painter.setBrush(QBrush(QColor(80, 140, 220, 50)))
            painter.setPen(QPen(QColor(80, 140, 220), 1))
            painter.drawRect(int(left), int(top), int(right - left), int(bottom - top))

        painter.end()
