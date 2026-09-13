# Parked: the MCP surface

`mcp_server.py` is Detective's MCP server — the `detective-mcp` command and the tools it registered,
each rendering the engine's results for a model caller rather than a human (design record: [below](#design-record)).
It was parked on 2026-09-13.

## Why it is parked

- **Dependency weight.** The `mcp` extra was the only thing that put a web stack in Detective's
  dependency tree: 30 packages (starlette, uvicorn, httpx, pydantic, cryptography, …), against a base
  install of pytest, ruff and Wesker. `cryptography` carried a published vulnerability
  (PYSEC-2026-3552) in the lockfile.
- **Agents drive the CLI.** Every command prints the next one; the agent workflow runs through the
  terminal, and the MCP tools had gone unused.
- **Severability.** No module in `Detective/` ever imported this one, so the package stands without
  it, and a future MCP surface can be built against the CLI's contract rather than inside the core.

## What is here

- `mcp_server.py` — the server, unchanged from the last version that shipped.
- `tests/` — every test that exercised it:
  - `test_mcp_decompose_residual_native.py`, moved whole;
  - `test_mcp_plan_server.py`, `test_certificate_standing_mcp.py` and `test_audit_closure_mcp.py`,
    the MCP halves split out of `tests/test_plan_decisions_intent.py` (was `test_mcp_plan_intent.py`),
    `tests/test_certificate_standing_intent.py` and `tests/test_audit_closure_advice_intent.py`.

None of it runs while parked: pytest collects only `tests/`, the wheel ships only `Detective/`, and
these tests import `Detective.mcp_server`, which does not exist until the surface is restored.

## Restoring it

1. `git mv parked/mcp/mcp_server.py Detective/mcp_server.py`, and move `parked/mcp/tests/*` into
   `tests/`.
2. Re-add to `pyproject.toml`:

   ```toml
   [project.optional-dependencies]
   mcp = ["mcp>=1.0,<2"]

   [project.scripts]
   detective-mcp = "Detective.mcp_server:main"
   ```

   The `<2` is load-bearing until the server is ported: it is written against FastMCP
   (`from mcp.server.fastmcp import FastMCP`, `@server.tool()`), which mcp 2.0 removed — the class
   became `MCPServer` on a different module path, so a bare `>=1.0` resolves 2.x and
   `detective-mcp` dies on its import line.
3. `uv lock`, then reconcile: the core kept moving while this was parked, and nothing tested the
   seam in between.
4. Move the design record below back into ARCHITECTURE.md §5a, and list `mcp_server.py` in its module
   map again.
5. Delete `plan.plan_closing` from `BY_DESIGN` in `tests/test_pinned_decision_consumption_intent.py`.
   Its only production consumer is this server's `_render_plan`, so the consumption guard reports the
   entry stale as soon as the surface is back.

<a id="design-record"></a>
## Design record (moved from ARCHITECTURE.md §5a)

Five tools: `diagnose`, `converge`, `decompose`, `audit`, `deep_context`. Optional (`[mcp]`
extra); `mcp` is imported lazily so the core stays Wesker + stdlib. Zero compute — each tool calls
the same library the CLI does, inside the same live session (`_in_session` → `run_with_live_suite`,
scoping included). It went without that wrap once, calling the library directly, and every verdict
it returned on a fixture-driven repo was wrong in the tool's least honest direction: MORE
unspecified behavior than exists.

Module map entry, as it stood: `build_server`, `_in_session`, `_rendered`,
`_render_diagnose`/`_render_converge`/`_render_decompose`, `_ask_for_input`, `main`.

**It is not the CLI's text.** That was tried. `cli.py` renders every result correctly and
completely *for a human*, and relaying it verbatim to an LLM failed — the same bytes, in full,
went to stdout and were piped to `tail -3` unread. The CLI's rendering is a **theorem**: every
clause as true as the engine can make it. This surface's output is a **prompt**: correctness is
whether it is *effective*, not whether it is *true*, and it deliberately says things the CLI would
not. Both objects are right; they answer to different criteria.

| Choice | Why |
|---|---|
| **No score in the default view** | a ratio is the most reliable way to make an LLM caller reach outside the tool and grind. The numbers are real and correct — behind `full=True` / `deep_context`, where reading them is deliberate |
| **The mutant kinds ARE shown** | the failure is symmetrical: too terse and the task reads as scut work to shortcut. The behavioral distinctions are the interesting *and* honest part |
| **One next action, an imperative, never a menu** | not because the world is unambiguous — the equivalents fork is undecidable — but because the *caller's legal move set* is singular even when the epistemics are not |
| **Flat prohibitions** ("more passes will not help") | strictly these overclaim. They are the load-bearing sentences |
| **No `flag` tool, no `purge` tool** | `flag` is a human oracle on an undecidable question — the renderer routes it to the user instead. `purge` is a delete-state button, and handing one to a grinding caller invites "the number didn't move, purge and retry" |
| **A header on every CLI-rendered report** | `full=True`/`deep_context` return the CLI's text, which says `--input "(…)"`, `--apply`, `detective flag …` — terminal syntax the caller cannot invoke. The header says: read the detail, ignore the imperatives |

**The engine's epistemics are untouched — and that is checked, not assumed.** Nothing here
re-decides a verdict, softens an UNPROVEN, or spends a crash kill to flatter a number. The
renderers use **direct attribute access, never `getattr(obj, name, default)`**: a default silently
absorbs a wrong field name, and this file did exactly that — it asked `SurvivorReport` for
`candidate_equivalent` (the field is `equivalent`), got `()` forever, and reported *"the suite is
complete, nothing to derive"* over nine UNPROVEN survivors. The engine had classified them
honestly; the renderer promoted UNPROVEN to done. `trace_truncated` is surfaced first for the same
reason: a completeness verdict resting quietly on a truncated measurement is the one failure this
tool cannot afford, and a surface that drops the warning commits it while looking tidier.

Debug-map row, as it stood: *an MCP tool reports "complete / nothing to derive" over UNPROVEN
survivors* → touch `mcp_server` — direct attribute access, never `getattr(obj, name, default)`; a
rename must break loudly, not promote UNPROVEN to done.
