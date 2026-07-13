# HANDOFF.md

**Last updated:** 2026-07-13
**Milestones completed:** 1 through 6 ✅ — plus a targeted fix ahead of
Milestone 7 (vision query gating). See `docs/ROADMAP.md` for full
milestone history.

---

## Summary of work completed since the last HANDOFF.md update

This file was last written at the end of Milestone 4; Milestones 5 and 6
have since shipped and been verified on real hardware (see
`docs/ROADMAP.md` and `docs/TODO.md` for their full detail — not
duplicated here). Most recently (2026-07-13), ahead of starting
Milestone 7:

1. **Vision query gating (loose end from Milestone 5's TODO).**
   `vision.enabled` previously ran screen capture + captioning on *every*
   transcribed/debug query, once turned on — real unnecessary latency
   since MiniCPM-V-2.6 is CPU-only on the target 3070 Ti. Added
   `VisionSettings.trigger_keywords` (default: `screen, see, look, this,
   here`) — a case-insensitive substring check in `main.py`'s
   `_build_prompt_with_screen_context()` that now runs before
   `screen_capture.capture()` is ever called. Empty list = old
   always-on behavior, kept as an escape hatch. See `docs/DECISIONS.md`
   for why a keyword heuristic was chosen over an explicit trigger
   phrase.
2. **Resynced `config/default_config.yaml`'s stale `vision:` section.**
   It still had Milestone 5's original ONNX/Xenova captioning fields from
   before the moondream2 → MiniCPM-V-2.6 rework — harmless at runtime
   (Pydantic falls back to schema defaults for missing yaml keys) but
   misleading to read/edit. Replaced with the current GGUF-based fields
   plus the new `trigger_keywords`.

## Files modified (this session)

- `config/schema.py` — added `VisionSettings.trigger_keywords`.
- `config/default_config.yaml` — added `trigger_keywords`; resynced the
  rest of the `vision:` section to match the current schema (GGUF fields,
  `ocr_*`, `tesseract_cmd` — replacing the stale ONNX/Xenova fields).
- `main.py` — `_build_prompt_with_screen_context()` now checks
  `settings.vision.trigger_keywords` against the query text before
  capturing/captioning/OCR-ing the screen.
- `docs/TODO.md` — marked the vision-gating loose end and the stale-yaml
  issue as fixed, with details.
- `docs/DECISIONS.md` — two new entries: the keyword-gating choice, and
  the yaml resync.

## Important implementation details

- **Gating is config-driven**, same pattern as every other tunable —
  no hardcoded keyword list in `main.py` itself.
- **Substring match, not word-boundary/regex match** — deliberately
  simple. `"this"` matches inside `"is this correct"` as intended; also
  matches inside unrelated longer words in principle (accepted
  imprecision for a first pass — see `docs/DECISIONS.md`'s "not yet
  tuned" note).
- **OCR (`ocr_reader`) is gated by the same check as captioning**, not
  separately — both were already only invoked from inside
  `_build_prompt_with_screen_context()`, so one early-return covers both.

## Known issues / not yet verified

- **Vision gating has NOT been verified on real hardware yet.** This
  sandbox has no microphone/real vision-model access. Next session on
  real hardware should: ask a query containing a trigger keyword (confirm
  screen context still appears in the response, same as before) and a
  query without one (confirm it's skipped — check the new debug log line
  `"Skipping screen context — query matched none of vision.trigger_keywords"`
  and that response latency is visibly lower).
- All previously-open items in `docs/TODO.md`'s "Loose ends" section
  remain open except the two closed this session (vision gating, stale
  yaml) — startup timing, `tests/` coverage for `voice/`/`speech/`/`llm/`,
  silence-detection tuning, etc. See `docs/TODO.md` directly rather than
  duplicating that list here.

## Current project status

Milestones 1–6 are code-complete and verified on real hardware (per
`docs/ROADMAP.md`). The vision-gating fix above is code-complete but
needs a real-hardware pass to confirm it actually triggers/skips
correctly, not just that it imports and merges config correctly (which
was verified in this sandbox). Milestone 7 (Visual Guidance) has not
been started yet — design discussion is in progress; approach chosen so
far is grammar/structured-JSON output from the vision model (over a
simpler regex-parsed single-location approach) so it can express multiple
shapes (circles, arrows, bounding boxes, labels) per the milestone's full
scope, not just one region. No code written for Milestone 7 yet.

## Next milestone

**Milestone 7 — Visual Guidance.** Overlay rendering (circles, arrows,
highlights, bounding boxes, labels) triggered by LLM/vision reasoning
about screen content, extending `aura/renderer/`. See `docs/ROADMAP.md`
for scope. Design approach (structured/JSON output via `llama-cpp-python`
GBNF grammar constraints) was chosen over a simpler regex-based approach
specifically to support multiple annotation shapes per response — see the
next session's discussion for the concrete schema before implementation
starts.

## Ready-to-copy prompt for the next session

```
Continue development of Iris, a fully local AI desktop copilot for Windows.

Before writing any code:
1. Read HANDOFF.md (this file)
2. Read every file inside /docs
3. Understand the current project state

Milestones 1-6 are done and verified on real hardware. A vision-gating
fix (query keyword check before screen capture) was added this session
but is NOT yet verified on real hardware -- verify it first:
  1. Run with vision.enabled: true
  2. Ask a query containing a trigger keyword (e.g. "what's on my
     screen") -- confirm screen context still appears in the response
  3. Ask a query without one (e.g. "what's 12 times 7") -- confirm the
     debug log shows it was skipped, and response latency is visibly
     lower than a vision-triggered query
  4. Report back before starting Milestone 7

Once that's confirmed, start Milestone 7 -- Visual Guidance, as scoped in
docs/ROADMAP.md. The chosen approach is structured/JSON output from the
vision model via a GBNF grammar (llama-cpp-python), constraining it to
emit shape annotations (circles, arrows, bounding boxes, labels) with
screen coordinates, which aura/renderer/ then draws. Work out the
concrete JSON schema and grammar as the first small piece, confirm it
before wiring it into the renderer.

Work incrementally, in small parts (not all at once -- confirm progress
with me between parts). Do not begin implementing anything beyond
Milestone 7's scope. End the session by updating HANDOFF.md and
docs/TODO.md, and only docs/ROADMAP.md / docs/ARCHITECTURE.md /
docs/DECISIONS.md / README.md if something actually changed.
```
