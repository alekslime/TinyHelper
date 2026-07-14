# HANDOFF.md

<<<<<<< HEAD
**Last updated:** 2026-07-15
**Milestones completed:** 1 through 6 ✅. Milestone 7 (Visual Guidance) is
in progress: Parts B.1, B.2, and B.3 are done, B.4 remains. See
`docs/ROADMAP.md` for full milestone history and `docs/TODO.md` for the
part-by-part breakdown.
=======
**Last updated:** 2026-07-14
**Milestones completed:** 1 through 6 ✅ — plus a targeted vision-gating
<<<<<<< HEAD
fix, and Milestone 7 (Visual Guidance) is now in progress: Parts B.1,
B.2, and B.3 done and code-complete; B.3 also has its first real-hardware
confirmation (Session 5, below). B.4 remaining. See `docs/ROADMAP.md` for
full milestone history and `docs/TODO.md` for the part-by-part breakdown.
=======
fix, and Milestone 7 (Visual Guidance) is now in progress: Parts B.1 and
B.2 done, B.3 and B.4 remaining. See `docs/ROADMAP.md` for full milestone
history and `docs/TODO.md` for the part-by-part breakdown.
>>>>>>> e2362707338d13541ed6704fe96c939f88592a87
>>>>>>> 5b2c291bc460334a015110c8d96fb071ae4ebdcd

---

## Summary of work completed since the last HANDOFF.md update

<<<<<<< HEAD
Three sessions since this file was last written:
=======
<<<<<<< HEAD
**Session 3 (2026-07-15) — Part B.3: wiring.** `main.py`'s query flow now
actually calls `VisionModel.locate()` for the first time.

- A new `vision.locate_trigger_keywords` setting (`config/schema.py`,
  `config/default_config.yaml`) gates a separate path from the existing
  `trigger_keywords` (caption/OCR context gate) — see `docs/DECISIONS.md`
  for why these are two independent lists, not one reused list.
- `on_transcribed()` checks `_is_locate_query(text)` first; if matched,
  `_locate_worker()` runs on its own thread and **bypasses normal LLM
  generation entirely** — `locate()`'s structured output already is the
  answer to "where is X," so there's no second real-time inference pass
  through the text LLM. See `docs/DECISIONS.md` if that's ever worth
  revisiting for a more conversational reply.
- `_locate_worker()`: `screen_capture.capture()` →
  `vision_model.locate(image, target=text)` → converts the result's
  percent-of-screenshot coordinates to real screen pixels using the
  *actually captured* monitor's geometry → reports through a new
  `app/locate_bridge.py::LocateResultBridge` (same cross-thread
  `QObject`+`Signal` pattern as the other three `app/*_bridge.py` files).
- `found=True` → `on_target_found()` → `AuraController.show_target_box()`
  + a short reply + `AuraState.IDLE`. `found=False` / parse failure both
  collapse into `on_target_not_found()` → `AuraState.ERROR` + "I couldn't
  find that — want to try again?" — one path, not two, per the Milestone
  7 design decision.
- `vision/capture.py`: `ScreenCapture` gained a `monitor_geometry`
  property — the real geometry of whatever `capture()` last grabbed,
  needed because the percent→pixel conversion must use the region that
  was *actually* captured, not assume it matches Aura's own
  primary-screen-only overlay geometry (documented multi-monitor caveat,
  not solved this session — Part B.2's clamping is the safety net).
- **Verified for real**, with only two boundaries faked (both plainly
  documented as such, not silently glossed over): Llama (no GPU/model
  weights in this sandbox, same as Part B.1) and mss's X11 grab (this
  sandboxed container can't get a real X11/shm connection to Xvfb —
  confirmed by actually trying it first and getting a connection error,
  not assumed). Everything else in the verification is real: real
  `VisionModel.locate()` JSON parsing, the exact percent→pixel conversion
  code copied verbatim from `main.py`, a real `QObject` signal crossing a
  real background thread, and a real `GlowAuraRenderer` ending up tracing
  the exact right rect — for both the found and not-found paths.
- **Found and fixed a real, pre-existing config/code drift bug** while
  double-checking `VisionModel`'s config path: `config/schema.py` /
  `config/default_config.yaml`'s `vision.repo_id` / `model_filename` /
  `mmproj_filename` / `n_ctx` still held moondream2's values from before
  `vision/model.py`'s MiniCPM-V-2.6 rework. This wasn't introduced this
  session, but it's a live bug — `vision/model.py`'s own docstring
  explains pairing the wrong weights with `MiniCPMv26ChatHandler` fails
  *silently* (garbage embeddings, not an error), which is why it was
  fixed immediately rather than just noted. Corrected to match
  `vision/model.py`'s own `DEFAULT_*` constants.

