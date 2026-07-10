# HANDOFF.md

**Last updated:** 2026-07-09
**Milestone completed:** Milestone 3 — Speech-to-Text ✅

---

## Summary of work completed

Milestone 3 is complete: local speech-to-text via Faster-Whisper, silence-based
utterance capture, and full wiring so a spoken command after "Hey Jarvis"
gets transcribed and logged, with Aura transitioning LISTENING → THINKING →
IDLE. Built in three parts:

1. **`speech/transcriber.py`** — Faster-Whisper wrapper. Verified the real
   API via `inspect.signature()` before writing code (lesson learned from
   Milestone 2's openWakeWord version mismatch). Could NOT test actual
   transcription in this sandbox — Hugging Face Hub (where model weights
   download from) isn't on the sandbox's allowed network list. Tested what
   was possible offline: audio format conversion, and the download-failure
   error path (which really did fail, for real, since HF is genuinely
   blocked here — confirmed it's wrapped in a clean `RuntimeError` instead
   of a raw traceback).
2. **`speech/listening_session.py`** — RMS-based silence detection for
   knowing when an utterance is complete. Fully testable offline (pure
   signal math). 4 synthetic edge-case tests (normal flow, no-speech
   timeout, continuous-speech safety cap, post-finish idempotency), all
   passing. Silence threshold (300) sanity-checked against real recorded
   speech audio (RMS peaks 6,000-10,000) — well-calibrated.
3. **Full wiring** — `config/schema.py` `SpeechSettings`,
   `app/transcript_bridge.py` (Qt signal bridge, same pattern as the wake
   word bridge), and a substantial rewrite of `voice/service.py` to
   orchestrate mode-based frame routing (wake word detector vs. active
   listening session) and background-thread transcription. `main.py`
   updated to wire the new `on_transcript` callback through to Aura state
   transitions.

## Files created

```
iris/
├── app/
│   └── transcript_bridge.py      (new)
├── speech/
│   ├── listening_session.py      (new)
│   └── transcriber.py            (new)
```

## Files modified

- `voice/service.py` — substantially rewritten: `VoiceActivationService`
  now takes both `voice_settings` and `speech_settings`, plus
  `on_wake_word` and `on_transcript` callbacks (was just `settings` +
  `on_wake_word`). Owns mode-based frame routing between the wake word
  detector and an active `ListeningSession`. Transcriber load failure is
  now handled gracefully (see "Important implementation details").
- `main.py` — wires `TranscriptBridge`, updated `VoiceActivationService`
  construction call to match the new signature, added `on_transcribed` /
  `on_no_speech_detected` handlers driving Aura LISTENING → THINKING → IDLE.
- `config/schema.py` — added `SpeechSettings`, registered on `AppSettings`
- `config/default_config.yaml` — added `speech:` section
- `docs/ROADMAP.md` — Milestone 3 marked complete
- `docs/ARCHITECTURE.md` — documented `speech/` module split, updated the
  data-flow diagram to reflect current (not just aspirational) state
- `docs/DECISIONS.md` — four new entries: speech-to-text failure isolation
  from wake word, mode-based single-stream frame routing, background-thread
  transcription
- `docs/TODO.md` — rewritten for Milestone 4 (LLM integration) next steps
- `README.md` — updated status and testing instructions

## Dependencies added

None — `faster-whisper` was already declared in the `speech` extras group
since Milestone 1's `pyproject.toml` scaffolding (just unused until now).

## Important implementation details

- **Transcriber load failure does NOT disable wake word detection.**
  `VoiceActivationService.__init__` catches any exception loading the
  Faster-Whisper model and sets `self._transcriber = None` rather than
  letting construction fail — verified directly in this sandbox (real HF
  network failure), confirmed wake word detection still fires correctly
  end-to-end afterward.
- **Single microphone stream, mode-based routing.** `VoiceActivationService._handle_frame()`
  routes each frame to either `WakeWordDetector.process_frame()` or the
  active `ListeningSession.add_frame()`, never both, based on whether
  `self._listening_session` is set. Avoids opening two simultaneous audio
  device streams.
- **Transcription runs on a dedicated worker thread**, never the audio
  callback thread or the Qt main thread. As soon as a `ListeningSession`
  finishes, it's cleared immediately (frame routing goes back to wake-word
  mode with no gap) and a `threading.Thread` picks up the actual
  transcription work.
