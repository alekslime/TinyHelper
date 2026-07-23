# HANDOFF.md

**Last updated:** 2026-07-23 (Session 11)
**Milestones completed:** 1 through 6 ✅, Milestone 7 (Visual Guidance)
code-complete (B.1-B.4), Milestone 8 (Voice Responses) confirmed on real
hardware (Session 8), Milestone 9 (Conversation Memory, both Part A and
Part B) done and confirmed on real hardware as of Session 9, and
Milestone 10 (reframed as the Dynamic Island, replacing the original
"generic settings screen" plan — see `docs/DECISIONS.md`) now has Parts
A and B code-complete (Session 10 / Session 11 below), with **Part B not
yet confirmed on any real hardware** (see next paragraph — this
session's sandbox couldn't even import PySide6). Parts C-D still open.
B.3/B.4 (Milestone 7) still only have partial or no real-hardware
confirmation — see `docs/ROADMAP.md` for full milestone history and
`docs/TODO.md` for the part-by-part breakdown.

**Read this before starting a new session — Session 11's sandbox had no
PySide6, no Windows, and no network at all.** Unlike Session 10 (which
had a working offscreen PySide6 install and visually verified Part A's
rendering), this session's container couldn't `pip install PySide6`
(no network egress) or import it from a prior install (not present), and
obviously isn't Windows either. Everything below was written carefully
and reasoned through against the real Win32 API contract, and the pure
hotkey-string-parsing logic (`app/hotkey.py:parse_hotkey`) *was* unit
tested in isolation (by stubbing `PySide6.QtCore` with plain classes) —
but **the actual `QAbstractNativeEventFilter`/`RegisterHotKey`/
`WM_HOTKEY` wiring has had zero real verification**: not offscreen, not
on real hardware, not even a successful import of the real module. Full
real-hardware verification (see "Next session" below) is not optional
polish here, it's the first time this code will run at all.

**Read this before starting a new session:** Milestone 10's scope
changed mid-stream (Session 10) from "generic settings screen wrapping
`config/`" to a Dynamic-Island-style floating pill overlay, with
settings access moving inside the island rather than being its own
screen — see `docs/DECISIONS.md`'s Milestone 10 entry for the full
reasoning before continuing this milestone.

