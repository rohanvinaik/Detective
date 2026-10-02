# CLAUDE.md — Detective

@AGENTS.md

## Claude Code specifics

- **Read the sandwich thesis first.** Read `~/.claude/projects/-Users-rohanvinaik-tools-Detective/memory/feedback_sandwich_thesis.md`
  before reasoning about architecture, performance, caching or scoping. It is the founder's own statement of the
  one-function law, with the session it cost to learn.
- **The per-issue loop's tools.** The task queue is TaskCreate, with real `addBlockedBy` edges. On a repo switch, run
  Serena's `activate_project`.
- **Serena cautions specific to these repos:**
  - Call Serena fresh each time, and verify the returned body matches what you asked for.
  - **Avoid `replace_symbol_body`.** Its index drifts on heavily edited files and has silently corrupted a source file
    here. Prefer `include_info` + a narrow `Read` + `replace_content` with a literal needle. `info` stays reliable when
    `body` extraction drifts.
  - Grep is permitted only to locate a line number for a subsequent `Read`, never to trace wiring or find references.
- **Self-analysis.** The full `DetectiveUUT/` procedure, with its verification commands, is in
  `memory/project_dogfood_harness.md`. Read it before any whole-package self-analysis run.
- **After a /compact.** Reading the session JSONL is **non-negotiable** when instructed: not the summary, and not the
  entire context either. Extract the user prompts and assistant text responses, with timestamps, for the last 1–4
  hours. Surface relevant tool calls only where needed, write it to a file, and read it. Skipping this once caused a
  bad regression: settled grounding was re-derived and a finished design was re-searched from scratch.
