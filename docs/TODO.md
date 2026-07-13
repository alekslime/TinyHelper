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
- [x] **Verified end-to-end on real hardware (2026-07-13).** Ran with
      `vision.enabled: true`, asked a screen-context question, and got a
      correct, specific description back (confirmed against Adobe
      Premiere Pro on screen). Note: by this point `vision/model.py` had
      already moved on from the original ONNX/Xenova captioning approach
      to MiniCPM-V-2.6 via `llama-cpp-python` (see the module docstring
      and `docs/DECISIONS.md` for the moondream2 → MiniCPM-V rework) — it
      was that later version that got verified, not the original
      ONNX-based one described earlier in this entry.
- [x] Caption quality confirmed reasonable on real hardware (2026-07-13)
      — MiniCPM-V-2.6 correctly identified Adobe Premiere Pro and gave
      screen-grounded editing guidance. Open question flagged separately
      below: it's currently CPU-only per query, which trades quality for
      real latency — worth gating (see "loose ends") rather than running
      on every query.

## Milestone 6 — Aura Rendering — COMPLETE (code + offscreen visual verification), pending real-display check

- [x] Real ambient edge glow — `aura/renderer/glow_renderer.py`'s
      `GlowAuraRenderer`.
- [x] State-based color transitions — a 350ms `QVariantAnimation`
      cross-fade per `set_state()` call, verified the animation reaches
      the correct target color.
- [x] Smooth fade, no sharp edges — see design history below.

**Design history (in order), all same-day (2026-07-11), each round driven
by direct user feedback on the previous one:**

1. **v1 — wide soft gradient wash.** `GLOW_DEPTH` = 140px, a single
   2-stop linear/radial gradient per edge/corner. Confirmed working on
   real hardware, but read as a hazy tint rather than a border, especially
   over bright screen content.
2. **v2 — thin neon core + bloom.** Replaced with a thin, near-solid
   "core" line (5px) plus a shorter bloom band (`GLOW_DEPTH` → 70px), and
   a `_vivid()` HSV boost so state colors read as punchy neon. Fixed the
   "hazy" complaint but introduced a visible seam where the core's inner
   edge met the separately-drawn bloom, and read as flat/static.
3. **v3 — single feathered gradient + breathing.** Merged core and bloom
   into one continuous multi-stop gradient per edge (feathers up from 0
   at the true edge over `FEATHER_PX` = 12px, peaks, decays smoothly to 0
   by `GLOW_DEPTH`) — removed the seam. Added a `QTimer`-driven sine
   "breathing" pulse (`BREATH_PERIOD_S` = 4.2s, alpha oscillating between
   `BREATH_MIN`/`BREATH_MAX` = 0.72–1.0) so it doesn't sit at one flat
   brightness. This intentionally revises Milestone 6's original
   "no pulsing" constraint — see `docs/DECISIONS.md`.
4. **Size experiments, reverted.** User asked to size the glow up 10%,
   then 50%; reported no visible difference either time. Rather than keep
   guessing, did a pixel-level comparison between the user's reference
   screenshot and offscreen renders at 70/105/200px — 70px (the original
   v3 size) was by far the closest match. Reverted to 70/12. **Lesson:**
   when a tweak is reported as "no difference" twice running, stop
   nudging the same direction and go back to direct comparison against a
   reference image instead of guessing again.
5. **v4 — real Gaussian blur.** User asked for an entirely
   different technique, not another parameter tweak. Replaced the
   hand-authored gradient-stack approach with an actual Gaussian blur:
   paint a solid-color band along each edge, blur it with
   `QGraphicsBlurEffect`, cache the result as a `QImage` (rebuilt only on
   resize), and re-tint that cached shape to the current color/breath-
   brightness each frame (cheap — `QPainter.CompositionMode_SourceIn`).
   This gives a genuine bell-curve falloff with zero seams at corners
   (blur handles that for free) instead of a manually tuned decay curve.
   Breathing pulse carried over unchanged from v3. **Liked the technique
   immediately**, but the first pass (`SEED_BAND_PX` = 55,
   `BLUR_RADIUS_PX` = 90) reached ~150-200px inward — reported as "very
   very thick... takes a lot of the screen's edges." Cut both roughly in
   half (`SEED_BAND_PX` = 18, `BLUR_RADIUS_PX` = 38), which fades to
   background by ~70-80px instead — same blur-based technique, just a
   smaller version of it.

**Verification so far:** all of the above verified offscreen only —
rendered each `AuraState`, pixel-sampled the falloff curve, and (for v4)
confirmed no seam and a smooth Gaussian-like decay via direct pixel
sampling at multiple x-offsets from the edge.

- [x] **Confirmed live on a real display (2026-07-13).** The design
      history above (v1 → v4) was itself driven by direct feedback on
      real-hardware screenshots at each step, so this was verified
      incrementally rather than in one final pass.
