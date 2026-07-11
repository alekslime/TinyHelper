"""Tests for `llm/engine.py`'s retry-with-backoff around
`Llama.from_pretrained()`, added 2026-07-11 after a real-hardware run hit
a transient SSL handshake timeout talking to Hugging Face Hub (see
docs/DECISIONS.md).

`llama-cpp-python` isn't installed in this sandbox (heavy C++ build, no
prebuilt wheel available here) -- a lightweight fake is installed into
`sys.modules` before importing `llm.engine`, the same way real CI would
need to handle it without a GPU/compiler. This only tests the retry loop
itself, not real model loading/inference.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def fake_llama_cpp(monkeypatch):
    """Install a minimal fake `llama_cpp` module so `llm.engine` (which
    does `from llama_cpp import Llama` at module level) can be imported
    without the real, heavy dependency.
    """
    fake_module = types.ModuleType("llama_cpp")
    fake_module.Llama = MagicMock()
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)
    # Drop any previously-imported copy so it re-imports against our fake.
    monkeypatch.delitem(sys.modules, "llm.engine", raising=False)
    yield


def _import_engine():
    import llm.engine as engine_module

    return engine_module


def test_retries_transient_failure_then_succeeds(monkeypatch) -> None:
    engine_module = _import_engine()

    call_count = {"n": 0}

    def flaky_from_pretrained(**kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise RuntimeError("_ssl.c:1015: The handshake operation timed out")
        return MagicMock(name="loaded-model")

    monkeypatch.setattr(engine_module.Llama, "from_pretrained", flaky_from_pretrained)
    monkeypatch.setattr(engine_module.time, "sleep", lambda _seconds: None)  # skip real delay

    llm = engine_module.LLMEngine(repo_id="some/repo", filename="model.gguf")

    assert call_count["n"] == 3
    assert llm._model is not None


def test_gives_up_after_max_attempts_and_raises_runtime_error(monkeypatch) -> None:
    engine_module = _import_engine()

    def always_fails(**kwargs):
        raise RuntimeError("_ssl.c:1015: The handshake operation timed out")

    monkeypatch.setattr(engine_module.Llama, "from_pretrained", always_fails)
    monkeypatch.setattr(engine_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="Could not load LLM"):
        engine_module.LLMEngine(repo_id="some/repo", filename="model.gguf")


def test_succeeds_first_try_without_any_retry_delay(monkeypatch) -> None:
    engine_module = _import_engine()

    call_count = {"n": 0}

    def succeeds_immediately(**kwargs):
        call_count["n"] += 1
        return MagicMock(name="loaded-model")

    monkeypatch.setattr(engine_module.Llama, "from_pretrained", succeeds_immediately)
    sleep_mock = MagicMock()
    monkeypatch.setattr(engine_module.time, "sleep", sleep_mock)

    engine_module.LLMEngine(repo_id="some/repo", filename="model.gguf")

    assert call_count["n"] == 1
    sleep_mock.assert_not_called()


def test_local_model_path_bypasses_retry_logic_entirely(monkeypatch) -> None:
    engine_module = _import_engine()

    from_pretrained_mock = MagicMock()
    monkeypatch.setattr(engine_module.Llama, "from_pretrained", from_pretrained_mock)

    with patch.object(engine_module, "Llama") as llama_ctor:
        llama_ctor.return_value = MagicMock(name="local-model")
        engine_module.LLMEngine(local_model_path="/some/local/model.gguf")
        llama_ctor.assert_called_once()

    from_pretrained_mock.assert_not_called()
