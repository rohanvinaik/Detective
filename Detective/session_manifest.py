"""One runner-derived description of the pytest session a proof was measured under (#58).

Detective reconstructs the pytest regime in at least five places — `regime.pytest_config`
mirrors precedence from the files on disk, `regime._pytest_table` parses the selected config,
`engine._suite_path` rebuilds the suite's import path from one pyproject dialect plus
root-conftest behaviour, `reachability._pytest_norecursedirs` reads only
`[tool.pytest.ini_options]`, and `reachability.module_name` derives a dotted name from a
root-relative path. Each was improved separately and each is still a MIRROR: a prediction of
what pytest would do, made from the same inputs but not by the same code.

A certificate has to name the regime and the exact test items that produced it. A prediction
cannot do that job, because the failure mode is precisely the case where the prediction and the
runner disagree — and the existing live check (`regime.pytest_configfile_live`) reads pytest's
own answer by REGEX-SCRAPING `--collect-only` stdout for a single field, at the cost of a
subprocess, which is why it is called only at `--migrate` and never on the measurement path.

THE IDENTITY RULE THIS MODULE ENFORCES: file origin is canonical; a dotted module name is an
ALIAS. Two files loaded under one name, or one file loaded under two names, is not a naming
curiosity — it is the shadowing condition `regime` already refuses a verdict over, because a
measurement attributed to the wrong copy of a function is a measurement of something else.
"""

from __future__ import annotations


def module_identity_conflicts(origins: dict[str, list[str]]) -> list[str]:
    """Module names that do not identify exactly one file, sorted (#58, pure — pinned).

    ``origins`` maps a dotted module name to every distinct file observed under it during the
    session. A well-formed session yields exactly one file per name; anything else means the
    import system resolved that name to different code at different moments, and every
    observation attributed to it is attributed to something the report cannot name.

    Returns the offending NAMES rather than a bool, because a caller has to say which one — a
    refusal that cannot name its cause sends the user to look at the whole suite. Sorted so two
    identical sessions cannot produce different reports.

    Empty lists count as conflict-free, not as conflicts: a name observed with no origin is a
    name nothing was attributed to, so there is nothing to misattribute. Duplicate spellings of
    ONE file are the caller's problem to canonicalise before calling — this compares what it is
    given, and treating `/var/x.py` and `/private/var/x.py` as two files here would report a
    conflict where there is only a symlink (the defect measured in Wesker #15).
    """
    return sorted(name for name, files in origins.items() if len(set(files)) > 1)
