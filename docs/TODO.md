# TODO

Granular, actionable task tracking. Coarser-grained progress lives in
`docs/ROADMAP.md`; this file is for the immediate next steps and small
loose ends.

## Milestone 5 — Screen Capture + Vision — COMPLETE (code), pending real-hardware verification

- [x] Integrate MSS for screenshot capture — `vision/capture.py`'s
      `ScreenCapture`, plus `config.schema.VisionSettings`. Verified for
      real under Xvfb in the dev sandbox (capture, debug-save-to-disk,
      and the out-of-range monitor_index error path all exercised).
- [x] Vision model integration (ONNX Runtime) — `vision/model.py`'s
      `VisionModel` (ViT encoder + non-merged GPT-2 decoder via
      `Xenova/vit-gpt2-image-captioning`'s ONNX export, `tokenizers` for
      id↔text). Wired into `main.py`: the LLM worker thread captures a
      screenshot, captions it, and prepends the caption to the prompt
      before calling `LLMEngine.generate()`.
- [x] Screenshot discarded after use by default (privacy requirement) —
      and the whole feature (capture + captioning + prompt-folding) is
      gated behind `vision.enabled` (default `false`), opt-in on top of
      the extra being installed. See `docs/DECISIONS.md`.
- [x] Decided how vision context reaches the LLM prompt — a bracketed
      prefix (`"[Current screen shows: {caption}]\n\nUser: {text}"`)
      built in `main.py`, no changes to `llm/engine.py`'s single-string
      interface. Flagged in `docs/DECISIONS.md` as a starting point to
      revisit once real captions are seen on real hardware.