- [ ] **Single-monitor only.** `GlowAuraRenderer.initialize()` sizes the
      overlay to `QGuiApplication.primaryScreen()`'s geometry, not the
      combined virtual geometry of all monitors — on a multi-monitor
      setup the glow will only appear around the primary display. Worth
      fixing once real multi-monitor hardware is available to test
      against — `vision/capture.py`'s `ScreenCapture.list_monitors()`
      may be useful groundwork here.
- [ ] `SEED_BAND_PX`, `BLUR_RADIUS_PX`, `PEAK_ALPHA`, `BREATH_PERIOD_S`,
      `BREATH_MIN`/`MAX`, and `TRANSITION_MS` in `glow_renderer.py` were
      all picked by eye/reasoning, not tuned against a real display — may
      still need adjustment once seen for real.
- [ ] **Blur mask rebuild cost on resize is unmeasured.** `_build_blurred_mask()`
      renders a `QGraphicsScene` through a blur effect at full screen
      resolution; took ~0.3s in this sandbox for 1920×1080 (see commit
      notes), which is fine since it only runs once at startup and on
      resize (which should be rare for a full-screen overlay), but hasn't
      been measured on real target hardware.

- [x] **Fixed: `config/default_config.yaml`'s `vision:` section was stale
      (2026-07-13).** Still had the original ONNX/Xenova captioning fields
      (`encoder_filename`, `decoder_filename`, `tokenizer_filename`,
      `local_model_dir`, `max_new_tokens`) from before the moondream2 →
      MiniCPM-V-2.6 rework (see `docs/DECISIONS.md`). Harmless in practice
      — Pydantic silently falls back to `VisionSettings`' schema defaults
      for anything the yaml doesn't provide — but misleading for anyone
      editing the bundled yaml expecting those fields to do something.
      Replaced with the current GGUF fields (`repo_id`, `model_filename`,
      `mmproj_filename`, `local_model_path`, `local_mmproj_path`, `n_ctx`,
      `n_gpu_layers`, `max_tokens`, `caption_prompt`, `ocr_*`,
      `tesseract_cmd`) plus the new `trigger_keywords`. Verified the merged
      `AppSettings` still matches schema defaults after the change.

## Milestone 7 — Visual Guidance — IN PROGRESS

