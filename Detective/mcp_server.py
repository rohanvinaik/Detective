"""Optional MCP surface — a thin projection of the diagnose/certify API.

Requires the ``mcp`` extra (``pip install Detective[mcp]``); ``mcp`` is imported
lazily so the core package stays Wesker + stdlib only. No compute here — each
tool calls the library and returns plain dicts.

    detective-mcp        # or: python -m Detective.mcp_server
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any


def build_server() -> Any:
    """Construct the FastMCP server exposing diagnose + certify."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("Detective")

    @server.tool()
    def diagnose(file: str, function: str, project_root: str = ".") -> dict:
        """Behavioral-scope map of a function (pure read)."""
        from .engine import diagnose as _diagnose

        return asdict(_diagnose(file, function, project_root))

    @server.tool()
    def certify(file: str, function: str, project_root: str = ".", write_dir: str | None = None) -> dict:
        """Diagnose then synthesize warrant-classed tests for the surviving mutants."""
        from .certify import certify as _certify

        result = _certify(file, function, project_root, write_dir=write_dir)
        return {**asdict(result), "scope": asdict(result.scope)}

    return server


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
