# CLAUDE.md — skills/

Inherits from the root `CLAUDE.md`; this states only what's specific to `skills/`.

## Purpose
Project-specific Claude Code skills, one per subfolder, each with its own `SKILL.md`.

## Present
- `project-scaffold/` — scaffolds the three-tier CLAUDE.md hierarchy (root → folder-level) + DESIGN.md
  for an AI-assisted project. This monorepo's own structure was generated from it.

## Conventions
- One skill per subfolder: `skills/<skill-name>/SKILL.md`.
- A skill's `description` should name the exact phrases that ought to trigger it, so it fires reliably.
- Skills are instructions, not runtime code — they don't ship in the Docker image or the static site.
