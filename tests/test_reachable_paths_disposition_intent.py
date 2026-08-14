"""`_reachable_paths` must CARRY why it chose its scope — not collapse three meanings into `None` (B2).

The old wrapper returned `None` for THREE unrelated reasons — no single target, a CRASHED static
analysis, and a deliberate "collect everything" — indistinguishably. That is the TEST_BASIS §14
conflation ("declined / computed / crashed must never be one value"), and a blanket crash-swallow of
exactly this shape has hidden a real defect before. Each reason now arrives as a named
`PathScope.disposition`, computed by the pinned pure decision `reachable_disposition`.

Hand-written from intent: the generated `*_synth.py` characterizes `reachable_disposition` (pins what
it does); these assert what `_reachable_paths` is *supposed* to do at the impure boundary.
"""

from Detective.cli import PathScope, _reachable_paths


def test_no_target_declines_without_analysis():
    scope = _reachable_paths("/repo", None)
    assert isinstance(scope, PathScope)
    assert scope.disposition == "declined_multi"
    assert scope.paths is None  # full collection, but for a NAMED reason


def test_two_targets_decline_without_analysis():
    scope = _reachable_paths("/repo", ["a.py", "b.py"])
    assert scope.disposition == "declined_multi"
    assert scope.paths is None


def test_a_raised_analysis_is_declined_error_not_a_silent_none(monkeypatch):
    """The load-bearing case: a crash degrades to full collection, but says so."""

    def boom(*args, **kwargs):
        raise RuntimeError("static analysis exploded")

    monkeypatch.setattr("Detective.reachability.reachable_test_paths", boom)
    scope = _reachable_paths("/repo", ["only.py"])
    assert scope.disposition == "declined_error"  # NOT "roots", NOT "declined_multi"
    assert scope.paths is None


def test_unnarrowed_analysis_is_roots(monkeypatch):
    monkeypatch.setattr("Detective.reachability.reachable_test_paths", lambda *a, **k: None)
    scope = _reachable_paths("/repo", ["only.py"])
    assert scope.disposition == "roots"
    assert scope.paths is None


def test_narrowed_analysis_is_scoped(monkeypatch):
    monkeypatch.setattr("Detective.reachability.reachable_test_paths", lambda *a, **k: ["tests/test_x.py"])
    scope = _reachable_paths("/repo", ["only.py"])
    assert scope.disposition == "scoped"
    assert scope.paths == ["tests/test_x.py"]


def test_all_four_dispositions_are_distinct():
    """The whole point of B2: the reasons are not one value."""
    assert len({"declined_multi", "declined_error", "roots", "scoped"}) == 4
