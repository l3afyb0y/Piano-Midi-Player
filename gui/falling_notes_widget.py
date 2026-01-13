"""Falling notes visualization for MIDI playback."""

from dataclasses import dataclass
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
        self._selected_index: int | None = None
        self._editing_enabled = True

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
        self._selected_index = None
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
        self._selected_index = None
        self._total_duration = 0.0
        self.update()
        self.events_changed.emit()

    def get_current_time(self) -> float:
        """Get current playback time."""
        return self._current_time

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
        return (height - 40) / self._visible_seconds

    def _now_y(self, height: int) -> float:
        return height - 20

    def _is_black_key(self, note: int) -> bool:
        return (note % 12) in self.BLACK_KEYS

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
        self._notes.pop(idx)
        self._selected_index = None
        self._reset_active_state(emit_audio=False)
        self._recalculate_total_duration()
        self.events_changed.emit()
        self.update()

    def mousePressEvent(self, event):
        if not self._editing_enabled or self._playing:
            return super().mousePressEvent(event)

        self.setFocus()
        pos = event.position()
        if event.button() == Qt.MouseButton.LeftButton:
            self._selected_index = self._hit_test_note_index(pos.x(), pos.y())
            self.update()
            return
        if event.button() == Qt.MouseButton.RightButton:
            idx = self._hit_test_note_index(pos.x(), pos.y())
            if idx is not None:
                self._delete_note_index(idx)
                return

        return super().mousePressEvent(event)

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
        note_event = NoteEvent(
            note=note,
            start_time=start_time,
            duration=self.DEFAULT_NOTE_DURATION,
            velocity=self.DEFAULT_VELOCITY,
        )
        self._notes.append(note_event)
        self._notes.sort(key=lambda e: e.start_time)
        self._selected_index = None
        for idx, event in enumerate(self._notes):
            if event is note_event:
                self._selected_index = idx
                break
        self._reset_active_state(emit_audio=False)
        self._recalculate_total_duration()
        self.events_changed.emit()
        self.update()
        return super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if not self._editing_enabled or self._playing:
            return super().keyPressEvent(event)

        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected_index is not None:
                self._delete_note_index(self._selected_index)
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

        # Draw "now" line at bottom
        painter.setPen(QPen(QColor(100, 100, 120), 2))
        now_y = self._now_y(height)
        painter.drawLine(0, now_y, width, now_y)

        # Draw notes
        pixels_per_second = self._pixels_per_second(height)

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
            if idx == self._selected_index:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(240, 220, 120), 2))
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

        painter.end()
