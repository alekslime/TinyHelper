# HANDOFF.md

**Last updated:** 2026-07-10
**Milestone completed:** Milestone 4 — Local LLM Integration ✅

---

## Summary of work completed

Milestone 4 is complete: local LLM text generation via llama.cpp
(`llama-cpp-python`), wired into `on_transcribed()` so a transcribed (or
debug-typed) command now gets a real generated response instead of the
`TODO (Milestone 4)` placeholder. Built in one part, since the shape
closely follows Milestone 3's speech-to-text wiring:

1. **`llm/engine.py`** — `LLMEngine`, wraps a llama.cpp `Llama`
   instance. Downloads its GGUF model from Hugging Face Hub via
   `Llama.from_pretrained(repo_id, filename)` by default (cached after
   first use, same pattern as Faster-Whisper), or loads a local `.gguf`
   directly if `llm.local_model_path` is set in config. Single-turn
   `generate(user_text) -> str`, no conversation memory yet (Milestone 9).
2. **`app/llm_bridge.py`** — Qt signal bridge (`response_ready`,
   `generation_failed`), same pattern as `transcript_bridge.py`.
3. **Wiring in `main.py`** — `on_transcribed()` now keeps Aura in THINKING
   and runs `LLMEngine.generate()` on a dedicated worker thread
   (`_run_generation`), never the audio callback or Qt main thread. The
   result reaches the main thread via `llm_bridge`, which drives
   `on_llm_response()` (display + Aura → IDLE) or `on_llm_failed()`
   (display + Aura → ERROR). LLM construction failure (missing extra, or
   model load/download failure) leaves `llm_engine = None` and
   `on_transcribed()` shows a fallback message instead of crashing —
   same graceful-degradation pattern as the transcriber.
4. **`app/main_window.py`** — added a read-only response text area (not
   gated by `debug.enabled`, unlike the debug input — this is the only
   way to see a response at all until Milestone 8 adds voice output) and
   a `show_response(text)` method.
5. **`config/schema.py` / `config/default_config.yaml`** — new `LLMSettings`
   / `llm:` section: `repo_id`, `filename`, `local_model_path`, `n_ctx`,
   `n_gpu_layers`, `max_tokens`, `temperature`, `system_prompt`.

## Files created

```
iris/
├── app/
│   └── llm_bridge.py    (new)
├── llm/
│   └── engine.py        (new)
```

## Files modified

- `main.py` — LLM construction (defensive import + graceful load-failure
  handling, same shape as `voice.service`), `llm_bridge` wiring,
  `on_transcribed()` now spawns a worker thread for generation instead of
  immediately returning to IDLE, new `on_llm_response()`/`on_llm_failed()`
  handlers.
- `app/main_window.py` — added the response display area + `show_response()`.
- `config/schema.py` — added `LLMSettings`, registered on `AppSettings`.
- `config/default_config.yaml` — added `llm:` section.
- `pyproject.toml` — added `huggingface_hub` to the `llm` extras group
  (needed by `Llama.from_pretrained`).
- `docs/ROADMAP.md` — Milestone 4 marked complete.
- `docs/ARCHITECTURE.md` — documented `llm/` module structure, updated the
  data-flow diagram.
