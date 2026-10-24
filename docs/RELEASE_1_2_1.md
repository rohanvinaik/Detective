# Paired 1.2.1 release receipt

## Released source and changes

- [Wesker v1.2.1](https://github.com/rohanvinaik/Wesker/releases/tag/v1.2.1)
  targets `8aa2b4e9d9c00680bd7035e74127143a06aaa4d2`: discovery-before-local-mask
  setup preserves cold opcode observations beside a foreign start-event disabler.
  Stale-source tests retain the fingerprint contract across interpreter versions.
- [Detective v1.2.1](https://github.com/rohanvinaik/Detective/releases/tag/v1.2.1)
  targets `bc37d875e6ed3b63d5d23b73379aadf02d919515`: requires Wesker>=1.2.1,
  adds live README badges and records the shared repair plan. Its development lock
  follows Wesker `6de166d24318ae3cce27c60adfe00a77f8699ccb`, whose additional
  change is README badges/Action example documentation; runtime code is unchanged.

Both GitHub release workflows built and attached the wheel/sdist and Sigstore
bundles successfully. Creating those releases did not publish to PyPI. The owner
published 1.2.0 earlier; **1.2.1 still requires the maintainer upload below**.

## Evidence and limits

The runtime correction checkpoints passed both six-cell Python 3.12/3.13/3.14
Linux/macOS CI matrices: [Wesker 40074238464](https://github.com/rohanvinaik/Wesker/actions/runs/40074238464)
and [Detective 40074339034](https://github.com/rohanvinaik/Detective/actions/runs/40074339034).
Packaging, pinned lint/format and workflow checks passed. SonarCloud checks passed;
that does not disposition every historical issue or establish local Sonar acceptance.
Wesker's separate full self-specification workflow is not claimed complete here.

Local coverage runs: 1,079 Wesker tests passed; 3,862 Detective tests passed, with
three skips and one expected failure. The 66 focused budget tests and 25 broker/
fingerprint tests passed on both managed Python 3.12 and 3.14.

Fresh managed 3.12.12/3.14.7 environments installed the candidate wheels without
PYTHONPATH. Imports resolve site-packages and both versions read 1.2.1. On each,
help → clean regime → converge on the README shipping function reached
`COMPLETE (operator universe)`, 17/17 killed, three written tests, and fresh isolated
reproducibility confirmation. This is a characterized fixture, not universal proof.

Every package file matched its wheel member, and the installed wheels matched the
downloaded GitHub release wheels. Wheel metadata requires Python>=3.12 and a plain
`wesker>=1.2.1` requirement without a Git reference. Clean-worktree sdist tracked-file
checks and Twine checks passed. The pre-existing certificate-ledger worktree edit
was left untouched and excluded. No test was purged.

The [OpenSpec plan](../openspec/changes/complete-paired-repair/tasks.md) retains the
remaining containment, identity, count/operator, CLI, state, removal, performance
and quality obligations. A release receipt does not close an umbrella issue.

## Upload files

The local files are downloaded from the signed GitHub releases, not rebuilt from
the uncommitted working tree. Exact SHA256 values:

| File | SHA256 |
| --- | --- |
| wesker-1.2.1-py3-none-any.whl | f3af4f903577b6d5d69d057a637433b780f79c048b27236aac493b846fd32811 |
| wesker-1.2.1.tar.gz | f88e320c3fad9a859e3e7a131e038d71cd218efd8ce21c36d8d117d79b99e823 |
| detective_spec-1.2.1-py3-none-any.whl | a78f15cc458b6c447468e4b541402b4aa8e93247ca79c9742a3383cedad54aa0 |
| detective_spec-1.2.1.tar.gz | 7084dc5ba50980c4fd5619af9662a06f9aaba60d5f970ad20defb91efc4e9e3e |

Run in order, with the maintainer's PyPI credentials. The explicit filenames leave
the already-published 1.2.0 files out of the upload:

```bash
cd /Users/rohanvinaik/tools/Wesker && uvx --from twine twine upload dist/wesker-1.2.1.tar.gz dist/wesker-1.2.1-py3-none-any.whl
cd /Users/rohanvinaik/tools/Detective && uvx --from twine twine upload dist/detective_spec-1.2.1.tar.gz dist/detective_spec-1.2.1-py3-none-any.whl
```

After publication, record a fresh ordinary PyPI install and smoke run separately.
