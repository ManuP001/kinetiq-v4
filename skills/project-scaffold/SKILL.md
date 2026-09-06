---
name: project-scaffold
description: Scaffold a full AI-assisted project structure — a root CLAUDE.md, folder-level CLAUDE.md files (agents/, evals/, frontend/, backend/, skills/), and a DESIGN.md — following the three-tier CLAUDE.md hierarchy (global → project → directory). Use this whenever the user wants to set up a new project, bootstrap a repo, initialize CLAUDE.md files, standardize an existing project's structure, or asks something like "set up my project", "scaffold this", "initialize CLAUDE.md", "create the folder structure", or "get this repo Claude-Code-ready" — even if they don't name these exact files. Also trigger if an Obsidian vault is mentioned as a source of project context.
---

# Project Scaffold

Generates a persistent-instruction file structure for any AI-assisted software project: one master `CLAUDE.md` at the repo root, narrower `CLAUDE.md` files inside key subfolders, a `DESIGN.md`, and the folders those files govern (`agents/`, `evals/`, `frontend/`, `backend/`, `skills/`). This is infrastructure, not boilerplate — the goal is a project where Claude Code never has to guess architecture, conventions, or quality bar.

This skill is project-agnostic. It works for a Next.js SaaS app, a mobile app, a data pipeline, or anything else — the questions below adapt the templates to whatever the user is building.

## When invoked

1. **Gather context before writing anything.** Don't generate placeholder-filled files and call it done — spend one round of questions first. Ask (batch these, don't drip them one at a time):
   - What is the project, in one sentence? Who is it for / what problem does it solve?
   - What's the tech stack? (framework, database, auth, AI/LLM usage if any, deployment target)
   - Is this a fresh repo or an existing one? If existing, look at the actual folder structure, `package.json` / `requirements.txt` / etc., and existing docs before assuming anything.
   - Solo project or team? (This decides whether the root CLAUDE.md needs the Team Collaboration additions — ownership, PR conventions, decision log.)
   - Does the project have (or will it have) sub-agents, an eval harness, a frontend, a backend, and reusable skills? Not every project needs all five folders — skip the ones that don't apply rather than forcing empty structure.

   If the user has already given most of this in the conversation, don't re-ask — confirm your understanding in one line and proceed.

2. **Check for an Obsidian vault.** If the user mentions a vault, a notes folder, or gives a path that looks like an Obsidian vault (a directory containing `.md` files and possibly a `.obsidian/` config folder): before drafting content, search that vault for files relevant to this project (matching the project name, or under a folder named after it). Pull in anything that looks like architecture decisions, naming conventions, known gotchas, or a decision log — these belong in CLAUDE.md more than a fresh guess does. If no vault is mentioned or accessible, skip this step silently — don't ask the user to set one up.

3. **Create the directory structure and files** (see templates below). Only create folders relevant to what the user is building.

4. **Populate, don't leave placeholders where you have real information.** Anything you learned in step 1 or step 2 goes into the file for real — sections you truly don't have information for stay bracketed for the user to fill in (`[fill in]`), rather than inventing plausible-sounding specifics.

5. **Tell the user what you created and what still needs their input.** List the files, and call out any `[fill in]` placeholders that remain so they know exactly what to complete before the first Claude Code session on the real work.

Don't treat this as a one-shot template dump — the point of the interview in step 1 is that a scaffold built from real answers is worth using, and one built from guesses gets rewritten within a day anyway.

---

## The hierarchy this skill builds

```
project-root/
├── CLAUDE.md                  ← master file: purpose, stack, architecture, quality bar
├── DESIGN.md                  ← design system / UX principles (if the project has a UI)
├── agents/
│   └── CLAUDE.md               ← scope, responsibilities, and boundaries for each agent
├── evals/
│   └── CLAUDE.md               ← what "correct" means here, how to run and read evals
├── frontend/
│   └── CLAUDE.md               ← component conventions, styling rules, state patterns
├── backend/
│   └── CLAUDE.md               ← API conventions, data layer rules, service boundaries
└── skills/
    └── CLAUDE.md               ← how project-specific Claude Code skills are structured
```

Claude Code reads the root `CLAUDE.md` at the start of every session, and additionally reads any directory-level `CLAUDE.md` under the file it's currently working on — more specific files take priority over the root file when they conflict. That's why the folder files should stay narrow: they only need to say what's true in that folder and different from the root defaults, not repeat the whole project context.