**Read this before starting a new session:** Session 9 hit a real
"the zip didn't land" problem again, but on the user's end this time —
their first real-hardware test of Part B produced a result that looked
exactly like a bug (follow-up questions got a generic "I don't have
access to that information") until `Select-String 'history=history'
main.py` on their machine came back empty, confirming they were still
running the old pre-Part-B `main.py`. **If a real-hardware test result
looks wrong, grep for a distinguishing string from the new code on the
machine that ran it before debugging further.**

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

**Session 11 (2026-07-23) — Milestone 10, Part B: activation triggers.**
Diffed HANDOFF.md/`docs/` against the actual checkout first, per the
standing instruction above — everything Session 10 claimed (Part A done,
not wired into `main.py`) matched what was actually on disk. Added:
- `app/hotkey.py` — `GlobalHotkeyFilter`, a `QAbstractNativeEventFilter`
  that registers a system-wide hotkey via raw Win32 `RegisterHotKey`
  (through `ctypes`, no new dependency) and emits `activated` on
  `WM_HOTKEY`. Windows-only; no-ops (logs and continues) on any other
  platform or if registration fails. Also `parse_hotkey()`, turning a
  `"ctrl+shift+space"`-style string into `(modifiers, vk)`.
- `config/schema.py` / `config/default_config.yaml` — new
  `IslandSettings` (`enabled`, `hotkey`, `expand_on_wake_word`).
- `main.py` — constructs the island widget (always, mirroring how `aura`
  is always constructed), registers the hotkey and connects it to
  `island.toggle()`, connects wake-word detection to `island.expand()`,
  and collapses the island at every existing turn-end point
  (`on_tts_finished`, `on_tts_failed`, `on_llm_failed`,
  `on_no_speech_detected`, and the two no-TTS/no-LLM early-exit
  branches) — same set of places Aura already returns to IDLE/ERROR.
  Unregisters the hotkey on shutdown.

**Verification is much weaker than usual this session — flagging this
clearly rather than letting it blend in with confirmed work.** This
sandbox had no PySide6 (and no network to install it) and isn't Windows,
so none of the Qt/Win32 wiring above has ever actually run. What *was*
verified: `python -m py_compile` on all three edited/new files, and
`parse_hotkey()`'s pure string-parsing logic unit-tested in isolation
(correct modifiers/vk for four hotkey strings, correct `ValueError` for
four malformed ones — see transcript) by stubbing `PySide6.QtCore` with
plain classes so the module would import at all. Everything else —
whether `RegisterHotKey`/`nativeEventFilter` actually works, whether the
island really expands/collapses on a real screen, whether the hotkey
conflicts with anything else bound to `Ctrl+Shift+Space` on the test
machine — needs a real Windows run before this can be called done, not
just code-complete. Treat this Part B like Milestone 7's B.3/B.4 before
their real-hardware pass: plausible, reasoned-through, unconfirmed.

**Design decisions made without the user in the loop, worth a second
look:** the exact "when does the island auto-collapse" behavior (every
existing turn-end point, chosen because it's where Aura already resets
to IDLE/ERROR) and the default hotkey (`ctrl+shift+space`, chosen only
because it seemed unlikely to collide with common app shortcuts — not
verified against anything on the actual test machine).

**Same-session follow-up (still 2026-07-23):** after confirming the
hotkey pops the island up on real hardware, the user asked for a real
text box inside it — "let it be the debug screen." Added:
- `app/dynamic_island.py` — a debug-only `QLineEdit` (constructor gains
  `debug_enabled: bool`), positioned inside the expanded panel, shown/
  focused only once fully expanded (hidden during the collapse/expand
  animation and while collapsed, so it never overflows the small pill).
  New `text_submitted` signal, same contract as
  `app/main_window.py:debug_text_submitted`. Explicitly calls
  `activateWindow()`/`setFocus()` on expand so a hotkey/wake-word pop-up
  is immediately typeable without an extra click.
- `main.py` — passes `debug_enabled=settings.debug.enabled` into the
  island's constructor and connects `island.text_submitted` to the exact
  same `on_debug_text_submitted` handler `MainWindow`'s debug input
  already used — one handler, two input surfaces now.

This is still unverified on real hardware (same PySide6/Windows gap as
the hotkey work above) — the geometry math and signal wiring were
reasoned through carefully but not run. Specifically worth checking
next real-hardware pass: does `activateWindow()` actually steal focus
from whatever app the user was in when the wake word (not the hotkey)
triggered the expand — that's arguably fine for a hotkey-driven "I want
to type now" moment, less obviously fine for a voice-driven expand where
the user wasn't necessarily reaching for a keyboard at all.

**Real-hardware confirmation, same session:** the user then actually ran
this on their machine — hotkey, island expand/collapse, and the new
debug text box all confirmed working end-to-end (typed "hi", got a real
LLM response, spoke via TTS, island collapsed on turn end). **This is
the first real-hardware confirmation of any of Milestone 10's activation
work** — update the "Milestones completed" line above accordingly next
time this file's summary is rewritten wholesale.

**Real-hardware crash found during that same test, fixed same session:**
submitting the same vision query twice within the vision model's
multi-second inference window caused two worker threads to call into
the same non-thread-safe llama.cpp context, crashing the whole process
(`GGML_ASSERT(out_ids.size() == n_outputs)`). Added a reentrancy guard
(`current_turn["active"]`) that refuses a new wake word/debug submission
while a previous turn's generation is still in flight — see
`docs/DECISIONS.md`'s 2026-07-23 entry for the full reasoning,
including why the guard is scoped to generation only (not the whole
turn through TTS playback, which would have regressed the existing
barge-in-during-speech behavior). **Not yet re-tested on real
hardware** — same sandbox gap as everything else this session. Worth a
clean single-query pass first, then deliberately trying to trigger the
old race again (submit a second query while the first is still
captioning) to confirm it's now refused with a log warning instead of
crashing.

**Session 10 (2026-07-16, same day) — Milestone 10 reframed, Part A:
static Dynamic Island widget.** The user redirected this milestone
before any settings-screen code was written: instead of a generic
settings UI, Iris gets a Dynamic-Island-style floating pill overlay,
with settings access moving inside it (a later part) rather than being
its own screen. Before writing anything, diffed HANDOFF.md/`docs/`
against the actual checkout (per the standing instruction above) —
everything Session 9 claimed (`ConversationStore`, history wired into
`main.py` and `LLMEngine.generate()`) was genuinely present this time,
no repeat of the earlier zip-didn't-land problem. Also read
`aura/controller.py`, `aura/renderer/base.py`, and
`aura/renderer/glow_renderer.py` before deciding where the island should
live — see `docs/DECISIONS.md` for why it became a new, independent
module (`app/dynamic_island.py`) rather than another `AuraRenderer`.

Built `DynamicIslandWidget`: frameless/translucent/always-on-top,
anchored bottom-center of the primary screen, with `IslandState.COLLAPSED`
(small pill) and `IslandState.EXPANDED` (larger panel with placeholder
title/status text and a decorative settings glyph) states, an animated
geometry transition between them, near-black (`#1A1A1A`-equivalent)
color per the user's explicit call, and a gradient+rim treatment
approximating a frosted-glass look (real backdrop blur not attempted —
platform-specific, real-hardware-only). This sandbox turned out to have
a working `PySide6` install under `QT_QPA_PLATFORM=offscreen` this time
(confirmed fresh rather than assumed) — used it to grab and inspect the
widget's actual painted pixels for both states rather than relying on
code review alone, and visually reviewed the composited renders before
tuning the glass effect to be more visible per the user's feedback. Full
verification detail in `docs/DECISIONS.md`.

Scoped as Part A only, per the user's explicit choice to confirm before
each part rather than build B-D in the same pass. Nothing wired into
`main.py` yet — no hotkey, no wake-word hookup, no working settings
button, `app/main_window.py` untouched. `docs/ROADMAP.md`'s Milestone 10
entry rewritten to reflect the new direction.

Three sessions since this file was last written (prior to Session 10):

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

**Session 9 (2026-07-16, same day) — Milestone 9, Part A: SQLite-backed
conversation history.** Scoped explicitly to storage only — Part B
(retrieval for follow-up context) was not started this session. New
`memory/store.py` (`ConversationStore`: `save_turn()`,
`get_recent_turns()`, `count_turns()`), `MemorySettings` in
`config/schema.py` (`enabled`, `db_path`) + matching `memory:` block in
`config/default_config.yaml`, wired into `main.py`'s `_generate_worker`
— a turn is saved right after a successful LLM response, before it's
reported back via `llm_bridge`. No optional-extra dependency
(`sqlite3` is stdlib), so no `_MEMORY_AVAILABLE`-style defensive import
like `llm`/`vision`/`tts` have; the only realistic failure is a bad
`db_path`, which raises a clear `RuntimeError` that `main.py` catches
the same way it catches the other engines' construction failures.
`tests/test_memory_store.py` — 9 tests, run for real against actual
`sqlite3` (nothing to mock, unlike `tts`/`llm`/`vision`) — caught and
fixed one real bug (`ConversationStore.__init__`'s `mkdir` call raised
an uncaught `FileExistsError` instead of the intended `RuntimeError`
when its parent path collided with an existing file; fixed by moving
`mkdir` inside the same `try`/`except` as the DB connect). This
session's sandbox could also install `pytest` for the first time (prior
sessions couldn't — no network), so these ran as real `pytest`, not a
standalone mocked script. **Confirmed on real hardware the same
session** (Windows, RTX 3070 Ti): the user ran three real queries,
`%APPDATA%\Iris\data\conversations.db` was created, and
`ConversationStore.get_recent_turns()` read back all 3 turns with
correct content and correct newest-first order. `main.py`'s wiring
itself was only verified by `py_compile` + code review in this sandbox
(`PySide6` isn't installed here) before the user's real-hardware run
confirmed it actually works end-to-end. Full reasoning in
`docs/DECISIONS.md`'s Milestone 9 Part A entry.

**Session 9 continued, same day — Milestone 9, Part B: retrieval for
follow-up context.** Originally scoped as a separate future session, but
the user asked to continue straight into it after Part A was confirmed.
`LLMEngine.generate()` (`llm/engine.py`) now accepts an optional
`history: list[tuple[str, str]] | None` parameter, inserted as
alternating user/assistant chat messages between the system prompt and
the current turn — a real change to the chat-completion `messages` list,
not string concatenation into the prompt. `MemorySettings.context_turns`
(default 5, config-driven) added. `main.py`'s `_generate_worker` fetches
that many recent turns from `ConversationStore.get_recent_turns()`
before each generation call, reverses them to chronological order, and
passes them through. 4 new tests in `tests/test_llm_engine.py` (same
faked-`llama_cpp` pattern the file already used) assert the *exact*
`messages` list sent to the model for no-history, with-history,
empty-text, and `history=None` cases — all 45 tests in the suite passed.

**Real-hardware confirmation hit a real deployment snag first.** The
user's first Part B test looked like a bug: "my name is Aleks" then
"what's my name?" got a generic "I don't have access to that
information," twice. Checked directly rather than debugging blind:
`Select-String 'context_turns'` against the live
`%APPDATA%\Iris\config\config.yaml` came back empty (should have been
backfilled), and `Select-String 'history=history' main.py` in the
folder the user was running from *also* came back empty — confirming
the zip's Part B code had never actually landed in
`C:\Users\aleks\TinyHelper`; the user was still running the old
Part-A-only build. Same "the zip didn't land" failure mode documented
in earlier sessions, this time on the delivery side rather than a fresh
sandbox checkout. After the user re-extracted and confirmed the grep
found a match, the real test passed: "hi. my name is Aleks" → "Hi Aleks,
how can I assist you today?", then "wait. whats my name?" → "Your name
is Aleks." — confirmed by reading `conversations.db` directly, not just
trusting the on-screen reply. Full reasoning, including the
no-token-budget-accounting caveat on `context_turns`, in
`docs/DECISIONS.md`'s Milestone 9 Part B entry.

## Files modified (Session 11, Milestone 10 Part B)

- `app/hotkey.py` (new) — `GlobalHotkeyFilter`, `parse_hotkey()`, Win32
  constants. Windows-only functional; safe no-op import/construction on
  any other platform.
- `app/dynamic_island.py` — added the debug-only embedded `QLineEdit`
  (`text_submitted` signal, `debug_enabled` constructor param,
  show/focus/position logic tied to the expand animation).
- `config/schema.py` — new `IslandSettings`, registered on `AppSettings`
  as `island`.
- `config/default_config.yaml` — matching `island:` block.
- `main.py` — constructs `DynamicIslandWidget`, registers the hotkey via
  `GlobalHotkeyFilter` + `app.installNativeEventFilter`, wires
  `island.expand()` into `on_wake_word_detected`, wires
  `island.collapse()` into every existing turn-end callback, connects
  `island.text_submitted` to the same handler as the `MainWindow` debug
  input, unregisters the hotkey at shutdown. Also (same-session
  follow-up, after a real crash): `on_wake_word_detected` now returns
  `bool` and refuses a new turn while `current_turn["active"]` is set;
  that flag is set before spawning `_generate_worker`'s thread and
  cleared in `on_llm_response`/`on_llm_failed`. See
  `docs/DECISIONS.md`'s 2026-07-23 entry.
- `HANDOFF.md` (this file) — this entry.

**NOT touched this session, still exactly as Session 10 left them:**
`app/dynamic_island.py` (Part A's widget itself — no changes needed),
Part C (settings surface inside the expanded island — the decorative
gear glyph in `_paint_expanded_content` is still non-interactive), Part
D (retiring `app/main_window.py` — `MainWindow` is still constructed and
shown in `main.py` exactly as before, alongside the island now).

## Files modified (Session 10, Milestone 10 Part A)

- `app/dynamic_island.py` — new file, `DynamicIslandWidget` and
  `IslandState`. Static shape/color/positioning only; no wiring into
  `main.py`.
- `docs/ROADMAP.md` — Milestone 10 rewritten from "generic settings
  screen" to the Dynamic Island direction; Part A marked done.
- `docs/TODO.md` — new Milestone 10 section with Part A's verification
  summary; Parts B-D listed as open.
- `docs/DECISIONS.md` — new entry: why a new module instead of an
  `AuraRenderer`, why `app/` instead of a new `ui/` package, the color
  and frosted-glass choices, and the verification approach/limits.
- `HANDOFF.md` — this file.

## Files modified (Session 9, Milestone 9 — Parts A and B)

- `memory/store.py` — new, `ConversationStore` (`save_turn`,
  `get_recent_turns`, `count_turns`).
- `config/schema.py` — `MemorySettings` added (`enabled`, `db_path`,
  `context_turns`), registered on `AppSettings`.
- `config/default_config.yaml` — matching `memory:` block added.
- `llm/engine.py` — `LLMEngine.generate()` gained an optional `history`
  parameter, inserted as alternating user/assistant chat messages;
  class docstring updated.
- `main.py` — `ConversationStore` construction (graceful-degradation
  pattern), `save_turn()` call in `_generate_worker` after a successful
  response, history fetch + reversal + pass-through before
  `llm_engine.generate()`, module docstring's numbered list updated.
- `tests/test_memory_store.py` — new, 9 real tests against actual
  `sqlite3`.
- `tests/test_llm_engine.py` — 4 new tests asserting `generate()`'s
  exact chat-message assembly with/without history.
- `docs/ROADMAP.md`, `docs/TODO.md`, `docs/DECISIONS.md`, `HANDOFF.md`
  — this file.

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
- **Dynamic Island Part A (`app/dynamic_island.py`) has only been
  verified offscreen** — real painted pixels for both states, screen
  anchoring math, transparent corners, near-black center, visual review
  at 2x/3x zoom. Not verified: real transparency/compositing over actual
  desktop content, real-monitor DPI scaling, whether `Qt.WindowType.Tool`
  keeps it off the taskbar/alt-tab on real Windows the same way it does
  for the Aura overlay, and whether the faked frosted-glass gradient/rim
  actually reads as intended over real content (vs. the synthetic
  background used for review here).

## Current project status

Milestones 1–6 are code-complete and verified on real hardware. Milestone
7 (Visual Guidance) is code-complete: Parts B.1-B.4 are all done and
verified offscreen; B.3 has been confirmed once on real hardware
(Windows laptop, Quadro M3000M) — locate → target-box → response worked
correctly end-to-end, though that laptop's live config still needs
syncing to the keyword-gating design (see `docs/TODO.md`'s "Loose
ends"). B.4 has still not been run on real hardware at all. Milestone 8
(Voice Responses) is confirmed on real hardware (Session 8, Windows RTX
3070 Ti) — LLM, vision, OCR, wake word, Whisper, and TTS all load and
run correctly, real audio plays. **Milestone 9 (Conversation Memory,
both Part A and Part B) is done and confirmed on real hardware as of
Session 9** — turns are persisted, and follow-up questions ("what's my
name?" after "my name is Aleks") are correctly answered using that
history. **Milestone 10 has been reframed** (Session 10) from a generic
settings screen to a Dynamic Island floating pill overlay, with Part A
(the static widget, `app/dynamic_island.py`) done and verified offscreen
— see `docs/DECISIONS.md` for the reasoning behind the redirect. Parts
B (activation triggers), C (settings surface), and D (retire
`app/main_window.py`) are still open, plus leftover real-hardware
confirmation gaps from Milestone 7 (B.4, and the Session 5 performance
follow-ups), per `docs/ROADMAP.md`.

## Next milestone

The user confirmed a part-by-part approach for Milestone 10 — the
natural next step is:

1. **Milestone 10, Part B — activation triggers.** Wire a global
   keyboard shortcut (needs a Windows global-hotkey mechanism —
   `pywin32`'s `RegisterHotKey`, or the `keyboard` package — since Qt's
   own `QShortcut` only fires when Iris has focus) and hook the existing
   voice wake word path (`main.py`'s `on_wake_word_detected`) so either
   trigger calls `DynamicIslandWidget.expand()`. Decide and document
   what collapses it again (timeout / another press / explicit dismiss).

Also still open, either is a reasonable session instead:

2. **Leftover real-hardware gaps from Milestone 7**, still open: a
   real-hardware pass on Part B.4 (does the ~4s cursor-dwell dismiss feel
   right?), and the Session 5 performance follow-ups (CUDA-enabled
   `llama-cpp-python`, syncing `vision.trigger_keywords`/
   `locate_trigger_keywords` in the live config) — see `docs/TODO.md`'s
   "Loose ends" section for full detail.
3. **Milestone 10 Part A's real-hardware gaps** — does the frosted-glass
   effect actually read well over real desktop content, and does the
   island stay off the taskbar/alt-tab as intended.

Also worth a look whenever it comes up naturally, not urgent enough to
be its own session: `memory.context_turns` has no token-budget
accounting against `llm.n_ctx` (see `docs/DECISIONS.md`'s Milestone 9
Part B entry) — fine at the current default of 5 short turns, but worth
revisiting if real usage pushes it higher or turns get long.

## Ready-to-copy prompt for the next session

```
Continue development of Iris, a fully local AI desktop copilot for Windows.

Before writing any code:
1. Read HANDOFF.md (this file)
2. Read every file inside /docs
3. Understand the current project state

Milestones 1-9 are done and confirmed on real hardware. Milestone 10 has
been reframed (Session 10) from a generic settings screen to a Dynamic
Island floating pill overlay -- see docs/DECISIONS.md's Milestone 10
entry for the full reasoning. Part A (the static widget,
app/dynamic_island.py -- shape, near-black/frosted-glass color,
collapsed/expanded states, bottom-center positioning) is done and
verified offscreen (real painted pixels, not just code review). Nothing
is wired into main.py yet.

Pick up Milestone 10, Part B -- activation triggers: wire a global
keyboard shortcut (needs a real Windows global-hotkey mechanism, e.g.
pywin32's RegisterHotKey or the keyboard package -- Qt's own QShortcut
only fires when Iris has focus) and the existing voice wake word path
(main.py's on_wake_word_detected) so either one calls
DynamicIslandWidget.expand(). Decide and document what collapses it
again. Confirm this is still the right next step with the user before
starting, and keep working in small, confirmed parts rather than doing
B-D in one pass, per the user's stated preference.

If the user would rather pick up something else instead, the other open
items are: leftover Milestone 7 real-hardware gaps (Part B.4 cursor-dwell
dismiss, and the Session 5 performance follow-ups -- see docs/TODO.md's
"Loose ends" section), or a real-hardware pass on Dynamic Island Part A
itself (does the frosted-glass effect read well over real desktop
content, does it stay off the taskbar/alt-tab).

IMPORTANT -- read this before touching anything: this project's zip
exports have repeatedly NOT contained the previous session's finished
work, and Session 9 also hit this from the other direction -- the
user's own machine was still running stale code after a zip delivery,
which looked exactly like a real bug until checked directly (grep for a
distinguishing string from the new code, both in the zip you're about
to build on top of AND, if a real-hardware test result looks
suspicious, on the machine that ran it). Before writing any code this
session: diff what HANDOFF.md/docs/TODO.md claim is done against what's
actually importable/present in the checkout.

Work incrementally, in small parts (not all at once -- confirm progress
with me between parts). Do not write fake/mock-only "it imports" tests --
verify things for real wherever this sandbox allows, and say plainly
when something genuinely can't be (e.g. real model weights, a real
display, real hardware). End the session by updating HANDOFF.md and
docs/TODO.md, and only docs/ROADMAP.md / docs/ARCHITECTURE.md /
docs/DECISIONS.md / README.md if something actually changed.
```
