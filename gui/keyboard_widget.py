"""Piano keyboard visualization widget."""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QLinearGradient


class KeyboardWidget(QWidget):
    """Visual piano keyboard showing pressed keys."""
    note_pressed = pyqtSignal(int, int)   # note, velocity
    note_released = pyqtSignal(int)       # note

    # MIDI note range (standard 88-key piano: A0=21 to C8=108)
    MIN_NOTE = 21
    MAX_NOTE = 108

    # Which notes in an octave are black keys (0=C, 1=C#, etc.)
    BLACK_KEYS = {1, 3, 6, 8, 10}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pressed_keys: set[int] = set()
        self._note_refcounts: dict[int, int] = {}
        self._velocities: dict[int, int] = {}  # note -> velocity for color intensity
        self._mouse_active_note: int | None = None
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)

    def note_on(self, note: int, velocity: int):
        """Mark a key as pressed."""
        if self.MIN_NOTE <= note <= self.MAX_NOTE:
            self._note_refcounts[note] = self._note_refcounts.get(note, 0) + 1
            self._pressed_keys.add(note)
            self._velocities[note] = int(max(1, min(127, velocity)))
            self.update()

    def note_off(self, note: int):
        """Mark a key as released."""
        current = self._note_refcounts.get(note, 0)
        if current <= 1:
            self._note_refcounts.pop(note, None)
            self._pressed_keys.discard(note)
            self._velocities.pop(note, None)
        else:
            self._note_refcounts[note] = current - 1
        self.update()

    def clear(self):
        """Clear all pressed keys."""
        self._pressed_keys.clear()
        self._note_refcounts.clear()
        self._velocities.clear()
        self._mouse_active_note = None
        self.update()

    def _is_black_key(self, note: int) -> bool:
        """Check if a MIDI note is a black key."""
        return (note % 12) in self.BLACK_KEYS

    def _get_white_key_index(self, note: int) -> int:
        """Get the index of this note among white keys only."""
        count = 0
        for n in range(self.MIN_NOTE, note):
            if not self._is_black_key(n):
                count += 1
        return count

    def _count_white_keys(self) -> int:
        """Count total white keys in range."""
        return sum(1 for n in range(self.MIN_NOTE, self.MAX_NOTE + 1)
                   if not self._is_black_key(n))

    def _velocity_from_y(self, y: float) -> int:
        if self.height() <= 0:
            return 100
        normalized = 1.0 - max(0.0, min(1.0, y / float(self.height())))
        return int(40 + normalized * 87)  # 40..127

    def _note_at_position(self, x: float, y: float) -> int | None:
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return None

        num_white = self._count_white_keys()
        if num_white <= 0:
            return None
        white_width = width / float(num_white)
        black_width = white_width * 0.6
        black_height = height * 0.6

        # Black keys visually overlay white keys, so resolve them first.
        if y <= black_height:
            for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
                if not self._is_black_key(note):
                    continue
                white_idx = self._get_white_key_index(note)
                key_x = (white_idx * white_width) - (black_width / 2.0)
                if key_x <= x <= key_x + black_width:
                    return note

        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if self._is_black_key(note):
                continue
            white_idx = self._get_white_key_index(note)
            key_x = white_idx * white_width
            if key_x <= x <= key_x + white_width:
                return note
        return None

    def _release_mouse_note(self):
        if self._mouse_active_note is None:
            return
        note = self._mouse_active_note
        self._mouse_active_note = None
        self.note_off(note)
        self.note_released.emit(note)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        note = self._note_at_position(event.position().x(), event.position().y())
        if note is None:
            self._release_mouse_note()
            event.accept()
            return

        self._release_mouse_note()
        velocity = self._velocity_from_y(event.position().y())
        self._mouse_active_note = note
        self.note_on(note, velocity)
        self.note_pressed.emit(note, velocity)
        event.accept()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return

        note = self._note_at_position(event.position().x(), event.position().y())
        if note == self._mouse_active_note:
            event.accept()
            return

        self._release_mouse_note()
        if note is not None:
            velocity = self._velocity_from_y(event.position().y())
            self._mouse_active_note = note
            self.note_on(note, velocity)
            self.note_pressed.emit(note, velocity)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._release_mouse_note()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def hideEvent(self, event):
        self._release_mouse_note()
        super().hideEvent(event)

    def paintEvent(self, event):
        """Draw the keyboard."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        num_white = self._count_white_keys()
        if num_white <= 0:
            painter.end()
            return

        white_width = width / num_white
        black_width = white_width * 0.6
        black_height = height * 0.6
        key_press_offset = 2

        # Draw white keys first
        white_idx = 0
        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if not self._is_black_key(note):
                x = white_idx * white_width
                is_pressed = note in self._pressed_keys
                y = 1 + (key_press_offset if is_pressed else 0)
                h = max(8, height - 2 - (key_press_offset if is_pressed else 0))
                rect_w = max(2, int(white_width - 1))
                rect_h = int(h)
                rect_x = int(x)
                rect_y = int(y)

                grad = QLinearGradient(0, float(rect_y), 0, float(rect_y + rect_h))
                if is_pressed:
                    vel = self._velocities.get(note, 100)
                    lift = int(8 + (vel / 127) * 12)
                    grad.setColorAt(0.0, QColor(234 + lift, 236 + lift, 240 + lift))
                    grad.setColorAt(1.0, QColor(190 + lift, 196 + lift, 206 + lift))
                else:
                    grad.setColorAt(0.0, QColor(247, 247, 246))
                    grad.setColorAt(0.62, QColor(236, 236, 234))
                    grad.setColorAt(1.0, QColor(210, 212, 214))

                painter.setBrush(QBrush(grad))
                painter.setPen(QPen(QColor(50, 56, 64), 1))
                painter.drawRect(rect_x, rect_y, rect_w, rect_h)

                # Subtle top highlight / pressed inset cue.
                if is_pressed:
                    painter.setPen(QPen(QColor(122, 126, 134), 1))
                    painter.drawLine(rect_x + 1, rect_y + 1, rect_x + rect_w - 2, rect_y + 1)
                else:
                    painter.setPen(QPen(QColor(255, 255, 255, 105), 1))
                    painter.drawLine(rect_x + 1, rect_y + 1, rect_x + rect_w - 2, rect_y + 1)
                white_idx += 1

        # Draw black keys on top
        white_idx = 0
        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if not self._is_black_key(note):
                white_idx += 1
            else:
                # Black key sits between previous white key and next
                x = (white_idx * white_width) - (black_width / 2)
                is_pressed = note in self._pressed_keys
                y = key_press_offset if is_pressed else 0
                h = max(8, int(black_height - (key_press_offset if is_pressed else 0)))
                rect_x = int(x)
                rect_y = int(y)
                rect_w = max(2, int(black_width))

                grad = QLinearGradient(0, float(rect_y), 0, float(rect_y + h))
                if is_pressed:
                    vel = self._velocities.get(note, 100)
                    lift = int(8 + (vel / 127) * 12)
                    grad.setColorAt(0.0, QColor(62 + lift, 66 + lift, 72 + lift))
                    grad.setColorAt(0.35, QColor(34 + lift, 36 + lift, 41 + lift))
                    grad.setColorAt(1.0, QColor(14 + lift, 16 + lift, 20 + lift))
                else:
                    grad.setColorAt(0.0, QColor(66, 71, 79))
                    grad.setColorAt(0.35, QColor(34, 37, 43))
                    grad.setColorAt(1.0, QColor(11, 13, 16))

                painter.setBrush(QBrush(grad))
                painter.setPen(QPen(QColor(8, 10, 14), 1))
                painter.drawRoundedRect(rect_x, rect_y, rect_w, h, 2, 2)

                # Side highlights/shadows to reinforce 3D depth.
                painter.setPen(QPen(QColor(220, 224, 232, 26), 1))
                painter.drawLine(rect_x + 1, rect_y + 1, rect_x + 1, rect_y + h - 2)
                painter.setPen(QPen(QColor(0, 0, 0, 78), 1))
                painter.drawLine(rect_x + rect_w - 2, rect_y + 1, rect_x + rect_w - 2, rect_y + h - 2)

        painter.end()