- [ ] **Vision model has NOT been verified end-to-end on real hardware.**
      This sandbox genuinely cannot reach Hugging Face Hub (confirmed via
      a real 403/connection failure, not simulated), so `VisionModel`
      could only be verified for its graceful-failure path — same
      limitation as Milestone 4's LLM. Also unverified, since they need
      the actual downloaded ONNX files to check: the encoder/decoder
      input/output tensor names (`pixel_values`, `input_ids`,
      `encoder_hidden_states`) assumed in `vision/model.py` match what
      `Xenova/vit-gpt2-image-captioning`'s ONNX export actually uses, and
      whether the plain (non-merged) `decoder_model.onnx` file exists at
      that path in the repo at all — Xenova's exact file layout wasn't
      directly inspectable from this sandbox either. **Next session on
      real hardware should:** `pip install -e ".[vision]"`, set
      `vision.enabled: true` in config, run `main.py`, ask a question
      with something on screen, and confirm a real caption shows up
      (check the console at `DEBUG` level for "Screen context added to
      prompt") rather than a load/inference error. If the assumed
      tensor/file names are wrong, the fix is local to `vision/model.py`
      — nothing else depends on those specifics.
- [ ] Caption quality/relevance is unverified — greedy decoding (no
      beam search, no sampling) on a small captioning model may produce
      generic or repetitive descriptions. Revisit once real captions are
      visible on real hardware; a better/bigger vision model is a
      config-only swap (`vision.repo_id`/filenames), same shape as
      Milestone 4's LLM.

## Milestone 6 — Aura Rendering — COMPLETE (code + offscreen visual verification), pending real-display check

- [x] Real ambient edge glow — `aura/renderer/glow_renderer.py`'s
      `GlowAuraRenderer`. Verified for real in this sandbox: rendered
      each `AuraState` offscreen to a PNG and confirmed via pixel
      sampling that glow intensity peaks at corners/edges and fades to
      fully transparent by screen center, with no visible seam between
      edge bands.
- [x] State-based color transitions — a 350ms `QVariantAnimation`
      cross-fade per `set_state()` call, verified the animation reaches
      the correct target color.
- [x] Smooth fade, no sharp edges, no pulsing — confirmed by the pixel
      sampling above (smooth gradient falloff) and by inspection of the
      animation code (single cross-fade per transition, nothing loops).
- [x] **Feathered + breathing update (2026-07-11, later same day).** After
      seeing the thin-core version on real hardware, feedback was that it
      looked flat and had a harsh seam where the core line met the bloom.
      Replaced the separate core-rectangle + bloom-rectangle pair with a
      single continuous multi-stop gradient per edge (feathers up from 0
      at the true screen edge over `FEATHER_PX` = 12px, peaks, then
      decays smoothly to 0 by `GLOW_DEPTH`) — removes the seam entirely.
      Also added a slow, continuous "breathing" pulse: a `QTimer`-driven
      sine wave (`BREATH_PERIOD_S` = 4.2s, oscillating peak alpha between
      `BREATH_MIN`/`BREATH_MAX` = 0.72–1.0) so the border has a sense of
      life instead of sitting at one flat brightness. This intentionally
      revises the original "no pulsing" constraint from Milestone 6 —
      see `docs/DECISIONS.md`. Verified offscreen: rendered the gradient
      at multiple breath phases and a close-up corner crop to confirm no
      visible seam and a believable dim→bright range. **Still needs a
      real-hardware look** — breathing speed/amplitude and the feather
      width were picked by eye, not tuned against a real display.
      real hardware, the original wide (140px) soft-gradient wash read as
      a hazy tint rather than a visible border, especially over bright
      screen content. Replaced with a bias-light-strip look: a thin,
      near-solid, saturation-boosted "core" line (`CORE_WIDTH` = 5px,
      `CORE_ALPHA` = 235) right at the screen edge, plus a much shorter
      bloom band (`GLOW_DEPTH` dropped from 140px to 70px) for soft
      falloff instead of a room-filling haze. Added `_vivid()` to push
      every state color to near-max saturation/value so the strip reads
      as punchy neon rather than the flatter tones used elsewhere in the
      app's palette. Re-verified offscreen (pixel-sampled each state) but
      **not yet re-confirmed over real desktop content** — that's the
      next real-hardware check.
- [ ] **Never shown on a real display with the new style.** The original
      wide-gradient version was confirmed working on real hardware
      (glow visible, though thin/washed-out per feedback); the new
      thin-core-line version above has only been verified offscreen in
      this sandbox. Next session on real hardware should: run
      `main.py`, confirm the border reads as a crisp, saturated line
      hugging all four edges (not just top), and trigger a few state
      changes to see the cross-fade live.
- [ ] **Single-monitor only.** `GlowAuraRenderer.initialize()` sizes the
      overlay to `QGuiApplication.primaryScreen()`'s geometry, not the
      combined virtual geometry of all monitors — on a multi-monitor
      setup the glow will only appear around the primary display. Worth
      fixing once real multi-monitor hardware is available to test
      against — `vision/capture.py`'s `ScreenCapture.list_monitors()`
      may be useful groundwork here.
- [ ] `GLOW_DEPTH`, `CORE_WIDTH`, `CORE_ALPHA`, `GLOW_EDGE_ALPHA`, and
      `TRANSITION_MS` in `glow_renderer.py` were picked by eye/reasoning,
      not tuned against a real display — may still need adjustment once
      seen for real (e.g. core width/alpha may want to differ by state,
      or by how bright the underlying desktop content is).

## Loose ends / small items

- [ ] **Real LLM generation has NOT been verified end-to-end on real
      hardware yet** — same category of gap as Milestone 3's Whisper
      transcription. This sandbox has no Hugging Face Hub access, so
      `LLMEngine` could only be verified for its graceful-failure path
      (dependencies missing / model load failure), not actual generation
      quality, latency, or VRAM usage on the RTX 3070 Ti or the laptop.
      Next session on real hardware should: `pip install -e ".[llm]"`,
      run `main.py`, use the debug text input (or real voice) to ask a
      question, and confirm a reasonable response appears in the window
      and the console within a few seconds.
- [ ] The default model (`Qwen/Qwen2.5-0.5B-Instruct-GGUF`,
      Q4_K_M) was picked to get something small and fast working
      end-to-end, not for response quality — revisit once real hardware
      testing shows how much headroom the 3070 Ti / laptop actually have.
      Swapping models is a one-line `config.yaml` change
      (`llm.repo_id`/`llm.filename`, or `llm.local_model_path` for a local
      file) — no code changes needed.
- [ ] No conversation memory yet — each `LLMEngine.generate()` call is
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
- [ ] Add `tests/` content — was completely empty; now has one file,
      `tests/test_vision_model.py`, covering only `vision/model.py`'s
      `preprocess_image()` (the part that doesn't need real model files
      to test). `voice/`, `speech/`, `llm/`, `vision/capture.py`, and
      `VisionModel` itself all still have zero test coverage and would
      benefit from a proper pytest suite instead of ad-hoc verification
      scripts used during development.
- [ ] Add a `LICENSE` file (MIT referenced in `pyproject.toml` but not yet present)
- [ ] Consider a `Makefile` or `justfile` for common dev commands
      (`run`, `test`, `lint`, `format`) once there's enough to script
- [ ] `GlowAuraRenderer` has no visual guidance rendering yet (arrows,
      highlights, bounding boxes) — that's Milestone 7. It only shows
      the ambient state glow so far.
- [ ] The silence-detection thresholds in `speech/listening_session.py`
      (`silence_rms_threshold`, timeouts) were tuned against one clean
      recorded sample and reasoned about mathematically, not tested across
      varied real-world conditions (background noise, different
      microphones, different speaking volumes). Revisit if real usage on
      the Windows machine shows utterances cutting off early or running
      long.
- [ ] `speech/transcriber.py`, `llm/engine.py`, and now `vision/model.py`
      (when `vision.enabled` is true) all load their models eagerly at
      startup, same as the wake word model. On the Quadro M3000M laptop
      (weaker than the documented RTX 3070 Ti target), this may add real
      time to startup — worth timing on real hardware and reconsidering
      lazy-loading if it's noticeably slow.

## Known issues

- None currently open beyond the real-hardware verification gaps noted
  above. See `HANDOFF.md` "Known issues" for details.
