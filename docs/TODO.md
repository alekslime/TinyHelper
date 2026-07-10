# TODO

Granular, actionable task tracking. Coarser-grained progress lives in
`docs/ROADMAP.md`; this file is for the immediate next steps and small
loose ends.

## Immediate next steps (Milestone 4 — Local LLM Integration)

- [ ] Integrate llama.cpp via llama-cpp-python
- [ ] Pick a model appropriate for 8GB VRAM (RTX 3070 Ti) — research
      quantization levels (Q4_K_M etc.) that balance quality/speed/VRAM
- [ ] Basic prompt/response loop (text only, no vision yet — vision is
      Milestone 5)
- [ ] Wire LLM response into `main.py`: currently `on_transcribed()`
      immediately sets Aura THINKING → IDLE with no actual processing in
      between (see the `TODO (Milestone 4)` comment in `main.py`) — this
      is where the LLM call goes, keeping Aura in THINKING while it runs
- [ ] Add `LLMSettings` to `config/schema.py` (model path, context size,
      GPU layers, temperature) following the `VoiceSettings`/`SpeechSettings` pattern
- [ ] Decide how the LLM response reaches the user — text-only for now
      (voice output is Milestone 8), so probably just logged/displayed in
      the placeholder window for this milestone

## Loose ends / small items

- [ ] Debug text input (`app/main_window.py`, gated by `debug.enabled`)
      was added mid-Milestone-3 for testing convenience without needing to
      speak. Remember to set `debug.enabled: false` (or remove the panel
      entirely) once Milestone 10's real settings UI / end-user experience
      lands — it's explicitly a dev aid, not part of Iris's intended UX.

- [ ] Add `tests/` content — still empty, now genuinely overdue. `voice/`
      and `speech/` both have real, testable logic (wake word thresholds,
      cooldown behavior, silence detection state machine, audio format
      conversion) that would benefit from a proper pytest suite instead of
      the ad-hoc verification scripts used during development. Worth doing
      before Milestone 4 adds LLM complexity on top.
- [ ] Add a `LICENSE` file (MIT referenced in `pyproject.toml` but not yet present)
- [ ] Consider a `Makefile` or `justfile` for common dev commands
      (`run`, `test`, `lint`, `format`) once there's enough to script
- [ ] `NullAuraRenderer` still has no visual feedback — Aura state changes
      are only visible in logs. Getting more noticeable now that a full
      conversation turn (wake word → listen → transcribe → THINKING → IDLE)
      happens with zero visual feedback. Worth reconsidering the priority
      of a minimal visual stopgap vs. waiting for the full Milestone 6
      GPU-rendered glow.
- [ ] The silence-detection thresholds in `speech/listening_session.py`
      (`silence_rms_threshold`, timeouts) were tuned against one clean
      recorded sample and reasoned about mathematically, not tested across
      varied real-world conditions (background noise, different
      microphones, different speaking volumes). Revisit if real usage on
      the Windows machine shows utterances cutting off early or running
      long.
- [ ] `speech/transcriber.py` loads the Faster-Whisper model eagerly at
      `VoiceActivationService` construction time, same as the wake word
      model. On the Quadro M3000M laptop (weaker than the documented RTX
      3070 Ti target), this may add a few seconds to startup — worth
      timing on real hardware and reconsidering lazy-loading if it's
      noticeably slow.

## Known issues

- None currently open. See `HANDOFF.md` "Known issues" for anything
  discovered during the most recent session.
