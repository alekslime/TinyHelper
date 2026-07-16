# HANDOFF.md

**Last updated:** 2026-07-16
**Milestones completed:** 1 through 6 ✅, Milestone 7 (Visual Guidance)
code-complete (B.1-B.4), and Milestone 8 (Voice Responses) is now
code-complete as of Session 7 below. B.3 has its first real-hardware
confirmation (Session 5); B.4 and all of Milestone 8 are verified
offscreen/mocked only, still need a real-hardware pass. See
`docs/ROADMAP.md` for full milestone history and `docs/TODO.md` for the
part-by-part breakdown.

**Read this first if you're starting Milestone 9 (or anything else):**
Session 7 (below) is the *third* time in a row this project's zip export
didn't actually contain the previous session's finished work — this time
it was a whole milestone (8), not just one part. The zip Session 7
started from had detailed HANDOFF/DECISIONS-style commentary describing
Milestone 8 as built, tested, and reasoned-about in depth, but not one
line of the actual code existed on disk: no `tts/` package, no
`app/tts_bridge.py`, no `AuraState.SPEAKING`, no `TTSSettings`, no `tts:`
YAML block, no TTS wiring in `main.py`, no test file. Session 7 rebuilt
all of it from scratch, using that stale narrative as a spec (it was
detailed enough to be a very good one) and independently verifying every
piece against the actual files this time — see below. **Before touching
anything in a new session: diff what this file / `docs/TODO.md` claim is
done against what's actually importable/present in the checkout.** If
they disagree, say so plainly and treat the checkout as ground truth.

---

## Summary of work completed since the last HANDOFF.md update

Three sessions since this file was last written:

**Session 1 (2026-07-13) — Part B.1: vision model structured output.**
`VisionModel.locate(image, target)` added to `vision/model.py`:
grammar-constrained (via `LlamaGrammar.from_json_schema`) to always
return `{"found": bool, "label": str, "x": int, "y": int, "w": int,
"h": int}`, coordinates as percent of the screenshot (0-100), not pixels.
`found=False` and a genuine parse failure are treated identically by
design — both mean "nothing to point at." Two pre-existing dead test
files (`tests/test_vision_model.py`, `tests/test_ocr.py`) were also
fixed in passing, with 11 new real tests between them. Full detail in
`docs/TODO.md`'s Milestone 7 section and `docs/DECISIONS.md`.

**Session 2 (2026-07-14) — Part B.2, first pass: morph the ambient glow
into a target box.** Built `show_target_box(x, y, w, h)` /
`clear_target_box()` as a generalization of `GlowAuraRenderer`'s
Milestone 6 ambient glow — `_build_blurred_mask()` took a `target_rect`,
`_AuraOverlayWidget` gained `set_target_rect()`, and a second
`QVariantAnimation` morphed the glow's outline between the full screen
edge and a target box. Verified for real via `QT_QPA_PLATFORM=offscreen`
— real `QApplication` + `GlowAuraRenderer`, real `AuraController` calls,
the real 600ms animation pumped through the Qt event loop, actual painted
mask pixels read back afterward. Along the way, found and fixed two
literal unresolved `git` merge conflict markers baked into the
*committed* `docs/TODO.md` and `docs/DECISIONS.md` from an earlier
session.

**Session 3 (2026-07-14, same day) — Part B.2, simplified: a flashed
rectangle outline instead.** The morphing-glow design from Session 2
worked but was judged disproportionate to what it delivers — replaced
same-day with a much simpler `_TargetBoxWidget`: its own small overlay
that paints one plain rectangle outline and auto-hides itself after
`TARGET_BOX_DURATION_MS` (2.5s) via a single-shot `QTimer`. No animation,
no morph-back state, no coupling to the ambient glow's rendering at all —
`_AuraOverlayWidget`/`_build_blurred_mask()` are back to exactly their
Milestone 6 shape. The `AuraRenderer` interface contract
(`show_target_box`/`clear_target_box`, untrusted-coordinates clamping)
is unchanged; only the implementation underneath it changed. See
`docs/DECISIONS.md` for the full reasoning, including why B.4 changes in
framing (early-dismiss rather than "revert to the full-screen edge") as
a result.

**Note on continuity:** Session 2's work (the morphing-glow version) was
done in a sandbox whose changes weren't present in the project zip this
session started from — Session 3 redid Session 2's code from scratch
against this repo before immediately simplifying it, rather than editing
Session 2's actual files. Functionally the end state is the same as if
Session 2 and 3 had run back-to-back on the same checkout.

