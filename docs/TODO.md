# TODO

Granular, actionable task tracking. Coarser-grained progress lives in
`docs/ROADMAP.md`; this file is for the immediate next steps and small
loose ends.

## Immediate next steps (Milestone 5 — Screen Capture + Vision)

- [ ] Integrate MSS for screenshot capture
- [ ] Vision model integration (ONNX Runtime)
- [ ] Screenshot discarded after use by default (privacy requirement)
- [ ] Decide how vision context reaches the LLM prompt (e.g. a vision
      model produces a text description that gets appended to the user's
      transcript before `LLMGenerator.generate()` is called)

## Loose ends / small items

- [ ] **Real LLM generation has NOT been verified end-to-end on real
      hardware yet** — same category of gap as Milestone 3's Whisper
      transcription. This sandbox has no Hugging Face Hub access, so
      `LLMGenerator` could only be verified for its graceful-failure path
      (dependencies missing / model load failure), not actual generation
      quality, latency, or VRAM usage on the RTX 3070 Ti or the laptop.
      Next session on real hardware should: `pip install -e ".[llm]"`,
      run `main.py`, use the debug text input (or real voice) to ask a
      question, and confirm a reasonable response appears in the window
      and the console within a few seconds.
- [ ] The default model (`bartowski/Qwen2.5-1.5B-Instruct-GGUF`,
      Q4_K_M) was picked to get something small and fast working
      end-to-end, not for response quality — revisit once real hardware
      testing shows how much headroom the 3070 Ti / laptop actually have.
      Swapping models is a one-line `config.yaml` change
      (`llm.repo_id`/`llm.filename`, or `llm.model_path` for a local
      file) — no code changes needed.
- [ ] No conversation memory yet — each `LLMGenerator.generate()` call is
      independent, seeded only with the system prompt. That's
      Milestone 9 (Conversation Memory).
- [ ] LLM responses are currently just displayed as text in the
      placeholder window (`MainWindow.show_response`) — no voice output
      yet. That's Milestone 8.
- [ ] Debug text input (`app/main_window.py`, gated by `debug.enabled`)
      was added mid-Milestone-3 for testing convenience without needing to
      speak. Remember to set `debug.enabled: false` (or remove the panel
      entirely) once Milestone 10's real settings UI / end-user experience
      lands — it's explicitly a dev aid, not part of Iris's intended UX.
- [ ] Add `tests/` content — still empty, now genuinely overdue. `voice/`,
      `speech/`, and now `llm/` all have real, testable logic that would
      benefit from a proper pytest suite instead of ad-hoc verification
      scripts used during development.
- [ ] Add a `LICENSE` file (MIT referenced in `pyproject.toml` but not yet present)
- [ ] Consider a `Makefile` or `justfile` for common dev commands
      (`run`, `test`, `lint`, `format`) once there's enough to script
- [ ] `NullAuraRenderer` still has no visual feedback — Aura state changes
      are only visible in logs. Getting more noticeable now that a full
      conversation turn (wake word → listen → transcribe → THINKING →
      generate → IDLE) happens with zero visual feedback beyond the
      placeholder window's response text. Worth reconsidering the
      priority of a minimal visual stopgap vs. waiting for the full
      Milestone 6 GPU-rendered glow.
- [ ] The silence-detection thresholds in `speech/listening_session.py`
      (`silence_rms_threshold`, timeouts) were tuned against one clean
      recorded sample and reasoned about mathematically, not tested across
      varied real-world conditions (background noise, different
      microphones, different speaking volumes). Revisit if real usage on
      the Windows machine shows utterances cutting off early or running
      long.
- [ ] `speech/transcriber.py` and `llm/generator.py` both load their
      models eagerly at startup, same as the wake word model. On the
      Quadro M3000M laptop (weaker than the documented RTX 3070 Ti
      target), this may add real time to startup — worth timing on real
      hardware and reconsidering lazy-loading if it's noticeably slow.

## Known issues

- None currently open beyond the real-hardware verification gaps noted
  above. See `HANDOFF.md` "Known issues" for details.
