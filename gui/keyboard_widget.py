"""Piano keyboard visualization widget."""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen


class KeyboardWidget(QWidget):
    """Visual piano keyboard showing pressed keys."""

    # MIDI note range (standard 88-key piano: A0=21 to C8=108)
    MIN_NOTE = 21
    MAX_NOTE = 108

    # Which notes in an octave are black keys (0=C, 1=C#, etc.)
    BLACK_KEYS = {1, 3, 6, 8, 10}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pressed_keys: set[int] = set()
        self._velocities: dict[int, int] = {}  # note -> velocity for color intensity
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)

    def note_on(self, note: int, velocity: int):
        """Mark a key as pressed."""
        if self.MIN_NOTE <= note <= self.MAX_NOTE:
            self._pressed_keys.add(note)
            self._velocities[note] = velocity
            self.update()

    def note_off(self, note: int):
        """Mark a key as released."""
        self._pressed_keys.discard(note)
        self._velocities.pop(note, None)
        self.update()

    def clear(self):
        """Clear all pressed keys."""
        self._pressed_keys.clear()
        self._velocities.clear()
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

    def paintEvent(self, event):
        """Draw the keyboard."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        num_white = self._count_white_keys()
        white_width = width / num_white
        black_width = white_width * 0.6
        black_height = height * 0.6

        # Draw white keys first
        white_idx = 0
        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if not self._is_black_key(note):
                x = white_idx * white_width

                # Color based on pressed state
                if note in self._pressed_keys:
                    vel = self._velocities.get(note, 100)
                    intensity = int(100 + (vel / 127) * 155)
                    painter.setBrush(QBrush(QColor(intensity, 80, 80)))
                else:
                    painter.setBrush(QBrush(QColor(250, 250, 250)))

                painter.setPen(QPen(QColor(40, 40, 40), 1))
                painter.drawRect(int(x), 0, int(white_width - 1), height - 1)
                white_idx += 1

        # Draw black keys on top
        white_idx = 0
        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if not self._is_black_key(note):
                white_idx += 1
            else:
                # Black key sits between previous white key and next
                x = (white_idx * white_width) - (black_width / 2)

                if note in self._pressed_keys:
                    vel = self._velocities.get(note, 100)
                    intensity = int(80 + (vel / 127) * 100)
                    painter.setBrush(QBrush(QColor(intensity, 50, 50)))
                else:
                    painter.setBrush(QBrush(QColor(30, 30, 30)))

                painter.setPen(QPen(QColor(20, 20, 20), 1))
                painter.drawRect(int(x), 0, int(black_width), int(black_height))

        painter.end()
