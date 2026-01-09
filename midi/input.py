"""MIDI input handling and parsing."""

from dataclasses import dataclass
from typing import Optional, Any, List, Callable
import threading
import time


@dataclass
class MidiMessage:
    """Parsed MIDI message."""
    type: str  # note_on, note_off, sustain, unknown
    note: Optional[int] = None
    velocity: Optional[int] = None
    value: Optional[Any] = None


def parse_midi_message(data: List[int]) -> MidiMessage:
    """Parse raw MIDI bytes into a MidiMessage."""
    if len(data) < 1:
        return MidiMessage(type="unknown")

    status = data[0] & 0xF0  # Ignore channel

    if status == 0x90 and len(data) >= 3:  # Note On
        note, velocity = data[1], data[2]
        if velocity == 0:
            return MidiMessage(type="note_off", note=note)
        return MidiMessage(type="note_on", note=note, velocity=velocity)

    elif status == 0x80 and len(data) >= 3:  # Note Off
        note = data[1]
        return MidiMessage(type="note_off", note=note)

    elif status == 0xB0 and len(data) >= 3:  # Control Change
        cc_num, cc_val = data[1], data[2]
        if cc_num == 64:  # Sustain pedal
            return MidiMessage(type="sustain", value=(cc_val >= 64))

    return MidiMessage(type="unknown")


class MidiInputThread(threading.Thread):
    """Thread that reads MIDI input and emits callbacks."""

    def __init__(self, port_name: Optional[str] = None):
        super().__init__(daemon=True)
        self._port_name = port_name
        self._running = False
        self._callbacks: List[Callable[[MidiMessage], None]] = []
        self._midi_in = None
        self._connected_port: Optional[str] = None

    def add_callback(self, callback: Callable[[MidiMessage], None]):
        """Register callback for MIDI messages."""
        self._callbacks.append(callback)

    @property
    def connected_port(self) -> Optional[str]:
        """Return name of connected MIDI port."""
        return self._connected_port

    def run(self):
        """Main thread loop - reads MIDI and dispatches callbacks."""
        import rtmidi

        self._midi_in = rtmidi.MidiIn()

        # Find and open port
        ports = self._midi_in.get_ports()
        port_index = None

        if self._port_name:
            for i, name in enumerate(ports):
                if self._port_name.lower() in name.lower():
                    port_index = i
                    break
        elif ports:
            # Auto-select first non-through port, prefer CASIO
            for i, name in enumerate(ports):
                if "casio" in name.lower():
                    port_index = i
                    break
            if port_index is None:
                for i, name in enumerate(ports):
                    if "through" not in name.lower():
                        port_index = i
                        break
            if port_index is None and ports:
                port_index = 0

        if port_index is None:
            print("No MIDI ports available")
            return

        self._midi_in.open_port(port_index)
        self._connected_port = ports[port_index]
        print(f"Opened MIDI port: {self._connected_port}")

        self._running = True
        while self._running:
            msg = self._midi_in.get_message()
            if msg:
                data, _ = msg
                parsed = parse_midi_message(data)
                for callback in self._callbacks:
                    callback(parsed)
            else:
                time.sleep(0.001)  # Small sleep to prevent busy waiting

    def stop(self):
        """Stop the MIDI input thread."""
        self._running = False
        if self._midi_in:
            self._midi_in.close_port()

    @staticmethod
    def list_ports() -> List[str]:
        """List available MIDI input ports."""
        import rtmidi
        midi_in = rtmidi.MidiIn()
        return midi_in.get_ports()