**Session 4 (2026-07-14, same day) — Part B.3: wiring `main.py`.**
`main.py`'s `_build_prompt_with_screen_context()` now actually calls
`VisionModel.locate()`, gated behind a new `vision.locate_trigger_keywords`
config field, and routes the result to `AuraController.show_target_box()`
(found) or the existing LLM-failure/`AuraState.ERROR` path (not
found/error) via a new `app/vision_locate_bridge.py` Qt bridge. Full
detail in `docs/TODO.md`'s Milestone 7 section. Verified end-to-end
offscreen with a real `QApplication`/`AuraController` and fake
vision/LLM/screen-capture dependencies; existing test suite unaffected.

**Note on continuity (Session 4):** same situation as the Session 2/3
note above — this session also started from a project zip that predated
the prior session's work (that time, missing the B.3 wiring entirely;
`main.py` still matched the pre-B.3 HANDOFF/TODO description, no
`app/vision_locate_bridge.py` present). Session 4 rebuilt B.3 from
scratch against this checkout — new `VisionSettings.locate_trigger_keywords`
field, new bridge file, and the wired `main.py` — using the just-finished
prior session's own `main.py` as the target end-state rather than
re-deriving the design. Along the way, fixed one bug the prior session's
own verification script had hit and left unresolved: pre-creating a
`QApplication` before calling `main.main()` (which creates its own)
raised `RuntimeError: libshiboken: Please destroy the QApplication
singleton...` — fixed by letting `main.main()` own `QApplication`
construction and fetching `QApplication.instance()` lazily instead.
**If this keeps happening:** whatever's producing these zips isn't
capturing every session's changes before the download link is generated
— worth checking that packaging step, since the growing pattern is a
strong signal something after `main()`'s work (Session 3, and now this
one) isn't landing back in the zip's contents.

**Session 5 (2026-07-14, same day) — first real-hardware run of Part B.3,
on the user's Windows laptop (Quadro M3000M, 4GB VRAM).** Not a code
session at first — the user installed the Session 4 zip fresh
(`pip install -e ".[speech,llm,vision]"`, real Windows/PowerShell,
Python 3.13), ran `python main.py`, and typed `"where's the red
button"` into the debug text box against a real on-screen image.
Confirmed for real: `VisionModel.locate()` (real MiniCPM-V-2.6 inference,
CPU-only) returned `found=True`, `_percent_box_to_pixels()` produced the
correct real screen coordinates, `AuraController.show_target_box()`
fired with no exceptions anywhere in the chain, and the LLM's final
response correctly referenced the located element. This is the first
time any part of Milestone 7 has run against real model weights and a
real display rather than offscreen/mocked.

