"""Tests for `tts/engine.py`'s `TTSEngine` (Milestone 8).

Neither `piper-tts` nor a working `sounddevice` (PortAudio) is available
in this sandbox (no network to install the former; the latter is
installed but fails to import without the system PortAudio libraries) --
lightweight fakes are installed into `sys.modules` before importing
`tts.engine`, the same way `test_llm_engine.py` fakes `llama_cpp`. This
only tests `TTSEngine`'s own logic (path resolution, the download-CLI
fallback, WAV encode/decode, play/stop bookkeeping) against those fakes,
not real synthesis or real audio playback -- see `docs/DECISIONS.md` for
what still needs a real-hardware pass.
"""

from __future__ import annotations

import io
import sys
import types
import wave
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def fake_piper_and_sounddevice(monkeypatch):
    """Install minimal fake `piper` and `sounddevice` modules so
    `tts.engine` (which does `from piper import PiperVoice` and
    `import sounddevice as sd` at module level) can be imported without
    either real dependency.
    """
    fake_piper = types.ModuleType("piper")
    fake_piper.PiperVoice = MagicMock()
    monkeypatch.setitem(sys.modules, "piper", fake_piper)

    fake_sd = types.ModuleType("sounddevice")
    fake_sd.play = MagicMock()
    fake_sd.wait = MagicMock()
    fake_sd.stop = MagicMock()
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    # Drop any previously-imported copy so it re-imports against our fakes.
    monkeypatch.delitem(sys.modules, "tts.engine", raising=False)
    yield fake_piper, fake_sd


def _import_engine():
    import tts.engine as engine_module

    return engine_module


def _write_local_voice_files(tmp_path):
    model_path = tmp_path / "voice.onnx"
    config_path = tmp_path / "voice.onnx.json"
    model_path.write_bytes(b"")
    config_path.write_text("{}")
    return model_path, config_path


def test_local_path_bypasses_download(tmp_path) -> None:
    engine_module = _import_engine()
    model_path, config_path = _write_local_voice_files(tmp_path)

    with patch.object(engine_module, "subprocess") as subprocess_mock:
        engine_module.TTSEngine(
            local_model_path=str(model_path), local_config_path=str(config_path)
        )
        assert not subprocess_mock.run.called


def test_mismatched_local_args_raise() -> None:
    engine_module = _import_engine()

    with pytest.raises(RuntimeError, match="must both be set together"):
        engine_module.TTSEngine(local_model_path="/x/voice.onnx")


def test_download_cli_success_but_missing_files_raises_clear_runtime_error(tmp_path) -> None:
    engine_module = _import_engine()

    with patch.object(
        engine_module.subprocess, "run", return_value=MagicMock(returncode=0, stderr="")
    ):
        with pytest.raises(RuntimeError, match="output layout may not match"):
            engine_module.TTSEngine(voice="en_US-lessac-medium", data_dir=tmp_path)


def test_download_cli_nonzero_exit_raises_clear_error(tmp_path) -> None:
    engine_module = _import_engine()

    with patch.object(
        engine_module.subprocess, "run", return_value=MagicMock(returncode=1, stderr="boom")
    ):
        with pytest.raises(RuntimeError, match="Could not load Piper voice"):
            engine_module.TTSEngine(voice="nope", data_dir=tmp_path)


def test_download_cli_invoked_with_expected_args_then_loads(tmp_path) -> None:
    engine_module = _import_engine()

    def fake_run(cmd, capture_output, text):
        (tmp_path / "en_US-lessac-medium.onnx").write_bytes(b"")
        (tmp_path / "en_US-lessac-medium.onnx.json").write_text("{}")
        return MagicMock(returncode=0, stderr="")

    with patch.object(engine_module.subprocess, "run", side_effect=fake_run) as run_mock:
        engine_module.TTSEngine(voice="en_US-lessac-medium", data_dir=tmp_path)

    cmd = run_mock.call_args.args[0]
    assert cmd[1:4] == ["-m", "piper.download_voices", "en_US-lessac-medium"]
    assert "--data-dir" in cmd


def test_already_cached_voice_skips_download(tmp_path) -> None:
    engine_module = _import_engine()
    (tmp_path / "en_US-lessac-medium.onnx").write_bytes(b"")
    (tmp_path / "en_US-lessac-medium.onnx.json").write_text("{}")

    with patch.object(engine_module, "subprocess") as subprocess_mock:
        engine_module.TTSEngine(voice="en_US-lessac-medium", data_dir=tmp_path)
        assert not subprocess_mock.run.called


def _make_engine_with_fake_voice(engine_module, fake_piper, tmp_path):
    model_path, config_path = _write_local_voice_files(tmp_path)

    fake_voice = MagicMock()

    def fake_synthesize_wav(text, wav_file, **kwargs):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x01" * 50)

    fake_voice.synthesize_wav.side_effect = fake_synthesize_wav
    fake_piper.PiperVoice.load.return_value = fake_voice

    engine = engine_module.TTSEngine(
        local_model_path=str(model_path), local_config_path=str(config_path)
    )
    return engine, fake_voice


def test_speak_synthesizes_and_plays(fake_piper_and_sounddevice, tmp_path) -> None:
    engine_module = _import_engine()
    fake_piper, fake_sd = fake_piper_and_sounddevice
    engine, _fake_voice = _make_engine_with_fake_voice(engine_module, fake_piper, tmp_path)

    engine.speak("hello there")

    assert fake_sd.play.called
    args, kwargs = fake_sd.play.call_args
    assert kwargs["samplerate"] == 22050
    assert len(args[0]) == 50
    assert fake_sd.wait.called


def test_speak_empty_text_is_a_noop(fake_piper_and_sounddevice, tmp_path) -> None:
    engine_module = _import_engine()
    fake_piper, fake_sd = fake_piper_and_sounddevice
    engine, fake_voice = _make_engine_with_fake_voice(engine_module, fake_piper, tmp_path)

    engine.speak("   ")

    assert not fake_voice.synthesize_wav.called
    assert not fake_sd.play.called


def test_stop_noops_when_idle_and_stops_sounddevice_when_speaking(
    fake_piper_and_sounddevice, tmp_path
) -> None:
    engine_module = _import_engine()
    fake_piper, fake_sd = fake_piper_and_sounddevice
    engine, _fake_voice = _make_engine_with_fake_voice(engine_module, fake_piper, tmp_path)

    engine.stop()
    assert not fake_sd.stop.called

    engine._speaking = True
    engine.stop()
    assert fake_sd.stop.called


def test_speak_resets_speaking_flag_even_when_playback_raises(
    fake_piper_and_sounddevice, tmp_path
) -> None:
    engine_module = _import_engine()
    fake_piper, fake_sd = fake_piper_and_sounddevice
    engine, _fake_voice = _make_engine_with_fake_voice(engine_module, fake_piper, tmp_path)

    fake_sd.wait.side_effect = RuntimeError("device error")

    with pytest.raises(RuntimeError):
        engine.speak("hello there")

    assert engine._speaking is False


def test_synthesize_wav_bytes_returns_valid_wav(fake_piper_and_sounddevice, tmp_path) -> None:
    engine_module = _import_engine()
    fake_piper, _fake_sd = fake_piper_and_sounddevice
    engine, _fake_voice = _make_engine_with_fake_voice(engine_module, fake_piper, tmp_path)

    wav_bytes = engine.synthesize_wav_bytes("hello")

    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        assert wav_file.getframerate() == 22050
        assert wav_file.getnchannels() == 1
