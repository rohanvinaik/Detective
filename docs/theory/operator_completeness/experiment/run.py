"""Orchestrate the output-mutation experiment for the paper's section 9.5.

For each pinned library (libs.json):
  1. setup     copy the pristine checkout, inject the decorator (transform.py), build a venv, install the
               library editable with its test dependencies, and make `__omut__` a builtin via a .pth file;
  2. baseline  run the project's own suite twice with the decorator OFF; a test is usable only if it passed
               both times (and the decorated copy is checked against the pristine copy the same way);
  3. record    run the suite once in RECORD mode: every returned value of every candidate, per test;
  4. sample    eligible functions = covered by a usable test, every observed value keyable, not all None;
               draw a seeded sample of at most `per_library`;
  5. mutate    per sampled function: one constant operator `return c` (c type-appropriate, chosen so that
               some observed output differs from c) and point swaps r -> c for observed r != c; each run
               executes only that function's covering usable tests.
All raw observations are written under results/<lib>/; analyze.py turns them into the paper's numbers.

Usage:  python run.py [--work DIR] [--workers N] [lib ...]
"""

from __future__ import annotations

import argparse
import base64
import collections
import gzip
import json
import os
import pickle
import random
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 20261106
PY = "3.12"


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def lib_paths(work: Path, lib: str) -> dict:
    base = work / lib
    return {
        "pristine": work / "src" / lib / "repo",
        "pristine_copy": base / "pristine",
        "mut": base / "mut",
        "venv": base / "venv",
        "scratch": base / "scratch",
        "results": HERE / "results" / lib,
    }