The box wasn't actually *seen* on that first attempt, though — not a
wiring bug, a timing one. Two real findings from the log:
1. **CPU-only vision inference is slow.** `locate()` alone took ~4
   minutes (8 image slices from MiniCPM-V-2.6's slicing preprocessing,
   ~19-24s per slice to encode+decode) — `llama-cpp-python` almost
   certainly installed without CUDA support (`pip install
   llama-cpp-python` doesn't pull GPU wheels by default), so none of
   that ran on the Quadro despite it being present.
2. **`describe()` (screen captioning) ran a second time, redundantly,
   after `locate()`** — another ~4 minutes — because the laptop's
   pre-existing `config.yaml` (from before this session; e.g. it already
   had `llm.repo_id` pointed at a 3B model, not this repo's 0.5B
   default) hadn't been updated to actually use the
   `trigger_keywords`/`locate_trigger_keywords` split Part B.3 added —
   see `docs/DECISIONS.md` and Part B.3's `docs/TODO.md` entry for the
   design; it only helps once a config's keyword lists are actually set
   up to separate the two triggers.
Combined, one query took roughly 8 minutes end-to-end — comfortably
longer than `TARGET_BOX_DURATION_MS` (2.5s at the time), so the box had
long since auto-hidden by the time the user could look.

Two changes made in response, both requested explicitly by the user
rather than assumed:
- **`TARGET_BOX_DURATION_MS` bumped 2.5s → 8s** in
  `aura/renderer/glow_renderer.py`, as a testing convenience so the
  flash is actually catchable on this hardware's current latency —
  documented in-code as provisional, to be revisited once real GPU
  offload or Part B.4's early-dismiss triggers change what "long enough"
  means.
- **No code change for the double-vision-call issue** — that one's a
  config problem, not a wiring problem. The user needs to sync their
  live `%APPDATA%\Iris\config\config.yaml`'s `vision.trigger_keywords`/
  `locate_trigger_keywords` to the split-keyword design (existing user
  config files only get new *keys* backfilled automatically, not new
  *values* for keys that already exist — see `config/settings.py`), and
  separately consider a CUDA-enabled `llama-cpp-python` reinstall if
  they want real GPU acceleration (4GB VRAM is tight for a 3B LLM +
  MiniCPM-V-2.6 loaded together — likely needs partial `n_gpu_layers`
  tuning rather than `-1`/full offload on both). Both flagged as
  follow-ups in `docs/TODO.md`'s "Loose ends" section, not yet done.

**Session 6 (2026-07-16) — Part B.4: early-dismiss triggers.** Two
triggers now call `clear_target_box()` before `TARGET_BOX_DURATION_MS`
elapses on its own: (1) the next query, wired in `main.py`'s
`on_transcribed()`; (2) a ~4s continuous cursor dwell inside the box, via
a new `_dwell_timer` polling `QCursor.pos()` in
`aura/renderer/glow_renderer.py`'s `_TargetBoxWidget`. Verified offscreen
(real `QApplication`/`GlowAuraRenderer`/`AuraController`, simulated dwell
via monkeypatched `time.monotonic` rather than sleeping real seconds);
existing 15-test suite unaffected. Full detail in `docs/TODO.md`'s
Milestone 7 section and `docs/DECISIONS.md`. Not yet run on real
hardware — this is the user's desktop (RTX 3070 Ti, Ryzen 7 5700X), a
different machine than Session 5's laptop, so it's also the first chance
to confirm the CUDA/GPU-offload follow-ups from Session 5 on hardware
that should actually support them well.

**Session 7 (2026-07-16, same day) — Milestone 8: voice responses,
rebuilt from scratch after the zip lost it (see the warning at the top
of this file).** Full local TTS via Piper: `tts/engine.py`'s `TTSEngine`
(local-path-or-download-CLI voice resolution, WAV synthesis, blocking
playback via `sounddevice`, `stop()`), `app/tts_bridge.py` (worker
thread -> Qt main thread, same shape as `llm_bridge.py`), a new
`AuraState.SPEAKING` (cyan — `GlowAuraRenderer` needed zero changes,
confirming Milestone 6/7's "renderer is generic over state" design held
up), `TTSSettings` in `config/schema.py` + matching `tts:` block in
`config/default_config.yaml` (9 fields, cross-checked to match exactly),
a `tts` extra added to `pyproject.toml` (missing even as a stub — nothing
to reinstate, since none of Milestone 8 had ever actually landed), and
full `main.py` wiring (eager load with graceful degradation, speak after
every LLM response, interrupt-on-new-query, SPEAKING/IDLE Aura
transitions). `tests/test_tts_engine.py` written as real pytest (pytest
itself still isn't installed in this sandbox, same as every prior
session — additionally verified with a standalone mocked-`piper`/
mocked-`sounddevice` script run directly, all 10 checks passing for
real against the actual files, not just asserted). Full reasoning in
`docs/DECISIONS.md`'s Milestone 8 entry (unchanged from what the stale
zip described — the *design* was sound, only the implementation was
missing) and `docs/TODO.md`.

**Session 8 (2026-07-16, same day) — first real-hardware run, one bug
found and fixed.** The user ran Session 7's build on Windows
(RTX 3070 Ti): LLM, vision, OCR, wake word, and Whisper all loaded and
worked correctly first try. TTS voice loading and the `download_voices`
CLI path also worked correctly. `speak()` crashed: `synthesize_wav()`
was being called with `length_scale=`/`noise_scale=`/`noise_w_scale=`
as direct keyword arguments, which the real (offline-guessed) Piper
API doesn't accept — confirmed via a web search against Piper's actual
published Python API docs that it wants a single
`syn_config=SynthesisConfig(...)` object instead. Fixed in
`tts/engine.py`, with a new regression test asserting the call shape
directly. See `docs/DECISIONS.md`'s Milestone 8 entry for the full
account. Synthesis is now confirmed correct only against mocks again
(no network for a second real-hardware round-trip this session) — still
needs one more real run to confirm actual audio output.

## Files modified (Session 7, Milestone 8)