## Files modified (2026-07-15 session)

- `main.py` — the actual Part B.3 wiring (see above).
- `app/locate_bridge.py` — new file, `LocateResultBridge`.
- `vision/capture.py` — `monitor_geometry` property.
- `config/schema.py`, `config/default_config.yaml` —
  `locate_trigger_keywords` (new), plus the moondream2→MiniCPM-V-2.6 drift
  fix (`repo_id`/`model_filename`/`mmproj_filename`/`n_ctx`).
- `docs/TODO.md`, `docs/DECISIONS.md` — Part B.3 marked done with real
  verification details; new decision entries for the LLM-bypass choice,
  the separate keyword list, the geometry-source-of-truth choice, and the
  config drift fix.
- `HANDOFF.md` — this file.

## Known issues / not yet verified

- **Part B.3 has only been verified with two documented sandbox-only
  fakes (Llama, mss's X11 grab)** — never against real hardware, a real
  microphone, or a real vision model. The percent→pixel conversion math
  and the full thread→bridge→Aura path are confirmed correct by direct
  execution; what a real `locate()` call on real screen content actually
  *finds* is not.
- **The multi-monitor geometry mismatch** between `vision.monitor_index`
  (can capture a single monitor or the combined virtual screen) and
  `GlowAuraRenderer`'s primary-screen-only overlay is a known, documented
  gap — not solved this session. On a single-monitor dev/target machine
  it won't matter; worth a real check once multi-monitor is in scope.
- **`locate_trigger_keywords`'s defaults are a first guess**, not tuned
  against real usage — worth revisiting once real voice queries are
  actually being tried against it.
- Everything already listed as open in Part B.1/B.2's entries (real
  MiniCPM-V-2.6 inference never run, `MIN_BOX_SIZE_PX` not tuned against
  a real display, etc.) is still open.
- All previously-open items in `docs/TODO.md`'s "Loose ends" section
  remain open.