def setup(work: Path, lib: str, spec: dict) -> None:
    p = lib_paths(work, lib)
    if not p["pristine"].exists():
        p["pristine"].parent.mkdir(parents=True, exist_ok=True)
        sh(
            [
                "git",
                "-c",
                "advice.detachedHead=false",
                "clone",
                "-q",
                "--depth",
                "1",
                "--branch",
                spec["ref"],
                spec["repo"],
                str(p["pristine"]),
            ]
        )
    head = subprocess.run(
        ["git", "-C", str(p["pristine"]), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if head != spec["commit"]:
        raise SystemExit(f"{lib}: checkout is {head}, libs.json pins {spec['commit']}")
    if p["mut"].exists():
        shutil.rmtree(p["mut"])
    shutil.copytree(p["pristine"], p["mut"], ignore=shutil.ignore_patterns(".git"))
    p["results"].mkdir(parents=True, exist_ok=True)
    sh(
        [
            sys.executable,
            str(HERE / "transform.py"),
            str(p["mut"] / spec["package_dir"]),
            spec["module"],
            str(p["results"] / "candidates.json"),
        ]
    )
    if not p["venv"].exists():
        sh(["uv", "venv", "-q", "--python", PY, str(p["venv"])])
    py = str(p["venv"] / "bin" / "python")
    # the copy has no .git, so a VCS-derived version (setuptools-scm) is supplied from the pinned tag
    version = spec["ref"].lstrip("v")
    install_env = dict(os.environ, SETUPTOOLS_SCM_PRETEND_VERSION=version)
    sh(
        [
            "uv",
            "pip",
            "install",
            "-q",
            "--python",
            py,
            "-e",
            str(p["mut"]),
            *spec["test_deps"],
            "pytest-timeout==2.4.0",
        ],
        env=install_env,
    )
    site = subprocess.run(
        [py, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    Path(site, "omut_experiment.pth").write_text(f"{HERE}\nimport omut; omut.install()\n", encoding="utf-8")
    freeze = subprocess.run(
        ["uv", "pip", "freeze", "--python", py], capture_output=True, text=True, check=True
    ).stdout
    # the editable install line names this machine's work directory; record the library by its pin instead
    freeze = "\n".join(
        f"{lib} @ {spec['repo']}@{spec['commit']} (editable, decorated)" if ln.startswith("-e ") else ln
        for ln in freeze.splitlines()
    )
    (p["results"] / "environment.txt").write_text(freeze + "\n", encoding="utf-8")


def pytest_run(
    work: Path,
    lib: str,
    spec: dict,
    cfg: dict,
    select: list[str] | None,
    tag: str,
    timeout: int = 900,
    cwd: Path | None = None,
    fires_out: dict | None = None,
) -> list[dict]:
    """Run the project's suite (or the selected node ids) under `cfg`; return per-test outcome records."""
    p = lib_paths(work, lib)
    p["scratch"].mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f"{tag}-", dir=p["scratch"]))
    cfg_path, res_path, sel_path = tmp / "cfg.json", tmp / "results.jsonl", tmp / "select.txt"
    fires_path = tmp / "fires.txt"
    if cfg.get("mode") == "mutate":
        cfg = {**cfg, "fires": str(fires_path)}
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    env = dict(
        os.environ,
        OMUT_CONFIG=str(cfg_path),
        OMUT_RESULTS=str(res_path),
        OMUT_LIB_ROOT=str((cwd or p["mut"]) / spec["package_dir"]),
        PYTHONHASHSEED="0",
    )
    env.pop("PYTHONPATH", None)
    if cwd is not None:  # the pristine copy: import the library from it, not from the decorated install
        env["PYTHONPATH"] = str(cwd / Path(spec["package_dir"]).parent)
    if select is not None:
        sel_path.write_text("\n".join(select) + "\n", encoding="utf-8")
        env["OMUT_SELECT"] = str(sel_path)
    cmd = [
        str(p["venv"] / "bin" / "python"),
        "-m",
        "pytest",
        "-p",
        "omut_plugin",
        "-p",
        "no:cacheprovider",
        "-q",
        "--timeout=20",
        "-o",
        "addopts=",
        *spec["pytest_args"],
    ]
    try:
        subprocess.run(cmd, cwd=cwd or p["mut"], env=env, capture_output=True, timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    recs = []
    if res_path.exists():
        recs = [json.loads(ln) for ln in res_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if timed_out:
        seen = {r["test"] for r in recs}
        recs += [
            {"test": t, "outcome": "fail", "how": "crash", "exc": "RunTimeout"}
            for t in (select or [])
            if t not in seen
        ]
    if fires_out is not None:
        fires = fires_path.read_text(encoding="utf-8").splitlines() if fires_path.exists() else []
        fires_out["fired"] = len(fires)
        fires_out["fired_tests"] = len(set(fires))
    shutil.rmtree(tmp, ignore_errors=True)
    return recs


def baseline(work: Path, lib: str, spec: dict) -> list[str]:
    p = lib_paths(work, lib)
    runs = [pytest_run(work, lib, spec, {"mode": "off"}, None, f"base{i}") for i in range(2)]
    # The pristine control: an undecorated copy, plus any files the build generated in the decorated
    # copy (e.g. a setuptools-scm/hatch-vcs _version.py) that a bare checkout lacks.
    if p["pristine_copy"].exists():
        shutil.rmtree(p["pristine_copy"])
    shutil.copytree(p["pristine"], p["pristine_copy"], ignore=shutil.ignore_patterns(".git"))
    for f in p["mut"].rglob("*"):
        rel = f.relative_to(p["mut"])
        if "__pycache__" in rel.parts or f.suffix == ".pyc":
            continue
        if f.is_file() and not (p["pristine"] / rel).exists():
            (p["pristine_copy"] / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, p["pristine_copy"] / rel)
    pristine = pytest_run(work, lib, spec, {"mode": "off"}, None, "pristine", cwd=p["pristine_copy"])
    passed = [{r["test"] for r in run if r["outcome"] == "pass"} for run in runs]
    pristine_pass = {r["test"] for r in pristine if r["outcome"] == "pass"}
    usable = sorted(passed[0] & passed[1] & pristine_pass)
    summary = {
        "tests_collected": len({r["test"] for r in runs[0]}),
        "passed_run1": len(passed[0]),
        "passed_run2": len(passed[1]),
        "passed_pristine": len(pristine_pass),
        "usable": len(usable),
        "decorated_vs_pristine_disagreements": sorted(passed[0] ^ pristine_pass),
    }
    (p["results"] / "baseline.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (p["results"] / "usable_tests.txt").write_text("\n".join(usable) + "\n", encoding="utf-8")
    return usable


def record(work: Path, lib: str, spec: dict, usable: list[str]) -> Path:
    p = lib_paths(work, lib)
    log = p["results"] / "observations.jsonl"
    if log.exists():
        log.unlink()
    pytest_run(work, lib, spec, {"mode": "record", "log": str(log)}, usable, "record", timeout=1800)
    return log


CANDIDATE_CONSTANTS = {
    "builtins.int": [0, -999983],
    "builtins.float": [0.0, -999983.5],
    "builtins.str": ["", "<omut>"],
    "builtins.bool": [False, True],
    "builtins.list": [[], [None]],
    "builtins.tuple": [(), (None,)],
    "builtins.dict": [{}, {None: None}],
    "builtins.bytes": [b"", b"<omut>"],
    "builtins.set": [set(), {None}],
    "builtins.frozenset": [frozenset(), frozenset({None})],
}


def choose_constant(types: set[str], keys: set[str]):
    """A type-appropriate constant c with some observed output != c; returns (c, type_preserving)."""
    import omut  # noqa: PLC0415  (the experiment runtime, for value_key)

    if len(types) == 1:
        (t,) = types
        options = CANDIDATE_CONSTANTS.get(t, [])
        for c in options:  # prefer a constant outside the observed outputs
            if omut.value_key(c) not in keys:
                return c, True
        for c in options:  # else one inside, provided some other output differs from it
            if len(keys) > 1:
                return c, True
    return None, False


def sample(work: Path, lib: str, spec: dict, usable: list[str], log: Path) -> list[dict]:
    import omut  # noqa: PLC0415

    p = lib_paths(work, lib)
    usable_set = set(usable)
    obs = collections.defaultdict(lambda: {"tests": set(), "keys": {}, "types": set(), "unkeyable": False})
    for ln in log.read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        if r["test"] not in usable_set:
            continue
        o = obs[r["fn"]]
        o["tests"].add(r["test"])
        o["types"].add(r["type"])
        if r["key"] is None:
            o["unkeyable"] = True
        else:
            o["keys"][r["key"]] = True
    cands = json.loads((p["results"] / "candidates.json").read_text(encoding="utf-8"))
    eligibility = {}
    for c in cands:
        o = obs.get(c["name"])
        if o is None:
            eligibility[c["name"]] = "not covered"
        elif o["unkeyable"]:
            eligibility[c["name"]] = "unkeyable outputs"
        elif o["types"] == {"builtins.NoneType"}:
            eligibility[c["name"]] = "returns only None (out of model scope)"
        else:
            eligibility[c["name"]] = "eligible"
    eligible = sorted(n for n, e in eligibility.items() if e == "eligible")
    rng = random.Random(SEED)
    chosen = sorted(rng.sample(eligible, min(spec["per_library"], len(eligible))))
    plan = []
    for name in chosen:
        o = obs[name]
        c, preserving = choose_constant(o["types"], set(o["keys"]))
        ckey = omut.value_key(c)
        from_keys = sorted(k for k in o["keys"] if k != ckey)
        partial = len(from_keys) > spec["max_swaps"]
        if partial:
            from_keys = sorted(rng.sample(from_keys, spec["max_swaps"]))
        plan.append(
            {
                "fn": name,
                "tests": sorted(o["tests"]),
                "observed_keys": sorted(o["keys"]),
                "observed_types": sorted(o["types"]),
                "constant_repr": repr(c),
                "constant_key": ckey,
                "type_preserving": preserving,
                "swap_from": from_keys,
                "swaps_partial": partial,
                "constant_pickle": base64.b64encode(pickle.dumps(c)).decode("ascii"),
            }
        )
    (p["results"] / "eligibility.json").write_text(
        json.dumps(
            {
                "counts": collections.Counter(eligibility.values()),
                "eligible": len(eligible),
                "sampled": len(chosen),
                "seed": SEED,
                "by_function": eligibility,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    (p["results"] / "plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    return plan


def mutate(work: Path, lib: str, spec: dict, plan: list[dict], workers: int) -> None:
    p = lib_paths(work, lib)
    jobs = []
    for f in plan:
        jobs.append((f, {"kind": "const", "value": f["constant_pickle"]}, "const"))
        for k in f["swap_from"]:
            jobs.append((f, {"kind": "swap", "from_key": k, "value": f["constant_pickle"]}, f"swap:{k}"))

    def one(job):
        f, op, label = job
        fires: dict = {}
        recs = pytest_run(
            work,
            lib,
            spec,
            {"mode": "mutate", "target": f["fn"], "operator": op},
            f["tests"],
            "mut",
            timeout=600,
            fires_out=fires,
        )
        return {"fn": f["fn"], "operator": label, **fires, "tests": recs}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(one, jobs))
    with gzip.open(p["results"] / "mutants.jsonl.gz", "wt", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=str(Path.home() / ".cache" / "knowability-experiment"))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("libs", nargs="*")
    a = ap.parse_args()
    specs = json.loads((HERE / "libs.json").read_text(encoding="utf-8"))
    work = Path(a.work)
    sys.path.insert(0, str(HERE))
    for lib in a.libs or list(specs):
        spec = specs[lib]
        print(f"[{lib}] setup", flush=True)
        setup(work, lib, spec)
        print(f"[{lib}] baseline", flush=True)
        usable = baseline(work, lib, spec)
        print(f"[{lib}] record ({len(usable)} usable tests)", flush=True)
        log = record(work, lib, spec, usable)
        plan = sample(work, lib, spec, usable, log)
        with open(log, "rb") as src, gzip.open(log.with_suffix(".jsonl.gz"), "wb") as dst:
            shutil.copyfileobj(src, dst)
        log.unlink()
        print(f"[{lib}] mutate ({len(plan)} functions)", flush=True)
        mutate(work, lib, spec, plan, a.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
