"""Local text-to-speech output via Piper (`piper-tts`).

Knows nothing about the LLM, Aura, or threading -- takes text in, plays
audio out (or hands back raw WAV bytes via `synthesize_wav_bytes()` for a
caller that wants to handle playback itself). `main.py` decides when to
call it and how to route Aura state around it, same division of
responsibility as `llm/engine.py` and `vision/model.py`.

Piper voices are a `<name>.onnx` + `<name>.onnx.json` pair. Two ways to
get them, mirroring `LLMSettings`/`VisionSettings`' local-path-overrides-
download pattern:

  1. `local_model_path` + `local_config_path` point directly at an
     already-downloaded voice. Always works, no network needed at
     runtime -- the safe option, and the only one exercised by this
     sandbox's tests (see docs/DECISIONS.md).
  2. Otherwise, `voice` (e.g. "en_US-lessac-medium") is resolved by
     shelling out to Piper's own documented voice-download CLI
     (`python -m piper.download_voices <voice> --data-dir <dir>`), then
     loading the two files it drops into `data_dir`. Deliberately goes
     through the documented CLI entry point rather than importing
     `piper.download`'s internal functions directly -- CLI surfaces are
     far less likely to have changed across `piper-tts` releases than
     internal function signatures, which this session had no way to
     confirm (no network in this sandbox -- see docs/DECISIONS.md).

**Not yet run against the real package.** `piper-tts` isn't installed in
this sandbox (no network to install it). Everything in this file is
written against Piper's documented public API as of this session's best
understanding, verified only by unit tests that install a fake `piper`
module into `sys.modules` (same technique `tests/test_llm_engine.py` uses
for `llama_cpp`). A real-hardware pass is needed to confirm both the
`PiperVoice.load()` / `synthesize_wav()` call shapes and the
`download_voices` CLI invocation actually work as written.
"""

from __future__ import annotations

import io
import logging
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from piper import PiperVoice

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "en_US-lessac-medium"
DEFAULT_LENGTH_SCALE = 1.0
DEFAULT_NOISE_SCALE = 0.667
DEFAULT_NOISE_W_SCALE = 0.8


class TTSEngine:
    """Wraps a Piper `PiperVoice` for one-shot text -> speech playback.

    Stateless across calls, same as `LLMEngine.generate()` -- each
    `speak()` call is an independent synthesis, no streaming/incremental
    text yet.
    """

    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        local_model_path: str | None = None,
        local_config_path: str | None = None,
        data_dir: str | Path | None = None,
        use_cuda: bool = False,
        length_scale: float = DEFAULT_LENGTH_SCALE,
        noise_scale: float = DEFAULT_NOISE_SCALE,
        noise_w_scale: float = DEFAULT_NOISE_W_SCALE,
    ) -> None:
        self._length_scale = length_scale
        self._noise_scale = noise_scale
        self._noise_w_scale = noise_w_scale
        # Guards playback so stop() has something to cancel and so two
        # overlapping speak() calls (shouldn't normally happen -- see
        # main.py's interrupt_on_new_query handling -- but worth being
        # defensive about) don't both try to drive the output device.
        self._speaking = False

        try:
            if local_model_path and local_config_path:
                logger.info("Loading local Piper voice from '%s'...", local_model_path)
                model_path = Path(local_model_path)
                config_path = Path(local_config_path)
            elif local_model_path or local_config_path:
                raise RuntimeError(
                    "tts.local_model_path and tts.local_config_path must both be "
                    "set together, or both left unset -- only one was provided."
                )
            else:
                model_path, config_path = self._ensure_voice_downloaded(
                    voice, Path(data_dir) if data_dir is not None else Path.cwd()
                )

            self._voice = PiperVoice.load(
                str(model_path), config_path=str(config_path), use_cuda=use_cuda
            )
        except Exception as exc:
            target = f"{local_model_path!r}/{local_config_path!r}" if local_model_path else voice
            raise RuntimeError(
                f"Could not load Piper voice ('{target}'). If this is the first time "
                "this voice has been used, it requires an internet connection to "
                f"download. Underlying error: {exc}"
            ) from exc

        logger.info("TTS engine ready (voice=%s).", voice)

    @staticmethod
    def _ensure_voice_downloaded(voice: str, data_dir: Path) -> tuple[Path, Path]:
        """Resolve `voice` to a local `(model_path, config_path)` pair,
        downloading it via Piper's `download_voices` CLI module first if
        the files aren't already present in `data_dir`.

        See the module docstring for why this shells out to the CLI
        rather than calling `piper.download`'s internals directly.
        """
        model_path = data_dir / f"{voice}.onnx"
        config_path = data_dir / f"{voice}.onnx.json"
        if model_path.exists() and config_path.exists():
            logger.debug("Piper voice '%s' already cached at '%s'.", voice, data_dir)
            return model_path, config_path

        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Downloading Piper voice '%s' into '%s' (first use only, cached after)...",
            voice,
            data_dir,
        )
        result = subprocess.run(
            [sys.executable, "-m", "piper.download_voices", voice, "--data-dir", str(data_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"'python -m piper.download_voices {voice}' failed "
                f"(exit {result.returncode}): {result.stderr.strip()}"
            )
        if not model_path.exists() or not config_path.exists():
            raise RuntimeError(
                f"'python -m piper.download_voices {voice}' reported success but "
                f"'{model_path.name}'/'{config_path.name}' aren't in '{data_dir}' -- "
                "the CLI's output layout may not match what this code expects "
                "(see this file's module docstring)."
            )
        return model_path, config_path

    def synthesize_wav_bytes(self, text: str) -> bytes:
        """Synthesize `text` to WAV-encoded bytes, no playback.

        Split out from `speak()` so synthesis can be unit-tested (and
        potentially reused, e.g. for a future "save response as audio"
        feature) without touching `sounddevice`/an output device.
        """
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            self._voice.synthesize_wav(
                text,
                wav_file,
                length_scale=self._length_scale,
                noise_scale=self._noise_scale,
                noise_w_scale=self._noise_w_scale,
            )
        return buffer.getvalue()

    def speak(self, text: str) -> None:
        """Synthesize `text` and play it on the default output device,
        blocking until playback finishes (or `stop()` cancels it).

        Empty/whitespace-only input is a silent no-op, same convention as
        `LLMEngine.generate()`.
        """
        if not text.strip():
            return

        wav_bytes = self.synthesize_wav_bytes(text)
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            n_channels = wav_file.getnchannels()
            frames = wav_file.readframes(wav_file.getnframes())

        samples = np.frombuffer(frames, dtype=np.int16)
        if n_channels > 1:
            samples = samples.reshape(-1, n_channels)

        logger.debug(
            "Playing %d samples at %dHz (%d chars of text).", len(samples), sample_rate, len(text)
        )
        self._speaking = True
        try:
            sd.play(samples, samplerate=sample_rate)
            sd.wait()  # blocks until playback finishes or sd.stop() is called
        finally:
            self._speaking = False

    def stop(self) -> None:
        """Cancel in-progress playback immediately, if any. Safe to call
        even when nothing is playing (Milestone 8's early-dismiss
        counterpart to `AuraController.clear_target_box()` -- see
        `main.py`'s `on_transcribed`).
        """
        if self._speaking:
            sd.stop()
