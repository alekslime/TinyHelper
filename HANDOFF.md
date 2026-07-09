# HANDOFF.md

**Last updated:** 2026-07-09
**Milestone completed:** Milestone 2 — Wake Word Detection ✅

---

## Summary of work completed

Milestone 2 is complete: microphone audio capture, wake word detection
(OpenWakeWord), and full wiring into `main.py` with proper thread-safety
and graceful degradation. Built in three incremental parts:

1. `voice/audio_stream.py` — `MicrophoneStream`, raw 16kHz mic capture via
   `sounddevice`. Smoke-tested (construction, device listing).
2. `voice/wake_word.py` — `WakeWordDetector` wrapping OpenWakeWord.
   **Tested against real speech audio** (not just synthetic/silent
   frames): correctly detected a real "Hey Mycroft" utterance and produced
   zero false positives on unrelated "Alexa" speech.
3. `config/schema.py` `VoiceSettings` + `voice/service.py`
   `VoiceActivationService` + `app/wake_word_bridge.py` `WakeWordBridge` +
   full `main.py` wiring. Tested three ways: with speech deps + no mic
   hardware (graceful error handling), in a clean core-only venv with no
   speech deps at all (graceful ImportError handling), and the underlying
   detection logic against real audio (from part 2).

## Files created

```
iris/
├── app/
│   └── wake_word_bridge.py       (new)
├── voice/
│   ├── audio_stream.py           (new)
│   ├── wake_word.py              (new)
│   └── service.py                (new)
```

## Files modified

- `main.py` — wired voice activation in; imports `voice.service`
  defensively (try/except ImportError) since it depends on optional
  `speech` extras
- `config/schema.py` — added `VoiceSettings`, registered on `AppSettings`
- `config/default_config.yaml` — added `voice:` section
- `pyproject.toml` — added `sounddevice` to the `speech` extras group
  (alongside existing `faster-whisper`, `openwakeword`)
- `README.md` — documented `pip install -e ".[speech]"` and wake word testing
- `docs/ROADMAP.md` — Milestone 2 marked complete
- `docs/ARCHITECTURE.md` — documented `voice/` module split and the Qt
  signal threading pattern
- `docs/DECISIONS.md` — two new entries: Qt signal bridge for thread
  safety, graceful degradation for voice activation
- `docs/TODO.md` — rewritten for Milestone 3 (speech-to-text) next steps
- `.gitignore` — added explicit `*.egg-info` pattern

## Dependencies added

Added to the existing `speech` optional extras group in `pyproject.toml`
(not core — still opt-in via `pip install -e ".[speech]"`):
- `sounddevice>=0.4.6` (new)
- `openwakeword>=0.6.0` (was already declared, now actually used)

No changes to core dependencies.

## Important implementation details

- **Threading:** `sounddevice`'s audio callback runs on a background
  thread. Wake word detections cross into Qt's main thread via
  `app/wake_word_bridge.py`'s `WakeWordBridge` (`QObject` + `Signal`), not
  a direct function call. This is required correctness now, and will be
  load-bearing once Aura does real GPU rendering (Milestone 6) — see
  `docs/DECISIONS.md`.
- **Graceful degradation, two layers:**
  1. If the `speech` extras aren't installed, `main.py` catches the
     `ImportError` on `from voice.service import VoiceActivationService`
     and continues without voice activation (logs a warning).
  2. If they *are* installed but starting the mic stream fails (no
     device, permission denied, etc.), `VoiceActivationService.start()`
     catches the exception, logs it, returns `False`, and `main.py`
     continues running (sets Aura to `ERROR` state).
  Neither case crashes the app.
- **Wake word model resolution:** `voice/wake_word.py:resolve_model()`
  accepts either a bundled stock model name (currently configured as
  `"hey_jarvis"`, the placeholder) or a full path to a custom `.onnx` file.
  Stock names trigger a one-time download via OpenWakeWord's
  `download_models()` (cached locally after first run — see
  `docs/DECISIONS.md`). Swapping to a trained "Hey Iris" model later is a
  config change only — set `voice.wake_word_model` in `config.yaml` to the
  model's file path, which skips the download path entirely.
- **Detection debouncing:** `WakeWordDetector` requires 2 consecutive
  frames (~160ms) above the confidence threshold (default 0.5) before
  firing, to avoid single-frame noise spikes causing false triggers.

## Current folder structure

See "Files created" above for what's new; full structure otherwise
unchanged from Milestone 1's `HANDOFF.md`.

## Known issues

- None blocking. Same offscreen-Qt-plugin cosmetic stderr line as
  Milestone 1 when testing in this sandbox (`propagateSizeHints()` warning)
  — expected, not a real issue, shouldn't occur on Windows with a real display.
