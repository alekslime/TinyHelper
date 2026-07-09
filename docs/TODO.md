# TODO

Granular, actionable task tracking. Coarser-grained progress lives in
`docs/ROADMAP.md`; this file is for the immediate next steps and small
loose ends.

## Immediate next steps (Milestone 3 — Speech-to-Text)

- [ ] Add `speech/` module: audio buffering from wake-word-triggered
      listening window (reuse `voice/audio_stream.py`'s `MicrophoneStream`
      — it's already decoupled from wake word logic)
- [ ] Integrate Faster-Whisper for local transcription
- [ ] Decide on end-of-utterance detection (silence timeout vs. VAD —
      OpenWakeWord ships a Silero VAD model already, may be reusable here)
- [ ] Wire transcription result into `main.py` → Aura → THINKING transition
- [ ] Add `SpeechSettings` to `config/schema.py` (model size, language,
      silence timeout) following the `VoiceSettings` pattern

## Loose ends / small items

- [ ] Add `tests/` content — still empty. Getting more pressing now that
      `voice/` has real logic (wake word threshold behavior, model
      resolution, graceful-degradation paths) that would benefit from
      regression tests before Milestone 3 adds more surface area.
- [ ] Add a `LICENSE` file (MIT referenced in `pyproject.toml` but not yet present)
- [ ] Consider a `Makefile` or `justfile` for common dev commands
      (`run`, `test`, `lint`, `format`) once there's enough to script
- [ ] `NullAuraRenderer` still has no visual feedback — Aura state changes
      (e.g. IDLE → LISTENING → ERROR) are currently only visible in logs.
      Fine for now, but will make manual testing of Milestone 3 (THINKING
      state, etc.) harder to verify without watching logs. Consider this
      when scoping Milestone 6 (Aura rendering) vs. pulling a minimal
      visual stopgap forward.
- [ ] `voice/wake_word.py` resolves stock model names via string prefix
      matching (`Path(path).stem.startswith(name)`). Works fine for the
      current bundled models but is a little loose — revisit if a future
      stock model name is a prefix of another (unlikely, but noted).

## Known issues

- None currently open. See `HANDOFF.md` "Known issues" for anything
  discovered during the most recent session.
