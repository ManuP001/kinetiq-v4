# CLAUDE.md — skills/

Inherits the root `CLAUDE.md`; this states only what's specific to `skills/`.

## Purpose
Project-specific Claude Code skills, one per subfolder, each with its own `SKILL.md`.

## Conventions
- One skill per subfolder: `skills/<skill-name>/SKILL.md`.
- A skill's `description` should name the exact phrases that ought to trigger it, so it
  fires reliably.
- Skills are instructions, not runtime code — they don't ship in the Docker image or the
  static site.

## Present
None yet. This repo is a clean-room rebuild; the original's `project-scaffold/` skill was
not part of the specification it was rebuilt from, so nothing is claimed here (anti-phantom
rule).
