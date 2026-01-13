"""MIDI input handling and parsing."""

from dataclasses import dataclass
from typing import Optional, Any, List, Callable


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


class MidiInputHandler:
    """Low-latency MIDI input using rtmidi's native callback."""

    def __init__(self, port_name: Optional[str] = None):
        self._port_name = port_name
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

    def _midi_callback(self, event, data=None):
        """Called directly by rtmidi when MIDI data arrives - lowest latency."""
        midi_data, delta_time = event
        parsed = parse_midi_message(midi_data)
        if parsed.type != "unknown":
            for callback in self._callbacks:
                callback(parsed)

    def start(self):
        """Start MIDI input with native callback."""
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

        # Use rtmidi's native callback - called directly from MIDI thread
        self._midi_in.set_callback(self._midi_callback)

    def stop(self):
        """Stop MIDI input."""
        if self._midi_in:
            self._midi_in.cancel_callback()
            self._midi_in.close_port()

    @staticmethod
    def list_ports() -> List[str]:
        """List available MIDI input ports."""
        import rtmidi
        midi_in = rtmidi.MidiIn()
        return midi_in.get_ports()


# Backwards compatibility alias
MidiInputThread = MidiInputHandler