- `tts/__init__.py`, `tts/engine.py` — new package, `TTSEngine`.
- `app/tts_bridge.py` — new, `TTSBridge`.
- `aura/states.py` — `AuraState.SPEAKING` + its `DEFAULT_STATE_COLORS`
  entry added.
- `config/schema.py` — `TTSSettings` added, registered on `AppSettings`.
- `config/default_config.yaml` — matching `tts:` block added.
- `pyproject.toml` — `tts` extra (`piper-tts`, `sounddevice`) added to
  `[project.optional-dependencies]`; `tts*` added to
  `[tool.setuptools.packages.find]`'s `include` list (both were entirely
  absent, not just stale).
- `main.py` — TTS engine construction, `tts_bridge`, `_speak_worker`,
  interrupt-on-new-query in `on_transcribed`, speak dispatch in
  `on_llm_response`, `on_tts_finished`/`on_tts_failed` handlers, signal
  connections, shutdown `tts_engine.stop()`.
- `tests/test_tts_engine.py` — new, 10 real tests against mocked
  `piper`/`sounddevice`.
- `docs/ROADMAP.md`, `docs/TODO.md`, `HANDOFF.md` — this file.

## Files modified (2026-07-14 sessions)

- `aura/renderer/glow_renderer.py` — the actual Part B.2 work: new
  `_TargetBoxWidget` (flash + auto-hide), `GlowAuraRenderer` updated to
  own and drive it, `_AuraOverlayWidget`/`_build_blurred_mask()` reverted
  to Milestone 6's original (no `target_rect` awareness).
- `aura/renderer/base.py` — `show_target_box`/`clear_target_box`
  docstrings updated to describe a flash, not a morph.
- `aura/controller.py` — matching docstring updates.
- `docs/TODO.md`, `docs/DECISIONS.md` — Part B.2 entries rewritten to
  describe the flash-based design and the reasoning for the revision;
  conflict markers from an earlier session removed.
- `HANDOFF.md` — this file.

## Files modified (Session 4, Part B.3)

- `main.py` — `_percent_box_to_pixels()` helper added at module level;
  monitor geometry resolved once at startup; `VisionLocateBridge`
  instantiated and connected; `_build_prompt_with_screen_context()` calls
  `VisionModel.locate()` behind `locate_trigger_keywords` gating and
  returns `None` on not-found/error to abort the query; `_generate_worker`
  returns early on that `None`; new `on_target_box_found` main-thread
  handler.
- `app/vision_locate_bridge.py` — new file, `VisionLocateBridge` (worker
  thread → Qt main thread for found-box coordinates), same pattern as the
  other `app/*_bridge.py` files.
- `config/schema.py` — `VisionSettings.locate_trigger_keywords` field
  added (default `where, find, point, show me, locate`).
- `config/default_config.yaml` — matching default added alongside the
  existing `trigger_keywords` line.
- `docs/TODO.md` — Part B.3 entry marked done with the verification
  summary.
- `HANDOFF.md` — this file.

## Files modified (Session 5, real-hardware run)

- `aura/renderer/glow_renderer.py` — `TARGET_BOX_DURATION_MS` 2.5s → 8s
  (testing convenience, see Session 5 summary above).
- `docs/TODO.md` — Part B.3 marked confirmed on real hardware; new
  "Loose ends" entry for the CPU-only-vision / redundant-caption
  findings and their follow-ups.
- `HANDOFF.md` — this file.

## Files modified (Session 6, Part B.4)

- `main.py` — `on_transcribed()` calls `aura.clear_target_box()` as its
  first line (next-query dismiss trigger).
- `aura/renderer/glow_renderer.py` — new `DWELL_DISMISS_MS` /
  `DWELL_POLL_INTERVAL_MS` constants; `_TargetBoxWidget` gained
  `_dwell_start`/`_dwell_timer`, `_check_dwell()`, and
  `_on_auto_hide_timeout()`; `flash()`/`stop()` updated to manage the new
  timer alongside the existing auto-hide one.
- `docs/TODO.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md` — Part B.4
  marked done with reasoning and verification summary; Milestone 7
  marked code-complete.
- `HANDOFF.md` — this file.

## Important implementation details

- **`_TargetBoxWidget` is fully independent of `_AuraOverlayWidget`.**
  It doesn't know about `AuraState`, hue, or the ambient glow's blur
  pipeline — it just paints a rect in a given color and disappears on a
  timer. `GlowAuraRenderer` sizes it to the same screen geometry as the
  main overlay in `initialize()` and translates screen-absolute
  coordinates to the widget's local space before calling `flash()`.