- `docs/DECISIONS.md` — four new entries: model download/cache pattern,
  default-model rationale ("small and working" over "best for target
  hardware"), worker-thread generation, graceful LLM failure handling.
- `docs/TODO.md` — rewritten for Milestone 5 (screen capture + vision)
  next steps.
- `README.md` — updated status and testing instructions.

## Dependencies added

- `huggingface_hub>=0.23.0` (new, `llm` extras group) — required by
  `Llama.from_pretrained()` for the download-and-cache flow.
- `llama-cpp-python` was already declared in the `llm` extras group since
  Milestone 1's `pyproject.toml` scaffolding (just unused until now).

## Important implementation details

- **Default model:** `Qwen/Qwen2.5-0.5B-Instruct-GGUF`,
  `qwen2.5-0.5b-instruct-q4_k_m.gguf` (~1GB). Picked to get the full
  pipeline working end-to-end quickly, not for best quality on the
  documented RTX 3070 Ti target — see `docs/DECISIONS.md`. Swapping models
  is a one-line `config.yaml` change (`llm.repo_id`/`llm.filename` for
  another HF-hosted GGUF, or `llm.local_model_path` for a local file already on
  disk) — no code changes needed either way.
- **`gpu_layers: -1`** (default) tells llama.cpp to offload as many layers
  as fit on the GPU. Should put the whole 0.5B model on the GPU comfortably
  on both the 3070 Ti and the dev laptop, but this is reasoned about, not
  yet measured on real hardware (see "Known issues").
- **Generation runs on a dedicated worker thread**, same reasoning as
  Milestone 3's transcription: a `threading.Thread` per request, result
  delivered back to Qt via `LLMResponseBridge`. Aura stays in THINKING for
  the duration.
- **No conversation memory.** Each `generate()` call is independent,
  seeded only with `llm.system_prompt`. Multi-turn context is Milestone 9.
- **LLM failure (missing extra or load failure) does not disable voice/
  transcription.** Mirrors the transcriber's failure isolation from
  Milestone 3 — `llm_engine` is `None` in that case, and
  `on_transcribed()` shows a fallback message and returns Aura to IDLE
  instead of attempting generation.
- **Response display, not gated by `debug.enabled`.** Unlike the debug
  text *input*, the response *display* is core Milestone 4 functionality
  (there's no other way to see a response yet, pending Milestone 8's
  voice output) — so it always shows, debug panel or not.

## Current folder structure

See "Files created" above for what's new; full structure otherwise
unchanged from Milestone 3's `HANDOFF.md`.

## Known issues

- **Real LLM generation has NOT been verified end-to-end on real hardware
  yet.** Same category of gap as Milestone 3's Whisper transcription —
  this dev sandbox has no Hugging Face Hub access, so `LLMEngine` could
  only be verified for its import-failure and graceful-degradation paths
  (via the debug text input, with no `llm` extra installed), not actual
  generation: model download, load time, VRAM usage, response quality, or
  latency. **The next session on real hardware should:**
  `pip install -e ".[llm]"`, run `main.py`, use the debug text input (or
  real voice, once verified per Milestone 3's open item) to ask something,
  and confirm a reasonable response shows up in the window and console
  within a few seconds. Report back before deciding whether to keep the
  default model or swap to something bigger.
- **Startup time impact unmeasured.** The LLM now loads eagerly at startup
  alongside the wake word and Whisper models, same as Milestone 3 flagged
  for Whisper. Worth timing combined startup on real hardware.
- Same open items as Milestone 3's `HANDOFF.md` re: real-mic silence
  detection tuning and `tests/` still being empty — now also applicable to
  `llm/engine.py`, which has zero test coverage.

## Testing performed

1. **`config/schema.py` / `config/default_config.yaml`:** loaded the YAML
   through `AppSettings` directly — validates cleanly, `llm.*` fields
   populate with the expected defaults — PASS.
2. **`llm/engine.py` / `main.py` import wiring:** confirmed the
   `try/except ImportError` path fires correctly with `llama-cpp-python`
   genuinely not installed in this sandbox (not simulated) — app logs the
   warning and continues rather than crashing.
3. **Full `main.py` end-to-end (offscreen Qt, real subprocess-equivalent
   run):** app starts, both voice and LLM dependencies genuinely missing
   in this sandbox → both warnings logged, window constructs, no crash.
4. **Debug text input → no-LLM fallback path:** emitted
   `debug_text_submitted` programmatically with `llm_engine is None`,
   confirmed `on_transcribed()` shows the fallback message in
   `MainWindow`'s response area and Aura returns to IDLE without error —
   PASS.
5. **NOT tested: actual generation** (needs Hugging Face Hub access this
   sandbox doesn't have, same limitation as Milestone 3's Whisper).
6. All test artifacts cleaned up afterward.

## Current project status

Milestone 4 is code-complete and tested as thoroughly as this sandbox
allows — the full pipeline wiring, failure-isolation paths, and config
validation were all verified for real. The one genuine gap is actual
generation (download, load, quality, latency), which needs the real
target machine's Hugging Face access.

## Next milestone

**Milestone 5 — Screen Capture + Vision**, via MSS + an ONNX Runtime
vision model. See `docs/ROADMAP.md` for scope and `docs/TODO.md` for
specific next actions, including deciding how vision output folds into
the LLM prompt built for `llm/engine.py`.

## Ready-to-copy prompt for the next session

```
Continue development of Iris, a fully local AI desktop copilot for Windows.

Before writing any code:
1. Read HANDOFF.md (this file)
2. Read every file inside /docs
3. Understand the current project state

Milestone 4 (local LLM integration) is code-complete but has an unverified
gap: real generation was not testable in the previous session's dev
sandbox (no Hugging Face Hub access). Before starting Milestone 5, please:
  1. Run `pip install -e ".[speech,llm]"` and `python main.py` on this machine
  2. Say "Hey Jarvis" (or use the debug text input) followed by a short
     question (e.g. "what's 12 times 7")
  3. Confirm a reasonable response appears in the window and console
     within a few seconds
  4. Note the model download time, load time, and rough response latency
  5. Report back what you observed before we proceed — including whether
     the default small model (Qwen2.5-0.5B) feels worth upgrading now
     that we can see real headroom on this hardware

Once that's confirmed, start Milestone 5 — Screen Capture + Vision, as
scoped in docs/ROADMAP.md and docs/TODO.md.

Work incrementally, in small parts (not all at once — confirm progress
with me between parts). Do not begin implementing anything beyond
Milestone 5's scope. End the session by updating HANDOFF.md and
docs/TODO.md, and only docs/ROADMAP.md / docs/ARCHITECTURE.md /
docs/DECISIONS.md / README.md if something actually changed.
```
