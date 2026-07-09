# Decisions

A log of notable architectural and design decisions, why they were made,
and what alternatives were considered. Add an entry whenever a decision is
made that a future session (or contributor) would otherwise have to
re-derive or might accidentally reverse.

---

## 2026-07-09 — Aura communicates via a controller + state enum, not direct calls

**Decision:** All Aura state changes go through `AuraController.set_state(AuraState.X)`.
No module outside `aura/` imports a renderer directly.

**Why:** The project requires Aura to remain "completely independent from
the AI logic" and support a future community theming system. A thin,
state-based interface is the smallest contract that achieves this — any
future renderer just needs to implement `AuraRenderer` and react to five
enum values.

**Alternative considered:** Event bus / pub-sub system. Rejected for now as
over-engineering at this stage — a direct controller call is simpler to
reason about with only one consumer (the renderer) so far. Revisit if
multiple independent listeners to Aura state emerge (e.g. logging,
telemetry, a future settings UI showing live state).

---

## 2026-07-09 — `NullAuraRenderer` ships before any real rendering

**Decision:** Milestone 1 ships an abstract `AuraRenderer` interface and a
no-op `NullAuraRenderer` implementation, not a real GPU renderer.

**Why:** Per the project's incremental development workflow, Milestone 1's
scope is explicitly "placeholder renderer interface... no rendering yet."
This lets every later milestone (voice, LLM, vision) integrate against a
stable Aura API immediately, without blocking on the more complex GPU
rendering work planned for Milestone 6.

---

## 2026-07-09 — Config: bundled defaults + user override file, not env vars

**Decision:** Configuration is YAML-based: a version-controlled
`config/default_config.yaml` plus a user-editable file written to
`%APPDATA%/Iris/config/config.yaml` on first run. No environment-variable
based configuration for user-facing settings.

**Why:** Iris is a desktop app for non-technical end users (eventually), not
a server process — a human-editable YAML file in a discoverable location
fits that model better than env vars. `%APPDATA%` is the idiomatic Windows
location for per-user application data.

**Alternative considered:** A single config file with no default/override
split. Rejected because it makes it impossible to distinguish "user
intentionally changed this" from "this is just the shipped default," which
matters once we build a settings UI (Milestone 10) that needs to show
users what they've customized.

---

## 2026-07-09 — Heavy ML dependencies as optional `pyproject.toml` extras

**Decision:** `faster-whisper`, `llama-cpp-python`, `mss`, `opencv-python`,
`onnxruntime-gpu`, `pywin32` are declared under `[project.optional-dependencies]`,
not core `dependencies`.

**Why:** These are large, sometimes platform/hardware-sensitive packages
(e.g. `onnxruntime-gpu` needs a matching CUDA setup). Installing them all
upfront before the milestones that use them exist would slow down early
development iteration and make it harder to isolate install issues to the
specific feature being built.