- **RESOLVED (post-handoff correction):** Real testing on the actual
  Windows machine surfaced a bug this session's dev-sandbox testing missed:
  `voice/wake_word.py` was written against openWakeWord's older bundled-models
  API. The pip-installed `openwakeword==0.6.0` no longer bundles stock
  model files at all — they must be explicitly downloaded once via
  `openwakeword.utils.download_models()`. This caused a `ValueError` crash
  on first launch on Windows. Fixed by rewriting `resolve_model()` to
  explicitly trigger the download for stock model names and always pass
  `inference_framework="onnx"`. Re-verified against real speech audio
  (`hey_mycroft` test clip, score 1.000) and a simulated fresh-install
  (model files deleted, reconstructed from scratch, download re-triggered
  successfully) in the dev sandbox after the fix, using the exact
  `openwakeword==0.6.0` version pulled fresh from PyPI (not a stale cached
  version, which is what caused this to be missed initially). See
  `docs/DECISIONS.md` for the full writeup.
- **Real end-to-end microphone verification: DONE.** Confirmed on the
  actual Windows target machine — model downloaded correctly, mic started,
  "Hey Jarvis" detected with strong confidence (scores 0.80-0.99), Aura
  transitioned to LISTENING.
- **RESOLVED (found via the real-mic test above):** A single spoken
  utterance was firing the detection callback 3-4 times instead of once
  (confirmed by the user saying "Hey Jarvis" exactly once and observing 4
  log lines). Root cause: spoken words stay above the confidence threshold
  for many more frames than the consecutive-frame confirmation needs,
  causing repeated re-triggers within one utterance. Fixed by adding a
  cooldown period (`voice.cooldown_seconds`, default 1.5s) that suppresses
  further detections for a model right after it fires. Verified directly:
  same real audio clip produced 3 detections with cooldown disabled, 1
  with it enabled. **Not yet re-verified on the real Windows mic** — the
  next session should confirm one "Hey Jarvis" now produces exactly one
  detection line.
- `tests/` package is still empty. Flagged again in `docs/TODO.md` — now
  more pressing since `voice/` has real logic worth protecting with
  regression tests before Milestone 3 adds more surface area.

## Testing performed

1. **`MicrophoneStream` construction/API smoke test** — PASS (no real
   hardware available in this sandbox to test actual capture).
2. **`WakeWordDetector` against real speech audio** (cloned test fixtures
   from the openWakeWord GitHub repo, deleted after use):
   - Real "Hey Mycroft" utterance → 2 detections, scores 0.967 and 0.998. PASS.
   - Real "Alexa" utterance (different phrase) → 0 detections. PASS (no false positive).
3. **Full `main.py` end-to-end, speech deps installed, no mic hardware:**
   Confirmed the app logs the `PortAudioError`, sets Aura to `ERROR`, and
   keeps running (didn't crash) via a real subprocess launch. PASS.
4. **Full `main.py` end-to-end, core-only venv (no speech extras):**
   Built a clean venv with only `pip install -e .`, confirmed
   `openwakeword`/`sounddevice` were absent, ran `main.py`, confirmed it
   logged a warning and launched successfully anyway. PASS.
5. Config schema smoke-tested after adding `VoiceSettings` — loads and
   validates correctly, `voice.wake_word_model` defaults to `"hey_jarvis"`.
6. All test artifacts (`.iris_data/`, `__pycache__/`, cloned test-fixture
   repo, temporary core-only venv) cleaned up afterward.

## Current project status

Milestone 2 complete and verified as thoroughly as this headless,
mic-less dev sandbox allows. The one meaningful gap is real-microphone
verification, called out above and in the next-session prompt below.

## Next milestone

**Milestone 3 — Speech-to-Text**, integrating Faster-Whisper. See
`docs/ROADMAP.md` for scope and `docs/TODO.md` for specific next actions,
including reusing `voice/audio_stream.py`'s `MicrophoneStream` for the
post-wake-word listening window and deciding on end-of-utterance detection.

## Ready-to-copy prompt for the next session

```
Continue development of Iris, a fully local AI desktop copilot for Windows.

Before writing any code:
1. Read HANDOFF.md (this file)
2. Read every file inside /docs
3. Understand the current project state

Milestone 2 (wake word detection) is complete but has one unverified gap:
real-microphone testing was not possible in the previous session's dev
sandbox (no audio hardware). Before starting Milestone 3, please:
  1. Run `pip install -e ".[speech]"` and `python main.py` on this machine
  2. Say "Hey Jarvis" into the real microphone
  3. Confirm in the logs that Aura transitions to LISTENING
  4. Report back whether this worked before we proceed

Once that's confirmed, start Milestone 3 — Speech-to-Text, as scoped in
docs/ROADMAP.md and docs/TODO.md.

Work incrementally, in small parts (not all at once — confirm progress
with me between parts). Do not begin implementing anything beyond
Milestone 3's scope. End the session by updating HANDOFF.md and
docs/TODO.md, and only docs/ROADMAP.md / docs/ARCHITECTURE.md /
docs/DECISIONS.md / README.md if something actually changed.
```