If the user is a solo developer working across multiple machines or projects, mention (don't force) that a fourth, even-broader level exists: `~/.claude/CLAUDE.md`, for preferences that apply to everything they build, not just this project.

---

## Template: root `CLAUDE.md`

Adapt every bracketed section to what you learned in the interview. Drop sections that don't apply (e.g., no "Database" section for a pure frontend project) rather than leaving them empty.

```markdown
# CLAUDE.md

## Project
[Project name] — [one sentence describing what it does]
[One paragraph: who uses it, what problem it solves, what stage it's at]

## Purpose & Objectives
- [Primary objective — the thing this project must do well]
- [Secondary objective]
- [Non-goal: something explicitly out of scope, to stop Claude from wandering into it]

## Tech Stack
- Framework: [...]
- Database: [...]
- Auth: [...]
- AI/LLM: [...] (if applicable)
- Styling: [...]
- Deployment: [...]
- CI: [...]

## Commands
[the actual commands to install, run dev, build, test, lint — not placeholders if you know them]

## Repo Structure
- /agents — [purpose]
- /evals — [purpose]
- /frontend — [purpose]
- /backend — [purpose]
- /skills — [purpose]
- [any other top-level folder and what lives there]

## Architecture Rules
- [The 3–6 structural rules that, if violated, cause the most rework — e.g. "business logic lives in /backend/services, never in route handlers"]

## Patterns to Follow
- [...]

## Patterns to Avoid
- [...]

## Security
- [Auth, input validation, secrets handling, rate limiting — whatever applies]

## Testing
- [What gets tested, what doesn't, how to run it]

## Quality Bar
- [The standard every PR/change is held to — loading/error/empty states, mobile-first, etc.]

## Current Focus
[What's being worked on right now — update at the start of each session]

## Known Issues
[Open bugs or tech debt Claude should be careful around]

## Decision Log
- [Date]: Chose [X] over [Y] because [reason]
[Only include this section for team projects, or solo projects where decisions get revisited often]
```

Why each section earns its place: **Purpose & Objectives** stops Claude from optimizing for the wrong thing when a request is ambiguous. **Architecture Rules** and **Patterns to Follow/Avoid** prevent drift between session 1 and session 50. **Known Issues** stops Claude from "fixing" a bug by introducing a different one nearby. **Decision Log** stops the same debate (framework choice, library choice) from being relitigated every few sessions.

Keep the whole file under ~100 lines where possible. A CLAUDE.md that's too long to skim stops getting read carefully — compress ruthlessly and let the project teach you which rules earn a permanent place.

---

## Template: folder-level `CLAUDE.md`

Each of these is short — a page, not a document. It only states what's specific to that folder; it inherits everything else from the root file.

**`agents/CLAUDE.md`**
```markdown
# CLAUDE.md — agents/

## Purpose
[What this directory holds — e.g. "Sub-agent definitions for the three-agent pipeline: Memory, Coaching, Planner"]

## Per-agent scope
- [agent-name]: [single responsibility — what it owns, what it must never do]
- [agent-name]: [...]

## Conventions
- Each agent gets a narrow, single-purpose prompt — no agent should need context outside its own scope
- [Model routing rules if relevant — e.g. "Coaching agent: Haiku for routine feedback, Sonnet for form-correction edge cases"]
- [Handoff format between agents, if applicable]

## Boundaries
- [What agents must escalate to a human or to the main/orchestrating agent rather than deciding themselves]
```

**`evals/CLAUDE.md`**
```markdown
# CLAUDE.md — evals/

## Purpose
[What "correct" means for this project, and how it's measured]

## Eval Types
- Rule-based checks: [what they cover]
- LLM-as-judge: [what they cover, which model judges]
- [Human review: when it's still required]

## Running Evals
[the actual command]

## Reading Results
[what a passing vs failing run looks like, where thresholds live]

## Adding a New Eval
[the pattern to follow — test case format, naming convention]
```

**`frontend/CLAUDE.md`**
```markdown
# CLAUDE.md — frontend/

## Conventions
- [Component structure, naming, file organization]
- [State management approach]
- [Styling approach — reference DESIGN.md for tokens, don't restate them here]

## Patterns to Follow / Avoid
- [...]

## States every component must handle
- Loading, empty, error, success
```

**`backend/CLAUDE.md`**
```markdown
# CLAUDE.md — backend/

## Conventions
- [API route structure: validate → auth → execute → respond, or whatever the actual pattern is]
- [Where business logic lives vs. where it must not live]
- [Data layer rules — ORM usage, raw queries, transactions]

## Security
- [Endpoint-specific rules beyond the root file's general security section]
```

**`skills/CLAUDE.md`**
```markdown
# CLAUDE.md — skills/

## Purpose
Project-specific Claude Code skills live here as subfolders, each with its own SKILL.md.

## Conventions
- One skill per subfolder: /skills/[skill-name]/SKILL.md
- Skill descriptions should be specific enough to trigger reliably and name the exact phrases that should invoke them
- [Any project-specific skill you already know you need — list it even if not yet written]
```

---

## Template: `DESIGN.md`

Only create this if the project has a user-facing interface.

```markdown
# DESIGN.md

## Design Principles
[2-4 principles specific to this product — not generic "clean and modern"]

## Color Tokens
[Reference the actual tokens file path, e.g. /frontend/styles/tokens.css — don't duplicate the values here, they'll drift out of sync]

## Typography
- [Heading font, body font, code font, and why each was chosen]

## Spacing & Layout
- [Base unit, grid, breakpoints]

## Component Patterns
- [Buttons, forms, cards — the handful of patterns that should look identical everywhere they appear]

## States & Feedback
- [Loading, error, empty, success — what each looks like, not just that it must exist]
```

---

## Obsidian cross-referencing (conditional)

If the user has an Obsidian vault path available (they mention one, or a path in the conversation looks like a vault): before finalizing CLAUDE.md content, search it for markdown notes relevant to the project — matching on project name, and on section topics like "architecture," "decisions," "gotchas," or "conventions." Anything found there that's still current should be folded into the relevant CLAUDE.md section (most often Architecture Rules, Known Issues, or Decision Log) rather than left to be rediscovered later. If nothing relevant turns up, or no vault is available, don't mention it — just proceed with what the user told you directly.

---

## After scaffolding

Tell the user, in a short list:
- Which files and folders were created
- Which sections still have `[fill in]` placeholders and need their input before the first real Claude Code session
- That CLAUDE.md is a living document — worth revisiting after every session where Claude made a repeated mistake, and worth compressing if it creeps past ~100 lines