- **Three ways an utterance capture can end** (see
  `speech/listening_session.py`): silence after speech (normal case),
  initial timeout if nobody speaks at all (e.g. accidental wake word），or
  a max-duration safety cap regardless. Current defaults: 1s end-silence,
  3s initial timeout, 10s max duration — all configurable via
  `config.yaml`'s `speech:` section.
- **No LLM integration yet.** `main.py`'s `on_transcribed()` currently sets
  Aura to THINKING then immediately back to IDLE with a `TODO (Milestone 4)`
  comment marking where the actual LLM call will go.

## Current folder structure

See "Files created" above for what's new; full structure otherwise
unchanged from Milestone 2's `HANDOFF.md`.

## Known issues

- None blocking. Same offscreen-Qt-plugin cosmetic stderr line as prior
  milestones when testing in this sandbox — expected, not a real issue.
- **Real end-to-end transcription has NOT been verified on real hardware
  yet.** Unlike wake word detection (which was verified via GitHub-hosted
  test audio, then confirmed live on the user's Windows machine),
  Hugging Face Hub is blocked in this dev sandbox, so `Transcriber` could
  only be tested for its error-handling path, not actual transcription
  accuracy or the real download flow. **The next session should verify:**
  `pip install -e ".[speech]"` (already includes faster-whisper), run
  `main.py`, say "Hey Jarvis" followed by a command, and confirm the
  console logs a reasonable transcription of what was actually said.
  First run will download Faster-Whisper model weights (~500MB-1GB
  depending on model size) — needs internet, one-time only.
- **Silence detection tuning is unverified on real hardware.** The RMS
  threshold and timeouts were reasoned about mathematically and checked
  against one clean pre-recorded sample, not tested with real background
  noise, varying microphone sensitivity, or varying speaking volume. If
  utterances cut off too early or run long on the real machine, start by
  adjusting `speech.silence_rms_threshold` and `speech.end_silence_seconds`
  in `config.yaml`.
- **Startup time on the Quadro M3000M laptop is unmeasured.** Both the wake
  word model and the Faster-Whisper model now load eagerly at startup.
  This laptop is notably weaker than the documented RTX 3070 Ti target
  hardware (see `docs/DECISIONS.md`/`docs/ARCHITECTURE.md` — target
  hardware docs were deliberately NOT changed per the user's explicit
  request; the laptop is for testing only). Worth timing actual startup
  and reconsidering lazy-loading if it's slow enough to be annoying during
  development.
- `tests/` package is still empty — flagged again, now genuinely overdue
  given the amount of real logic in `voice/` and `speech/`.

## Testing performed

1. **`speech/transcriber.py`:**
   - `int16_to_float32()` conversion — verified correct, properly normalized.
   - Model load failure — verified real `RuntimeError` wrapping (genuine
     network failure in this sandbox, not simulated).
   - **NOT tested: actual transcription accuracy** (needs Hugging Face
     access this sandbox doesn't have).
2. **`speech/listening_session.py`:**
   - Normal flow (silence → speech → silence) — PASS.
   - No-speech initial timeout — PASS.
   - Continuous-speech max-duration safety cap — PASS.
   - Post-finish idempotency — PASS.
   - Silence threshold sanity-checked against real speech audio RMS values — PASS.
3. **`voice/service.py` (rewritten):**
   - `VoiceActivationService` constructs successfully despite transcriber
     load failure (`self._transcriber is None`) — PASS.
   - Wake word detection still fires correctly end-to-end through the full
     service despite transcriber being unavailable (real audio, score
     0.9999) — PASS.
   - `_finish_listening_session()` correctly falls back to an empty
     transcript when the transcriber is unavailable — PASS.
4. **Full `main.py` end-to-end:** ran as a real subprocess; confirmed the
   full startup sequence (wake word model load → transcriber load attempt
   → graceful failure → mic start attempt → graceful failure → app
   continues running) all logs correctly and the app doesn't crash.
5. **`app/transcript_bridge.py`:** directly tested cross-thread signal
   delivery (emit from a background thread, receive on the Qt main thread)
   for both the `transcribed` and `no_speech_detected` signals — PASS.
6. All test artifacts (`.iris_data/`, `__pycache__/`, cloned test-fixture
   repos) cleaned up afterward.

## Current project status

Milestone 3 is code-complete and as thoroughly tested as this sandbox
allows — every piece that could be verified offline or against
GitHub-hosted resources was verified for real, not assumed. The one
genuine gap is real transcription accuracy, which needs Hugging Face
access this sandbox doesn't have.

## Next milestone

**Milestone 4 — Local LLM Integration**, via llama.cpp. See
`docs/ROADMAP.md` for scope and `docs/TODO.md` for specific next actions,
including picking a model/quantization appropriate for the documented RTX
3070 Ti (8GB VRAM) target and wiring the actual response generation into
the `on_transcribed()` handler in `main.py` where the `TODO (Milestone 4)`
comment currently sits.

## Ready-to-copy prompt for the next session

```
Continue development of Iris, a fully local AI desktop copilot for Windows.

Before writing any code:
1. Read HANDOFF.md (this file)
2. Read every file inside /docs
3. Understand the current project state

Milestone 3 (speech-to-text) is code-complete but has an unverified gap:
real transcription accuracy was not testable in the previous session's dev
sandbox (no Hugging Face Hub access). Before starting Milestone 4, please:
  1. Run `pip install -e ".[speech]"` and `python main.py` on this machine
  2. Say "Hey Jarvis" followed by a short command (e.g. "what time is it")
  3. Confirm the console logs a reasonable transcription of what was said
  4. Also check startup time feels acceptable on this laptop's hardware
     (Quadro M3000M / i7-6820HQ) — both the wake word and Whisper models
     load eagerly at startup
  5. Report back what you observed before we proceed

Once that's confirmed, start Milestone 4 — Local LLM Integration, as
scoped in docs/ROADMAP.md and docs/TODO.md.

Work incrementally, in small parts (not all at once — confirm progress
with me between parts). Do not begin implementing anything beyond
Milestone 4's scope. End the session by updating HANDOFF.md and
docs/TODO.md, and only docs/ROADMAP.md / docs/ARCHITECTURE.md /
docs/DECISIONS.md / README.md if something actually changed.
```
