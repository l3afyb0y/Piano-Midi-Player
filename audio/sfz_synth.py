"""SFZ synthesizer backend using libsfizz via ctypes."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import queue
import threading
from pathlib import Path

import numpy as np


class _SfizzBindings:
    def __init__(self):
        self._lib = self._load_library()
        self._configure_signatures()

    @staticmethod
    def _load_library():
        candidates: list[str] = []
        found = ctypes.util.find_library("sfizz")
        if found:
            candidates.append(found)
        candidates.extend(["sfizz", "libsfizz.so"])
        candidates.extend(
            [
                "/usr/lib/libsfizz.so",
                "/usr/local/lib/libsfizz.so",
            ]
        )

        # Preserve order but avoid duplicate lookups.
        unique_candidates: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            unique_candidates.append(candidate)

        last_error: Exception | None = None
        for candidate in unique_candidates:
            try:
                return ctypes.CDLL(candidate)
            except OSError as exc:
                last_error = exc
        if last_error is not None:
            raise OSError(f"Unable to load libsfizz: {last_error}") from last_error
        raise OSError("Unable to locate libsfizz")

    def _configure_signatures(self):
        lib = self._lib
        lib.sfizz_create_synth.argtypes = []
        lib.sfizz_create_synth.restype = ctypes.c_void_p

        lib.sfizz_free.argtypes = [ctypes.c_void_p]
        lib.sfizz_free.restype = None

        lib.sfizz_load_file.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.sfizz_load_file.restype = ctypes.c_bool

        lib.sfizz_set_samples_per_block.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.sfizz_set_samples_per_block.restype = None

        lib.sfizz_set_sample_rate.argtypes = [ctypes.c_void_p, ctypes.c_float]
        lib.sfizz_set_sample_rate.restype = None

        lib.sfizz_send_note_on.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        lib.sfizz_send_note_on.restype = None

        lib.sfizz_send_note_off.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        lib.sfizz_send_note_off.restype = None

        lib.sfizz_send_cc.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        lib.sfizz_send_cc.restype = None

        lib.sfizz_render_block.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
            ctypes.c_int,
            ctypes.c_int,
        ]
        lib.sfizz_render_block.restype = None

        if hasattr(lib, "sfizz_all_sound_off"):
            lib.sfizz_all_sound_off.argtypes = [ctypes.c_void_p]
            lib.sfizz_all_sound_off.restype = None


_SFIZZ_BINDINGS: _SfizzBindings | None = None


def _load_sfizz_bindings() -> _SfizzBindings:
    global _SFIZZ_BINDINGS
    if _SFIZZ_BINDINGS is None:
        _SFIZZ_BINDINGS = _SfizzBindings()
    return _SFIZZ_BINDINGS


class SfizzSynth:
    """libsfizz-backed SFZ synthesizer."""

    def __init__(self, sample_rate: int = 44100, block_size: int = 384):
        bindings = _load_sfizz_bindings()
        self._bindings = bindings
        self._lib = bindings._lib
        self.sample_rate = int(sample_rate)
        self._instrument = "Piano"
        self._output_gain = 1.0
        self._notes: set[int] = set()
        self._notes_lock = threading.Lock()
        self._event_queue: queue.SimpleQueue = queue.SimpleQueue()

        self._synth = self._lib.sfizz_create_synth()
        if not self._synth:
            raise RuntimeError("Failed to initialize libsfizz synthesizer")

        self._block_size = max(64, int(block_size))
        self._left = np.zeros(self._block_size, dtype=np.float32)
        self._right = np.zeros(self._block_size, dtype=np.float32)
        self._channel_array = (ctypes.POINTER(ctypes.c_float) * 2)()
        self._sync_buffers()

        self._lib.sfizz_set_sample_rate(self._synth, float(self.sample_rate))
        self._lib.sfizz_set_samples_per_block(self._synth, int(self._block_size))

    def _sync_buffers(self):
        self._channel_array[0] = self._left.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        self._channel_array[1] = self._right.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

    def _ensure_capacity(self, num_samples: int):
        if num_samples <= self._block_size:
            return
        self._block_size = int(num_samples)
        self._left = np.zeros(self._block_size, dtype=np.float32)
        self._right = np.zeros(self._block_size, dtype=np.float32)
        self._sync_buffers()
        self._lib.sfizz_set_samples_per_block(self._synth, int(self._block_size))

    def load_sfz(self, path: str) -> bool:
        target = Path(path).expanduser().resolve()
        if target.suffix.lower() != ".sfz" or not target.is_file():
            return False
        loaded = bool(self._lib.sfizz_load_file(self._synth, os.fsencode(str(target))))
        if loaded:
            # Reset sustain to avoid carried pedal state from previous patch.
            self._lib.sfizz_send_cc(self._synth, 0, 64, 0)
        return loaded

    def set_instrument(self, instrument: str):
        # SFZ does not expose standardized preset numbers the way GM SoundFonts do.
        self._instrument = instrument if instrument in ("Piano", "Guitar") else "Piano"

    def note_on(self, note: int, velocity: int):
        note_number = max(0, min(127, int(note)))
        midi_velocity = max(1, min(127, int(velocity)))
        self._event_queue.put(("note_on", note_number, midi_velocity))

    def note_off(self, note: int):
        note_number = max(0, min(127, int(note)))
        self._event_queue.put(("note_off", note_number, 0))

    def sustain_on(self):
        self._event_queue.put(("sustain", 1, 0))

    def sustain_off(self):
        self._event_queue.put(("sustain", 0, 0))

    def _drain_event_queue(self):
        while True:
            try:
                event_type, a, b = self._event_queue.get_nowait()
            except queue.Empty:
                break
            if event_type == "note_on":
                self._lib.sfizz_send_note_on(self._synth, 0, int(a), int(b))
                with self._notes_lock:
                    self._notes.add(int(a))
                continue
            if event_type == "note_off":
                self._lib.sfizz_send_note_off(self._synth, 0, int(a), 64)
                with self._notes_lock:
                    self._notes.discard(int(a))
                continue
            if event_type == "sustain":
                self._lib.sfizz_send_cc(self._synth, 0, 64, 127 if int(a) else 0)

    def generate(self, num_samples: int) -> np.ndarray:
        frames = max(1, int(num_samples))
        self._drain_event_queue()
        self._ensure_capacity(frames)
        self._left[:frames] = 0.0
        self._right[:frames] = 0.0
        self._lib.sfizz_render_block(self._synth, self._channel_array, 2, frames)
        mono = ((self._left[:frames] + self._right[:frames]) * 0.5).astype(np.float32, copy=True)

        # Gentle automatic gain control to keep aggressive patches from clipping.
        peak = float(np.max(np.abs(mono)))
        if peak > 1e-9:
            target_gain = min(1.0, 0.94 / peak)
            if target_gain < self._output_gain:
                self._output_gain += (target_gain - self._output_gain) * 0.30
            else:
                self._output_gain += (target_gain - self._output_gain) * 0.06
            mono *= self._output_gain

        return mono

    def active_notes_count(self) -> int:
        self._drain_event_queue()
        with self._notes_lock:
            return len(self._notes)

    def cleanup(self):
        synth = self._synth
        if not synth:
            return
        if hasattr(self._lib, "sfizz_all_sound_off"):
            self._lib.sfizz_all_sound_off(synth)
        self._lib.sfizz_free(synth)
        self._synth = None
