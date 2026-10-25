"""Intent: doctor's ordering remedy is always a command `converge` accepts (#111).

The defect: when doctor's process check found `taste_without_measurement` after `plan` on a FILE or
a PACKAGE, its "Do this" line echoed that path into `detective converge '<path>'` — and converge
accepts only `file.py::function`, so the prescription was refused as written. Reproduced
2026-10-25 on current code: `plan 'm.py'`, then `doctor`, printed `detective converge 'm.py'`.

Two more flaws sat behind it, and either alone would have turned a corrected prescription into a
loop: the process read compared a path target against converge/audit targets by EXACT string (a
converge of `m.py::double` never counted as measuring `m.py`), and it read the certificate store
from the project ROOT rather than from `tests/detective/`, where converge writes it — so no target
ever read as pinned, and the finding could never clear however faithfully it was followed.
"""

from __future__ import annotations

import shlex

import pytest

from Detective.certificates import record_certificate
from Detective.cli import _build_parser, main
from Detective.doctor import order_remedy, red_facts
from Detective.ledger import append

_SRC = "def double(x):\n    return x * 2\n\n\ndef triple(x):\n    return x * 3\n"


@pytest.mark.parametrize(
    ("target", "unpinned", "count", "expected"),
    [
        ("m.py::double", [], 0, ("converge_target", "m.py::double")),
        (" m.py::double ", ["m.py::triple"], 2, ("converge_target", "m.py::double")),
        ("m.py", ["m.py::double", "m.py::triple"], 2, ("converge_region", "m.py::double")),
        ("pkg", ["pkg/mod.py::f"], 5, ("converge_region", "pkg/mod.py::f")),
        ("m.py", [], 2, ("reread", "")),
        ("m.py", [], 0, ("no_function", "")),
        ("", [], 0, ("no_function", "")),
    ],
)
def test_the_remedy_is_one_function_or_says_why_none(target, unpinned, count, expected):
    assert order_remedy(target, unpinned, count) == expected


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "m.py").write_text(_SRC)
    return tmp_path


def _ledger(root, verb, target):
    append(
        str(root),
        {
            "v": 1,
            "verb": verb,
            "target": target,
            "args": {},
            "exit": 0,
            "refusal": None,
            "env": {"interpreter": "/py", "detective": "/d.py", "wesker": "/w.py", "version": "1"},
            "state": {"target_src": f"sha256:{verb}{target}", "suite": "", "inputs": "", "equivalents": ""},
            "outcome": [],
        },
    )


def _pin(root, func_key):
    record_certificate(str(root), func_key, "digest", "complete", "")


def test_a_plan_over_a_file_names_its_first_function(repo):
    _ledger(repo, "plan", "m.py")
    facts = red_facts(str(repo))
    assert facts["order"] == "taste_without_measurement"
    assert (facts["order_remedy"], facts["order_region"], facts["order_more"]) == (
        "converge_region",
        "m.py::double",
        1,
    )


def test_following_the_remedy_moves_it_to_the_next_unpinned_function(repo):
    _ledger(repo, "plan", "m.py")
    _ledger(repo, "converge", "m.py::double")
    _pin(repo, "m.py::double")
    _ledger(repo, "plan", "m.py")
    facts = red_facts(str(repo))
    assert facts["order"] == "taste_before_behaviour"
    assert (facts["order_remedy"], facts["order_region"], facts["order_more"]) == (
        "converge_region",
        "m.py::triple",
        0,
    )


def test_a_file_whose_every_function_is_pinned_has_no_ordering_finding(repo):
    for fn in ("double", "triple"):
        _ledger(repo, "converge", f"m.py::{fn}")
        _pin(repo, f"m.py::{fn}")
    _ledger(repo, "plan", "m.py")
    assert red_facts(str(repo))["order"] == "ok"


def test_a_pin_is_read_where_converge_writes_it(repo):
    # A yellow command on ONE function: its certificate lives under tests/detective/, not the root.
    _ledger(repo, "converge", "m.py::double")
    _pin(repo, "m.py::double")
    assert (repo / "tests" / "detective" / "certificates.json").exists()
    assert not (repo / "certificates.json").exists()
    _ledger(repo, "decompose", "m.py::double")
    assert red_facts(str(repo))["order"] == "ok"


def test_a_package_names_a_function_inside_it(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(x):\n    return -x\n")
    _ledger(tmp_path, "plan", "pkg")
    facts = red_facts(str(tmp_path))
    assert (facts["order_remedy"], facts["order_region"]) == ("converge_region", "pkg/mod.py::f")


def _do_this(out: str) -> str:
    return next(line for line in out.splitlines() if "Do this" in line).split("Do this", 1)[1].strip()


def test_the_printed_prescription_is_a_converge_command_converge_accepts(repo, capsys):
    _ledger(repo, "plan", "m.py")
    main(["doctor", "--project-root", str(repo), "--red"])
    out = capsys.readouterr().out
    line = _do_this(out)
    assert line.startswith("detective converge 'm.py::double'")
    argv = shlex.split(line.split("#", 1)[0])
    parsed = _build_parser().parse_args(argv[1:])
    assert parsed.command == "converge"
    file, sep, function = parsed.target.partition("::")
    assert sep and file.endswith(".py") and function == "double"
    assert "1 more" in out


def test_a_path_with_no_function_prints_no_converge_command(tmp_path, capsys):
    (tmp_path / "empty").mkdir()
    _ledger(tmp_path, "plan", "empty")
    main(["doctor", "--project-root", str(tmp_path), "--red"])
    out = capsys.readouterr().out
    assert "detective converge" not in out
    assert "no function" in out
