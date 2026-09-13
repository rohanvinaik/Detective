# Parked: the MCP surface

`mcp_server.py` is Detective's MCP server — the `detective-mcp` command and the tools it registered,
each rendering the engine's results for a model caller rather than a human (design record:
[ARCHITECTURE.md §5a](../../ARCHITECTURE.md)). It was parked on 2026-09-13.

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
4. Return ARCHITECTURE.md §5a and its table rows from "parked" to current.
5. Delete `plan.plan_closing` from `BY_DESIGN` in `tests/test_pinned_decision_consumption_intent.py`.
   Its only production consumer is this server's `_render_plan`, so the consumption guard reports the
   entry stale as soon as the surface is back.