- **Clamping still lives in the renderer, not the caller.**
  `_clamp_target_rect()` is unchanged in spirit from the original Part
  B.2 — still enforces on-screen bounds and a minimum size
  (`MIN_BOX_SIZE_PX`, now 40px, no longer tied to the glow's seed-band
  width). Part B.3's `main.py` wiring will call `show_target_box()` with
  whatever `VisionModel.locate()` returns (converted from percent to
  pixels) and trust the renderer to keep it sane.
- **`TARGET_BOX_DURATION_MS` (2.5s) is not yet tuned against a real
  display** — a first guess, not measured. Worth a look once Part B.3 is
  wired up and boxes are coming from real vision-model output.

## Known issues / not yet verified

- **The flashed target box has only been verified offscreen**
  (`QT_QPA_PLATFORM=offscreen`) — grabbed the widget's real painted
  pixels and confirmed an outline-only stroke (opaque edge, transparent
  interior), confirmed `clear_target_box()` hides immediately, confirmed
  the auto-hide timer runs, confirmed both the out-of-bounds and
  minimum-size clamps. A real-monitor pass (does 2.5s/40px/3px stroke
  actually read well) hasn't happened.
- **Vision gating (Milestone 6.5 fix) still hasn't been verified on real
  hardware either** — carried over from before Part B.1, still open.
- **Part B.3 has now been confirmed on real hardware once** (Session 5,
  Windows laptop, Quadro M3000M) — the locate → target-box → response
  chain ran correctly end-to-end with real model weights. Still only
  one data point, only via the debug-text path (not real voice input),
  and only for a "found" case — the not-found path hasn't been exercised
  against real vision-model output yet, only offscreen with a fake one.
- **Real-hardware vision inference is currently very slow (CPU-only) and
  the vision-gating keyword split isn't yet applied on the test
  laptop's live config** — see `docs/TODO.md`'s "Loose ends" section for
  the full finding and the two follow-ups (CUDA-enabled
  `llama-cpp-python`, syncing `%APPDATA%\Iris\config\config.yaml`'s
  trigger-keyword lists). Neither started.
- **Minor UX nit in Part B.3's not-found path:** the retry message
  reaches the window pre-wrapped as `"(LLM error — see logs: ...)"`
  (it reuses the existing `LLMResponseBridge.report_failure()` →
  `on_llm_failed` path, per B.3's scoping to reuse the existing
  `AuraState.ERROR` path rather than add a new one) even though nothing
  about a `locate()` miss is actually an LLM error. Not a bug — right
  text, right state — just confusing framing. Worth a dedicated
  `on_locate_failed` handler if this bothers real usage.
