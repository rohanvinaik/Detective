"""The decorator_wrapper sentence prints a repair that works, or says none exists (Detective #77 item 4).

The defect: the page said "pin the undecorated callable (its __wrapped__)", which cannot work: the
install rebinds module names and `functools.wraps` keeps the original object, so a test of `__wrapped__`
enters no mutant. What moves it is a call by the module attribute; for a caller reaching the function only
through the wrapper's closure no repair exists until Wesker's robust install mode (Wesker#18).
"""

from Detective.validity import cut_reason_sentence

_REASON = "mutant_not_entered_decorator_wrapper"


def test_the_sentence_no_longer_recommends_pinning_the_wrapped_callable():
    sentence = cut_reason_sentence(_REASON)
    assert "pin the undecorated callable" not in sentence
    assert "does NOT move it" in sentence and "functools.wraps" in sentence


def test_the_sentence_names_the_repair_that_works_and_the_case_with_none():
    sentence = cut_reason_sentence(_REASON)
    assert "module.fn(...)" in sentence
    assert "no repair exists yet" in sentence and "Wesker#18" in sentence


def test_the_sentence_is_still_its_own_and_recognised():
    assert not cut_reason_sentence(_REASON).startswith("an unrecognised")
    assert cut_reason_sentence(_REASON) != cut_reason_sentence("mutant_not_entered_captured_at_import")
