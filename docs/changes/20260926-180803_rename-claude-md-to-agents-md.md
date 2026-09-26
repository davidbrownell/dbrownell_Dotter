---
type: Change
title: Renamed CLAUDE.md to AGENTS.md
description: Moved agent instructions from CLAUDE.md to the tool-neutral AGENTS.md and updated them to python_development version 0.8.0.
tags: [config, agents]
generated:
  by: claude-code/claude-opus-5-5
  at: 2026-09-26T22:08:03Z
sources:
  - resource: /AGENTS.md
    title: Agent instructions
---

# Summary
The repository's agent instructions moved from `CLAUDE.md` to `AGENTS.md`. The content was refreshed to the `python_development` template version 0.8.0.

# Changes
* **Deletion**: Removed `CLAUDE.md`.
* **Creation**: Added `AGENTS.md` with the previous instructions plus:
  * Version header renamed from `Version: 0.6.0` to `python_development Version: 0.8.0`.
  * "SOLID" expanded to "SOLID design principles".
  * New "Python Development > General" section: run `python`-related tasks using `uv`.

# Rationale
`AGENTS.md` is the vendor-neutral convention read by multiple coding agents, whereas `CLAUDE.md` targets only Claude Code. The template update keeps the instructions in sync with the shared `python_development` template.