- All previously-open items in `docs/TODO.md`'s "Loose ends" section
  remain open — startup timing, `tests/` coverage for
  `voice/`/`speech/`/`llm/`/`aura/`, silence-detection tuning, etc.
  `aura/` still has zero committed `pytest` coverage — this session's
  verification was a real, hands-on offscreen script, not a committed
  test file; worth turning into `tests/test_aura_*.py` at some point
  (needs `PySide6` + `pytest-qt` or an offscreen fixture, which the
  existing `tests/` suite doesn't set up yet).

## Current project status

Milestones 1–6 are code-complete and verified on real hardware. Milestone
7 (Visual Guidance) is now code-complete: Parts B.1 (vision model
structured output), B.2 (a flashed rectangle target box,
`_TargetBoxWidget`), B.3 (wiring `main.py`'s query flow to
`VisionModel.locate()` and `AuraController.show_target_box()`), and B.4
(early-dismiss triggers — next query, ~4s cursor dwell) are all
code-complete and verified offscreen in this sandbox. B.3 has additionally
been confirmed once on real hardware (Windows laptop, Quadro M3000M) —
locate → target-box → response worked correctly end-to-end with real
model weights, though real-hardware vision inference is currently slow
(CPU-only) and that laptop's live config still needs syncing to the
keyword-gating design (see "Known issues" and `docs/TODO.md`'s "Loose
ends"). B.4 has not yet been run on real hardware at all.

## Next milestone

Milestone 7's current scope is done. Two things are worth doing before
picking up Milestone 8 (Voice Responses):

1. **Real-hardware pass on Part B.4** — confirm the cursor-dwell dismiss
   feels right (is 4s too long/short?) and that click-through still holds
   with the new polling timer running, on a real display and a real
   mouse.
2. **The Session 5 performance follow-ups**, still open and now testable
   on different, stronger hardware (RTX 3070 Ti, Ryzen 7 5700X, per the
   user) than the laptop that surfaced them: a CUDA-enabled
   `llama-cpp-python` reinstall for real GPU offload, and syncing
   `vision.trigger_keywords`/`locate_trigger_keywords` in this machine's
   own `config.yaml` so `locate()` and `describe()` don't both run on a
   single "where's X" query. See `docs/TODO.md`'s "Loose ends" section
   for the full detail.

Once those are confirmed (or at least attempted) on real hardware,
Milestone 8 — Voice Responses (local TTS output) is next per
`docs/ROADMAP.md`.

## Ready-to-copy prompt for the next session

```
Continue development of Iris, a fully local AI desktop copilot for Windows.

Before writing any code:
1. Read HANDOFF.md (this file)
2. Read every file inside /docs
3. Understand the current project state

Milestones 1-6 are done and verified on real hardware. Milestone 7
(Visual Guidance) is in progress: Part B.1 (vision model structured
output, VisionModel.locate()), Part B.2 (a flashed rectangle outline via
_TargetBoxWidget, auto-hides after TARGET_BOX_DURATION_MS, now 8s), and
Part B.3 (wiring main.py's query flow to VisionModel.locate() and
AuraController.show_target_box(), via app/vision_locate_bridge.py and
VisionSettings.locate_trigger_keywords gating) are all code-complete and
verified for real in this sandbox. B.3 has also been confirmed once on
real hardware (Windows laptop, Quadro M3000M, 4GB VRAM) -- locate ->
target-box -> response worked correctly end-to-end, though real-hardware
vision inference is currently slow (CPU-only, no CUDA wheels) and the
test laptop's live config still needs syncing to the trigger-keyword
split. See HANDOFF.md's Session 5 notes and docs/TODO.md's "Loose ends"
section for full detail.

Start with Part B.4 -- Early-dismiss triggers, as scoped in
docs/TODO.md's Milestone 7 section:
  1. clear_target_box() should fire when the next query comes in (i.e.
     a new on_transcribed/debug-text-submitted call arrives while a box
     is still showing), not just after TARGET_BOX_DURATION_MS elapses.
  2. clear_target_box() should also fire after the cursor dwells inside
     the box for ~4 seconds (matches the existing breathing-pulse
     period) -- needs a QTimer polling QCursor.pos() against the box
     rect, or a Qt event filter; your call on the approach, but explain
     the tradeoff you picked in docs/DECISIONS.md.
  3. Confirm end-to-end as best this sandbox allows (offscreen Qt, same
     approach as B.2/B.3), then flag plainly what still needs a
     real-hardware pass.

Optional, only if time allows and it doesn't distract from B.4 -- two
follow-ups from the Session 5 real-hardware run, neither started:
  - The not-found path (Part B.3) still hasn't been exercised against
    real vision-model output on real hardware, only the found path has.
  - A dedicated on_locate_failed handler (see HANDOFF.md "Known issues")
    for cleaner not-found-message framing than reusing on_llm_failed's
    "(LLM error -- see logs: ...)" wrapping.

IMPORTANT -- read this before touching anything: the last two sessions
in a row started from a project zip that didn't contain the prior
session's own finished work (Session 3 was missing Session 2's
morphing-glow code entirely; Session 4 was missing Session 3's finished
B.3 wiring entirely). Before writing any code this session: diff what
HANDOFF.md/docs/TODO.md claim is done against what's actually in the
files on disk (main.py, app/, aura/renderer/glow_renderer.py,
config/schema.py). If Part B.3's wiring isn't actually present, say so
plainly and redo it before starting B.4 -- don't build early-dismiss
triggers on top of wiring that doesn't exist in this checkout. If it IS
present, proceed straight to B.4.

Work incrementally, in small parts (not all at once -- confirm progress
with me between parts). Do not begin implementing anything beyond
Milestone 7's scope. Do not write fake/mock-only "it imports" tests --
verify things for real wherever this sandbox allows, and say plainly
when something genuinely can't be (e.g. real model weights, a real
display, real hardware). End the session by updating HANDOFF.md and
docs/TODO.md, and only docs/ROADMAP.md / docs/ARCHITECTURE.md /
docs/DECISIONS.md / README.md if something actually changed.
```