=======
Two sessions since this file was last written:
>>>>>>> 5b2c291bc460334a015110c8d96fb071ae4ebdcd

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
<<<<<<< HEAD
  `voice/`/`speech/`/`llm/`/`aura/`, silence-detection tuning, etc.
  `aura/` still has zero committed `pytest` coverage — this session's
  verification was a real, hands-on offscreen script, not a committed
  test file; worth turning into `tests/test_aura_*.py` at some point
  (needs `PySide6` + `pytest-qt` or an offscreen fixture, which the
  existing `tests/` suite doesn't set up yet).
=======
  `voice/`/`speech/`/`llm/`/`aura/`, silence-detection tuning, etc. Note
  `aura/` specifically still has zero `pytest` coverage — Part B.2's
  verification this session was a real, hands-on offscreen script, not a
  committed test file; worth turning into an actual `tests/test_aura_*.py`
  at some point (needs `PySide6` + `pytest-qt` or an offscreen fixture in
  the test environment, which the existing `tests/` suite doesn't set up
  yet). See `docs/TODO.md` directly rather than duplicating that list
  here.
>>>>>>> e2362707338d13541ed6704fe96c939f88592a87
>>>>>>> 5b2c291bc460334a015110c8d96fb071ae4ebdcd

## Current project status

Milestones 1–6 are code-complete and verified on real hardware. Milestone
<<<<<<< HEAD
7 (Visual Guidance): Parts B.1 (vision model structured output), B.2 (a
flashed rectangle target box, `_TargetBoxWidget`), and B.3 (wiring
`main.py`'s query flow to `VisionModel.locate()` and
`AuraController.show_target_box()`) are all code-complete and verified
for real in this sandbox. B.3 has additionally been confirmed once on
real hardware (Windows laptop, Quadro M3000M) — locate → target-box →
response worked correctly end-to-end with real model weights, though
real-hardware vision inference is currently slow (CPU-only) and the
laptop's live config still needs syncing to the newer keyword-gating
design (see "Known issues" and `docs/TODO.md`'s "Loose ends"). Part B.4
(early-dismiss triggers) has not been started.
=======
<<<<<<< HEAD
7 (Visual Guidance): Parts B.1, B.2, and B.3 are code-complete and
verified for real in this sandbox wherever the sandbox allows (real logic
throughout, with only the unavoidable Llama/display boundaries faked and
plainly documented). None of Milestone 7 has run against real hardware
yet. Part B.4 (reverting to the full-screen edge on next-query or
cursor-dwell) has not been started.

## Next milestone

**Milestone 7, Part B.4 — Reverting to full-screen edges.** Two triggers:

1. **The next query comes in.** `on_transcribed()` already runs at the
   start of every query — call `aura.clear_target_box()` there
   unconditionally (before branching into the locate vs. LLM path), so
   any active target box always clears the moment a new query starts,
   regardless of whether the new query is itself a locate query.
2. **The cursor dwells inside the target box for ~4 seconds** (matches
   the existing breathing-pulse period). Needs a `QTimer` polling
   `QCursor.pos()` against the currently-active box rect, or an event
   filter — and needs to track "is a box currently active" and "what is
   its rect" somewhere accessible to that timer, which right now only
   `GlowAuraRenderer`/`_AuraOverlayWidget` know internally. Worth
   deciding whether `AuraController` needs a way to expose "is a target
   box active" (e.g. a property) rather than `main.py` tracking its own
   separate copy of that state.
=======
7 (Visual Guidance): Part B.1 (vision model structured output) and Part
B.2 (renderer generalization) are code-complete and verified for real in
this sandbox (offscreen Qt rendering / mocked `Llama` respectively — see
each part's entry in `docs/TODO.md`), but neither has run against real
hardware/real model weights yet. Part B.3 (wiring `main.py`'s query flow
to `VisionModel.locate()` and `AuraController.show_target_box()`/
`clear_target_box()`) and Part B.4 (reverting to the full-screen edge on
next-query or cursor-dwell) have not been started.
>>>>>>> 5b2c291bc460334a015110c8d96fb071ae4ebdcd

## Next milestone

**Milestone 7, Part B.4 — Early-dismiss triggers.** The box now
disappears on its own after `TARGET_BOX_DURATION_MS`, but should also
clear early via explicit `clear_target_box()` calls on two triggers:
(1) the next query comes in, (2) the cursor dwells inside the box for
~4 seconds (matches the existing breathing-pulse period — needs a
`QTimer` polling `QCursor.pos()` against the box rect, or an event
<<<<<<< HEAD
filter). This is the last piece of Milestone 7's current scope.
=======
filter).
>>>>>>> e2362707338d13541ed6704fe96c939f88592a87
>>>>>>> 5b2c291bc460334a015110c8d96fb071ae4ebdcd

## Ready-to-copy prompt for the next session

```
Continue development of Iris, a fully local AI desktop copilot for Windows.

Before writing any code:
1. Read HANDOFF.md (this file)
2. Read every file inside /docs
3. Understand the current project state

Milestones 1-6 are done and verified on real hardware. Milestone 7
<<<<<<< HEAD
(Visual Guidance) is in progress: Parts B.1 (VisionModel.locate()), B.2
(GlowAuraRenderer's target-box morph), and B.3 (main.py wiring: a
locate-triggered query calls locate() and morphs Aura to the result) are
all code-complete and verified for real in this sandbox -- real logic
throughout, with only the Llama/display boundaries faked (this sandbox
has no GPU/model weights or a working X11 connection to its own Xvfb).
None of it has run against real hardware yet.

Start with Part B.4 -- Reverting to full-screen edges, as scoped in
docs/TODO.md's Milestone 7 section:
  1. Trigger 1 (next query): call aura.clear_target_box() at the start
     of on_transcribed(), unconditionally, before branching into the
     locate vs. LLM generation path.
  2. Trigger 2 (cursor dwell, ~4s): needs a QTimer polling
     QCursor.pos() against the active target box's rect. Decide first
     whether AuraController should expose "is a target box currently
     active, and what's its rect" as its own small piece of state (it
     isn't tracked anywhere outside GlowAuraRenderer/_AuraOverlayWidget
     right now), rather than main.py keeping a separate shadow copy that
     could drift out of sync.
  3. Confirm the whole flow end-to-end as best this sandbox allows (see
     docs/TODO.md and the verify_target_box.py / verify_part_b3.py
     approach from the last two sessions for the offscreen-Qt pattern),
     then flag plainly what still needs a real-hardware pass.

=======
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

>>>>>>> e2362707338d13541ed6704fe96c939f88592a87
Work incrementally, in small parts (not all at once -- confirm progress
with me between parts). Do not begin implementing anything beyond
Milestone 7's scope. Do not write fake/mock-only "it imports" tests --
verify things for real wherever this sandbox allows, and say plainly
<<<<<<< HEAD
when something genuinely can't be. End the session by updating
HANDOFF.md and docs/TODO.md, and only docs/ROADMAP.md /
docs/ARCHITECTURE.md / docs/DECISIONS.md / README.md if something
actually changed.
=======
when something genuinely can't be (e.g. real model weights, a real
display, real hardware). End the session by updating HANDOFF.md and
docs/TODO.md, and only docs/ROADMAP.md / docs/ARCHITECTURE.md /
docs/DECISIONS.md / README.md if something actually changed.
>>>>>>> e2362707338d13541ed6704fe96c939f88592a87
```
