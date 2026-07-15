"""Optional MCP surface — a thin projection of the diagnose/certify API.

Requires the ``mcp`` extra (``uv pip install 'detective-spec[mcp]'``); ``mcp`` is imported
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
    """Entry point for the ``detective-mcp`` console script.

    The script is installed unconditionally — a wheel cannot make a console script
    depend on an extra — so on a plain ``detective-spec`` install it is present but its
    dependency is not. Left alone, it dies on a raw ModuleNotFoundError traceback and
    reads like a broken package. Say what is missing and how to get it instead.
    """
    try:
        server = build_server()
    except ModuleNotFoundError as exc:  # pragma: no cover — depends on the extra being absent
        if exc.name != "mcp" and not str(exc).startswith("No module named 'mcp"):
            raise
        raise SystemExit(
            "detective-mcp: the optional MCP server dependency is not installed.\n"
            "  install it with:  uv pip install 'detective-spec[mcp]'\n"
            "  (the `detective` CLI itself needs nothing extra — this is only for the MCP surface)"
        ) from None
    server.run()


if __name__ == "__main__":
    main()
