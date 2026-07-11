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
5. **v4 — real Gaussian blur (current).** User asked for an entirely
   different technique, not another parameter tweak. Replaced the
   hand-authored gradient-stack approach with an actual Gaussian blur:
   paint a solid-color band (`SEED_BAND_PX` = 55px) along each edge, blur
   it with `QGraphicsBlurEffect` (`BLUR_RADIUS_PX` = 90), cache the
   result as a `QImage` (rebuilt only on resize), and re-tint that cached
   shape to the current color/breath-brightness each frame (cheap —
   `QPainter.CompositionMode_SourceIn`). This gives a genuine bell-curve
   falloff with zero seams at corners (blur handles that for free)
   instead of a manually tuned decay curve. Breathing pulse carried over
   unchanged from v3.

**Verification so far:** all of the above verified offscreen only —
rendered each `AuraState`, pixel-sampled the falloff curve, and (for v4)
confirmed no seam and a smooth Gaussian-like decay via direct pixel
sampling at multiple x-offsets from the edge.

- [ ] **Never confirmed live on a real display.** Every version above,
      including the current Gaussian-blur one, has only been verified via
      offscreen rendering (`QT_QPA_PLATFORM=offscreen`) and pixel
      sampling — click-through behavior, always-on-top stacking, and how
      the blur actually reads over real desktop content and at real
      viewing distance are all unverified. Next session on real hardware
      should: run `main.py`, confirm the blurred glow appears around all
      four edges, trigger a few state changes to see the cross-fade and
      breathing live, and confirm click-through still works (nothing
      about the paint pipeline changed there, but worth re-checking).
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
