"""Audio engine - generates and outputs audio buffers."""

import threading
import queue
import os
import time
import re
import subprocess
import shutil
import numpy as np
from typing import Optional, Protocol, Callable
import sounddevice as sd


class Synthesizer(Protocol):
    """Protocol for synthesizer implementations."""
    def generate(self, num_samples: int) -> np.ndarray: ...
    def note_on(self, note: int, velocity: int) -> None: ...
    def note_off(self, note: int) -> None: ...


class AudioEngine:
    """Manages audio generation and output."""

    MASTER_LIMITER_TARGET_PEAK = 0.95
    MASTER_LIMITER_ATTACK = 0.50
    MASTER_LIMITER_RELEASE = 0.04

    @staticmethod
    def _normalize_device_name(name: str) -> str:
        base = re.sub(r"\s+\[[^\]]*\]\s*$", "", str(name or "").strip())
        base = base.lower()
        base = re.sub(r"[^a-z0-9]+", " ", base).strip()
        return base

    @classmethod
    def _list_pipewire_sink_names(cls) -> list[str]:
        """Return active PipeWire sink names (best effort)."""
        if not shutil.which("wpctl"):
            return []
        try:
            proc = subprocess.run(
                ["wpctl", "status", "-n"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.0,
                check=False,
            )
        except Exception:
            return []
        if proc.returncode != 0 or not proc.stdout:
            return []

        names: list[str] = []
        in_sinks = False
        line_re = re.compile(r"^\s*[│├└─*\s]*([0-9]+)\.\s+(.+)$")
        for raw in proc.stdout.splitlines():
            line = raw.rstrip()
            if "Sinks:" in line:
                in_sinks = True
                continue
            if in_sinks and re.search(r"\bSink endpoints:\b", line):
                break
            if not in_sinks:
                continue
            match = line_re.match(line)
            if not match:
                continue
            display = match.group(2)
            display = re.sub(r"\s+\[[^\]]*\]\s*$", "", display).strip()
            if display:
                names.append(display)
        return names

    @classmethod
    def _matches_pipewire_sink(cls, device_name: str, sink_names: list[str]) -> bool:
        dev_norm = cls._normalize_device_name(device_name)
        if not dev_norm:
            return False
        for sink in sink_names:
            sink_norm = cls._normalize_device_name(sink)
            if not sink_norm:
                continue
            if dev_norm == sink_norm or sink_norm in dev_norm or dev_norm in sink_norm:
                return True
        return False

    @staticmethod
    def _parse_sample_rate(raw: str | None) -> int | None:
        value = (raw or "").strip()
        if not value:
            return None
        try:
            parsed = int(float(value))
        except ValueError:
            return None
        return max(22050, min(192000, parsed))

    @classmethod
    def _resolve_initial_sample_rate(cls, requested: int | None) -> int:
        env_rate = cls._parse_sample_rate(os.environ.get("PIANO_PLAYER_SAMPLE_RATE"))
        if env_rate:
            return env_rate

        if requested is not None:
            return max(22050, min(192000, int(requested)))

        try:
            output_idx = cls.default_output_device()
            if output_idx is not None:
                device = sd.query_devices(output_idx)
                native = device.get("default_samplerate")
                if native:
                    return max(22050, min(192000, int(round(float(native)))))
            # Fallback to library default output device info.
            device = sd.query_devices(kind="output")
            native = device.get("default_samplerate")
            if native:
                return max(22050, min(192000, int(round(float(native)))))
        except Exception:
            pass

        return 48000

    def __init__(self, sample_rate: int | None = None, buffer_size: int = 512):
        self.sample_rate = self._resolve_initial_sample_rate(sample_rate)
        env_buffer = os.environ.get("PIANO_PLAYER_BUFFER_SIZE", "").strip()
        if env_buffer:
            try:
                buffer_size = max(128, int(env_buffer))
            except ValueError:
                pass
        self.buffer_size = buffer_size  # 512 @ 44.1kHz ~= 11.6ms, better underrun headroom
        self._latency_hint = self._parse_latency_hint(os.environ.get("PIANO_PLAYER_AUDIO_LATENCY", ""))
        self._volume = 0.8
        self._synth: Optional[Synthesizer] = None
        self._stream: Optional[sd.OutputStream] = None
        self._running = False
        self._output_device: Optional[int] = None
        self._synth_lock = threading.Lock()  # Only for synth swapping, not generation
        self._audio_callback_fn: Optional[Callable[[np.ndarray], None]] = None
        self._mix_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._mix_current: Optional[np.ndarray] = None
        self._mix_index = 0
        self._xrun_count = 0
        self._callback_count = 0
        self._master_gain = 1.0
        self._last_peak = 0.0
        self._peak_hold = 0.0
        self._clip_samples = 0
        self._non_finite_blocks = 0
        self._over_budget_callbacks = 0
        self._avg_callback_ms = 0.0
        self._max_callback_ms = 0.0

    @property
    def volume(self) -> float:
        return self._volume

    @staticmethod
    def _parse_latency_hint(raw: str):
        value = (raw or "").strip().lower()
        if not value:
            return None
        if value in ("low", "high"):
            return value
        try:
            return max(0.0, float(value))
        except ValueError:
            return None

    @volume.setter
    def volume(self, value: float):
        self._volume = max(0.0, min(1.0, value))

    def set_synth(self, synth: Synthesizer):
        """Set the synthesizer to use."""
        with self._synth_lock:
            self._synth = synth

    @property
    def output_device(self) -> Optional[int]:
        return self._output_device

    @staticmethod
    def list_output_devices() -> list[tuple[int, str]]:
        """Return likely output devices as (sounddevice index, display name)."""
        devices = sd.query_devices()
        outputs: list[tuple[int, str, int]] = []
        for idx, dev in enumerate(devices):
            if dev.get("max_output_channels", 0) > 0:
                name = str(dev.get("name", f"Device {idx}"))
                hostapi = int(dev.get("hostapi", -1))
                outputs.append((idx, name, hostapi))

        if not outputs:
            return []

        default_idx = AudioEngine.default_output_device()
        default_hostapi = None
        if default_idx is not None and 0 <= default_idx < len(devices):
            try:
                default_hostapi = int(devices[default_idx].get("hostapi", -1))
            except Exception:
                default_hostapi = None

        # Prefer current host API to avoid listing unrelated backends.
        if default_hostapi is not None and default_hostapi >= 0:
            filtered = [item for item in outputs if item[2] == default_hostapi]
            if filtered:
                outputs = filtered

        # Best effort: align with active PipeWire sinks shown by wpctl.
        sink_names = AudioEngine._list_pipewire_sink_names()
        if sink_names:
            matched = [item for item in outputs if AudioEngine._matches_pipewire_sink(item[1], sink_names)]
            if matched:
                outputs = matched

        # Drop obvious non-user-facing outputs.
        blocked = ("monitor", "loopback", "null", "dummy", "discard")
        cleaned: list[tuple[int, str]] = []
        seen_names: set[str] = set()
        for idx, name, _hostapi in outputs:
            lowered = name.lower()
            if any(token in lowered for token in blocked):
                continue
            norm = AudioEngine._normalize_device_name(name)
            if norm in seen_names:
                continue
            seen_names.add(norm)
            cleaned.append((idx, name))

        return cleaned

    @staticmethod
    def default_output_device() -> Optional[int]:
        default_dev = sd.default.device
        if isinstance(default_dev, (list, tuple)) and len(default_dev) > 1:
            output_idx = default_dev[1]
            if isinstance(output_idx, int) and output_idx >= 0:
                return output_idx
        return None

    def set_output_device(self, device_index: Optional[int]) -> bool:
        """Set active output device. Restarts stream if already running."""
        if device_index is not None and device_index < 0:
            device_index = None
        if self._output_device == device_index:
            return True

        previous = self._output_device
        was_running = self._running
        if was_running:
            self.stop()

        self._output_device = device_index
        if not was_running:
            return True

        try:
            self.start()
            return True
        except Exception as exc:
            print(f"Failed to set audio output device: {exc}")
            self._output_device = previous
            if previous != device_index:
                try:
                    self.start()
                except Exception as restart_exc:
                    print(f"Failed to restart previous audio output: {restart_exc}")
            return False

    def set_audio_callback(self, callback: Optional[Callable[[np.ndarray], None]]):
        """Set callback to receive generated audio (for recording)."""
        self._audio_callback_fn = callback

    def get_runtime_stats(self) -> dict[str, float | int]:
        callbacks = int(self._callback_count)
        xruns = int(self._xrun_count)
        ratio = (float(xruns) / float(callbacks)) if callbacks > 0 else 0.0
        return {
            "callbacks": callbacks,
            "xruns": xruns,
            "xrun_ratio": ratio,
            "master_gain": float(self._master_gain),
            "peak": float(self._peak_hold),
            "clip_samples": int(self._clip_samples),
            "non_finite_blocks": int(self._non_finite_blocks),
            "over_budget_callbacks": int(self._over_budget_callbacks),
            "avg_callback_ms": float(self._avg_callback_ms),
            "max_callback_ms": float(self._max_callback_ms),
            "buffer_size": int(self.buffer_size),
            "sample_rate": int(round(self._stream.samplerate)) if self._stream is not None else int(self.sample_rate),
        }

    def reset_runtime_stats(self):
        self._xrun_count = 0
        self._callback_count = 0
        self._last_peak = 0.0
        self._peak_hold = 0.0
        self._clip_samples = 0
        self._non_finite_blocks = 0
        self._over_budget_callbacks = 0
        self._avg_callback_ms = 0.0
        self._max_callback_ms = 0.0

    def queue_audio(self, samples: np.ndarray):
        """Queue one-shot audio to mix into output (e.g., metronome click)."""
        if samples is None or len(samples) == 0:
            return
        self._mix_queue.put(np.asarray(samples, dtype=np.float32).copy())

    def _audio_callback(self, outdata, frames, _time_info, _status):
        """Sounddevice callback - runs in audio thread.

        IMPORTANT: Avoid blocking here - real-time thread cannot wait.
        Synth reference is stable; only swapped via set_synth().
        """
        t0 = time.perf_counter()
        self._callback_count += 1
        if _status:
            self._xrun_count += 1

        synth = self._synth  # Atomic read
        if synth:
            buffer = synth.generate(frames)
            if not isinstance(buffer, np.ndarray):
                buffer = np.asarray(buffer, dtype=np.float32)
            if buffer.dtype != np.float32:
                buffer = buffer.astype(np.float32, copy=False)
            if len(buffer) != frames:
                fixed = np.zeros(frames, dtype=np.float32)
                copy_len = min(frames, len(buffer))
                if copy_len > 0:
                    fixed[:copy_len] = buffer[:copy_len]
                buffer = fixed
            if not np.all(np.isfinite(buffer)):
                self._non_finite_blocks += 1
                buffer = np.nan_to_num(buffer, copy=False, nan=0.0, posinf=1.0, neginf=-1.0)
            np.multiply(buffer, self._volume, out=buffer, casting="unsafe")
        else:
            buffer = np.zeros(frames, dtype=np.float32)

        # Mix any queued one-shot audio (e.g., metronome click).
        if self._mix_current is None:
            try:
                self._mix_current = self._mix_queue.get_nowait()
                self._mix_index = 0
            except queue.Empty:
                self._mix_current = None

        if self._mix_current is not None:
            remaining = len(self._mix_current) - self._mix_index
            if remaining <= 0:
                self._mix_current = None
            else:
                count = min(frames, remaining)
                buffer[:count] += (
                    self._mix_current[self._mix_index:self._mix_index + count] * self._volume
                )
                self._mix_index += count
                if self._mix_index >= len(self._mix_current):
                    self._mix_current = None

        # Smooth master limiting to avoid hard clipping crackle at high loudness/polyphony.
        peak = float(np.max(np.abs(buffer)))
        self._last_peak = peak
        self._peak_hold = max(peak, self._peak_hold * 0.965)
        if peak > 1e-9:
            needed = min(1.0, self.MASTER_LIMITER_TARGET_PEAK / peak)
            if needed < self._master_gain:
                coeff = self.MASTER_LIMITER_ATTACK
            else:
                coeff = self.MASTER_LIMITER_RELEASE
            self._master_gain += (needed - self._master_gain) * coeff
            buffer *= self._master_gain
        else:
            self._master_gain = min(1.0, self._master_gain + self.MASTER_LIMITER_RELEASE)

        over = np.abs(buffer) > 1.0
        if np.any(over):
            self._clip_samples += int(np.count_nonzero(over))
        # Final guardrail clip.
        np.clip(buffer, -1.0, 1.0, out=buffer)
        outdata[:, 0] = buffer

        # Notify callback (for recording)
        if self._audio_callback_fn:
            self._audio_callback_fn(buffer)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self._max_callback_ms = max(self._max_callback_ms, elapsed_ms)
        if self._callback_count == 1:
            self._avg_callback_ms = elapsed_ms
        else:
            self._avg_callback_ms = (self._avg_callback_ms * 0.98) + (elapsed_ms * 0.02)
        budget_ms = (float(frames) / float(self.sample_rate)) * 1000.0
        if elapsed_ms > budget_ms:
            self._over_budget_callbacks += 1

    def start(self):
        """Start audio output."""
        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            blocksize=self.buffer_size,
            channels=1,
            dtype=np.float32,
            callback=self._audio_callback,
            device=self._output_device,
            latency=self._latency_hint,
        )
        self._stream.start()
        self._running = True

    def stop(self):
        """Stop audio output."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def generate_buffer(self) -> np.ndarray:
        """Generate next audio buffer. For testing without output."""
        synth = self._synth
        if synth:
            return synth.generate(self.buffer_size) * self._volume
        return np.zeros(self.buffer_size, dtype=np.float32)