Design (2026-07-13, refined through direct back-and-forth): instead of a
generic multi-shape overlay layer, the existing full-screen edge Aura
(Milestone 6's `GlowAuraRenderer`) will itself morph to trace the outline
of a single target UI element, then ease back to the full-screen edge.
One box at a time, not a general shape/annotation system. See
`docs/DECISIONS.md` for the full reasoning and the parts breakdown.

- [x] **Part B.1 — Vision model structured output.** `vision/model.py`:
      added `VisionModel.locate(image, target)`, grammar-constrained (via
      `LlamaGrammar.from_json_schema`, `llama-cpp-python`'s built-in
      GBNF-from-JSON-Schema support) to always return
      `{"found": bool, "label": str, "x": int, "y": int, "w": int, "h": int}`
      — `x`/`y`/`w`/`h` as percent of the screenshot (0-100), not pixels
      (see the `LOCATE_JSON_SCHEMA` comment in `vision/model.py` for why).
      `found=False` and a genuine parse failure (`locate()` returning
      `None`) are deliberately treated as equivalent by callers — both
      mean "nothing to point at," not two different error states.
      Covered by 6 real tests in `tests/test_vision_model.py` (grammar
      built from the exact schema, built once and reused across calls,
      well-formed found/not-found responses, unparseable-output and
      missing-required-field failure paths, target substituted into the
      prompt) — all passing, no mocking of the parsing/grammar-building
      logic itself, only the underlying `Llama` instance (same pattern as
      `test_llm_engine.py`).
      **Not yet run against the real model** — this sandbox can't run
      real MiniCPM-V-2.6 inference (no GPU/model weights); needs a
      real-hardware pass to confirm the grammar actually produces valid,
      *semantically* sensible boxes (the grammar guarantees shape, not
      correctness — see the `locate()` docstring).
- [ ] **Part B.2 — Generalize `GlowAuraRenderer` to trace an arbitrary
      rectangle.** Currently only traces the 4 screen edges. Needs a
      `target_rect` concept (screen bounds by default) and a geometry
      morph animation (screen edges → box edges), reusing the existing
      `QVariantAnimation` cross-fade pattern from Milestone 6's color
      transitions.
- [ ] **Part B.3 — Wiring.** `found=True` → new `show_target_box(x, y, w,
      h)` on the aura controller (percent-to-pixel conversion happens
      here, using the known screen-capture geometry). `found=False` /
      parse failure → `AuraState.ERROR` (already red, already wired) +
      a reply asking the user if they want to try again.
- [ ] **Part B.4 — Reverting to full-screen edges.** Two triggers: (1)
      the next query comes in, (2) the cursor dwells inside the target
      box for ~4 seconds (matches the existing breathing-pulse period —
      needs a `QTimer` polling `QCursor.pos()` against the box rect, or
      an event filter).

## Loose ends / small items

- [x] **Fixed: Whisper transcription crashed permanently on real hardware
      with a CUDA/cuBLAS DLL error (2026-07-11).** First real-hardware run
      (Windows, RTX 3070 Ti) showed `Transcriber` loading fine but every
      `.transcribe()` call raising `RuntimeError: Library cublas64_12.dll
      is not found or cannot be loaded` — `device="auto"` detected the GPU
      and picked CUDA, but the actual CUDA/cuBLAS runtime wasn't loadable
      (driver present, redistributables missing or the wrong major
      version). The existing try/except in `voice/service.py` kept this
      from crashing the app, but every wake word afterward would fail
      the same way forever, silently. Fixed in `speech/transcriber.py`:
      `Transcriber.transcribe()` now catches this specific failure shape
      (`_looks_like_cuda_runtime_failure()`, matching on
      cublas/cudnn/cuda/nvcuda in the error message), reloads the model
      on CPU (`device="cpu", compute_type="int8"`), and retries — once,
      permanently, not per-call. Other exceptions are re-raised unchanged
      so unrelated failures still surface normally. Covered by
      `tests/test_transcriber.py` (mocked `WhisperModel`, no real
      download), including the literal error message from the log.
      **Still needs a real-hardware re-run** to confirm the fallback
      actually fires and recovers on the machine that hit this, not just
      in the mocked test.
- [x] **Real LLM generation verified end-to-end on real hardware
      (2026-07-13).** `pip install -e ".[llm]"`, ran `main.py`, asked via
      the debug text input, got a coherent generated response back in the
      response window. Retry-with-backoff logic (added 2026-07-11 for the
      transient SSL handshake timeout) has not needed to fire again since,
      but remains in place. Quality/latency/VRAM usage on the actual RTX
      3070 Ti still hasn't been explicitly measured/reported — see the
      startup-timing item below, which the next session will cover at the
      same time.
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
- [x] **Fixed: two dead test files (2026-07-13).** `tests/test_vision_model.py`
      and `tests/test_ocr.py` both imported free functions
      (`preprocess_image`, `extract_text`) that no longer exist — leftover
      from the ONNX/Xenova → MiniCPM-V-2.6 rework and the later refactor
      of OCR into the `OCRReader` class. Both silently failed collection
      (ImportError) with nothing exercising either module. Rewritten
      against the current APIs (`VisionModel.locate()` for the former,
      `OCRReader.__init__`/`.read()` for the latter) — 6 and 5 real tests
      respectively, all passing. `voice/`, `speech/`, `llm/engine.py`
      (partially, via `test_llm_engine.py`) still need their own coverage
      — see next item.
- [ ] Add `tests/` content — `voice/`, `speech/`, `llm/engine.py`
      (partially covered by `test_llm_engine.py`'s retry logic only),
      and `vision/capture.py` still have zero test coverage and would
      benefit from a proper pytest suite instead of ad-hoc verification
      scripts used during development.
- [x] Add a `LICENSE` file — project is private/proprietary (all rights
      reserved, no third-party use, modification, or redistribution);
      `pyproject.toml`'s `license` field updated from the old placeholder
      "MIT" to "Proprietary" to match.
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

- [x] **Gate vision (MiniCPM-V-2.6) behind relevance, don't run it on
      every query.** Fixed (2026-07-13): `VisionSettings.trigger_keywords`
      (default `screen, see, look, this, here`) added to
      `config/schema.py` / `config/default_config.yaml`. In
      `main.py`'s `_build_prompt_with_screen_context()`, a case-insensitive
      substring check against the transcribed/debug text now runs before
      `screen_capture.capture()` is ever called — no match, no capture, no
      captioning, no OCR. Empty list = old always-on behavior, kept as an
      escape hatch. Chose the keyword heuristic (option (a)) over an
      explicit trigger phrase (option (b)) — see `docs/DECISIONS.md`.
      **Not yet verified on real hardware** — needs a real-mic run to
      confirm keyword-matched queries still trigger vision correctly and
      non-matched queries skip it (and stay fast).
- [ ] **Startup timing still not measured on real hardware.** Flagged
      since Milestone 3/4 — five models now load eagerly at launch (wake
      word, Whisper, LLM, vision, OCR is cheap). Next launch: time from
      process start to window becoming usable, report back before
      deciding whether lazy-loading is worth it.

## Known issues

- None currently open beyond the real-hardware verification gaps noted
  above. See `HANDOFF.md` "Known issues" for details.
