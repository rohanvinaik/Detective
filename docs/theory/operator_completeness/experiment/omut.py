"""Runtime for the output-mutation experiment: a decorator that post-composes an output operator.

The transformed library source carries `@__omut__("module:Qual.name")` as the innermost decorator of every
candidate function. The decorator reads one configuration (env OMUT_CONFIG, a JSON file) and acts in one of
three modes:

  off     -- call through unchanged (the decorated copy must reproduce the pristine suite);
  record  -- call through, and log each returned value of every decorated function, per test;
  mutate  -- for the one target function, return p(f(x)) instead of f(x), where p is the configured
             output operator: a constant (`return c` on every return) or a point swap (r -> c, identity
             elsewhere). This is the uniform post-composition p o f of the paper's model (Definition 2.1).

Only the OUTERMOST call of a function is observed or mutated: a recursive call made from inside the original
body sees the unmutated function, so callers outside f see exactly p o f.

Values are compared by key: the type's qualified name and a hash of repr(value). Values whose repr embeds a
memory address are unkeyable and make the function ineligible (analysis excludes it).
"""

from __future__ import annotations

import base64
import builtins
import functools
import hashlib
import json
import os
import pickle
import threading

CURRENT_TEST: list[str] = [""]  # set by the pytest plugin before each test phase
_CFG: dict | None = None
_LOG = None
_local = threading.local()
_RECORD_CAP = 200  # per (function, test): stop logging after this many calls


def _config() -> dict:
    global _CFG
    if _CFG is None:
        path = os.environ.get("OMUT_CONFIG")
        cfg: dict = {"mode": "off"}
        if path:
            with open(path, encoding="utf-8") as fh:
                cfg = json.load(fh)
        _CFG = cfg
    return _CFG


def value_key(v) -> str | None:
    try:
        r = repr(v)
    except Exception:  # noqa: BLE001
        return None
    if " at 0x" in r or "object at" in r:
        return None
    t = type(v)
    return f"{t.__module__}.{t.__qualname__}:{hashlib.sha1(r.encode('utf-8', 'replace')).hexdigest()[:20]}"


_counts: dict = {}


def _record(name: str, v) -> None:
    global _LOG
    test = CURRENT_TEST[0]
    k = (name, test)
    n = _counts.get(k, 0)
    if n >= _RECORD_CAP:
        return
    _counts[k] = n + 1
    if _LOG is None:
        _LOG = open(_config()["log"], "a", encoding="utf-8")  # noqa: SIM115
    t = type(v)
    rec = {"fn": name, "test": test, "key": value_key(v), "type": f"{t.__module__}.{t.__qualname__}"}
    _LOG.write(json.dumps(rec) + "\n")
    _LOG.flush()


_FIRES = None


def _fired(cfg: dict) -> None:
    """Count applications of the operator, so a swap whose value never recurs is not read as undetected."""
    global _FIRES
    if _FIRES is None:
        _FIRES = open(cfg["fires"], "a", encoding="utf-8")  # noqa: SIM115
    _FIRES.write(CURRENT_TEST[0] + "\n")
    _FIRES.flush()


_decoded: dict = {}


def _operator_value(op: dict):
    k = id(op)
    if k not in _decoded:
        _decoded[k] = pickle.loads(base64.b64decode(op["value"]))
    return _decoded[k]


def omut(name: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            depth = getattr(_local, name, 0)
            setattr(_local, name, depth + 1)
            try:
                result = fn(*args, **kwargs)
            finally:
                setattr(_local, name, depth)
            if depth:  # an inner (recursive) call: the program f itself, unobserved
                return result
            cfg = _config()
            mode = cfg["mode"]
            if mode == "record":
                _record(name, result)
            elif mode == "mutate" and cfg["target"] == name:
                op = cfg["operator"]
                if op["kind"] == "const" or (op["kind"] == "swap" and value_key(result) == op["from_key"]):
                    _fired(cfg)
                    return _operator_value(op)
            return result

        return wrapper

    return deco


def install() -> None:
    builtins.__omut__ = omut  # type: ignore[attr-defined]
