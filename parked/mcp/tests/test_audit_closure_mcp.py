"""PARKED with the MCP surface (see parked/mcp/README.md): the MCP half of what was
`test_both_surfaces_keep_inexpressible_line_gaps_out_of_input_commands` in
tests/test_audit_closure_advice_intent.py, whose CLI half stayed there as
`test_the_cli_keeps_inexpressible_line_gaps_out_of_input_commands`.

Split out 2026-09-13. Imports `Detective.mcp_server`, which does not exist while the surface is
parked; it runs again once the surface is restored.
"""

from types import SimpleNamespace

from Detective.mcp_server import _ask_for_input


def test_the_mcp_surface_keeps_inexpressible_line_gaps_out_of_input_commands():
    proof = SimpleNamespace(
        param_names=("grid",),
        signature="f(grid)",
        inputs_expressible=False,
        missing_lines=(8,),
        missing_line_guards=((8, "grid.shape[0] > 0"),),
    )
    mcp = "\n".join(_ask_for_input("converge", "m.py", "f", ("grid",), "gap", proof=proof))
    assert "WRITE TEST" in mcp
    assert "line 8" in mcp
    assert "--input" not in mcp
    assert "inputs=[" not in mcp
