# Paired 1.2.2 correction

## Why a new pair

Detective's published 1.2.1 tag failed macOS 3.14 CI because the input harvest retained
a sample after the aggregate deadline. Its producer checked time between tests, but
a worker could finish after the wall before its parent resumed. The earlier release
handoff relied on an older passing checkpoint and was premature. Later green CI on
documentation-only main did not resolve the race. Both 1.2.1 packages are already on PyPI.

## Candidate changes

Detective rejects late input/return observations and snapshots that cross the wall
during copy or repr. Setup/startup draw from the same absolute deadline, the remaining
join allowance is recomputed after startup, and a final-test overrun remains a named
cut. Timely partial inputs survive for their existing diagnostic/search purpose;
an incomplete codomain still refuses certification. The return-observation cache
policy changes so old observations cannot masquerade as the corrected contract.

The controlled-clock regressions fail on 1.2.1 without relying on sleep timing.
They cover late entry, partial retention, copy/repr overruns, late codomain, setup/startup
expiry and the remaining join allowance. Existing interrupt/containment obligations stay.
An additional startup/remaining-budget interrupt regression requires the started
worker to be reaped before the operator's interrupt propagates.

Wesker 1.2.2 retains the 1.2.1 engine implementation. Both release workflows now
refuse to build/sign artifacts unless push CI for the exact checked-out release commit
has completed successfully. A pending, missing, failed or wrong-commit run does not
satisfy that prerequisite; an older green run cannot mask a newer failed run.

Detective's published floor is Wesker>=1.2.2, a maintainer-directed pairing requirement,
and its development lock selects the exact pushed Wesker 1.2.2 commit.

## Required release sequence

1. Freeze and push the Wesker candidate, then update/sync Detective's exact dependency lock.
2. Freeze and push Detective's corrected candidate, including this release documentation.
3. Wait for the entire CI matrix and quality/security checks on each exact candidate SHA.
   A later passing parent/main run, a smoke test or an unfinished matrix is insufficient.
4. Create both 1.2.2 GitHub releases at those SHAs. Wait for both exact-CI guarded
   build/sign jobs and obtain their wheel/sdist assets with matching digests.
5. Install the candidate artifacts in clean managed environments and exercise the public
   workflow, then hand off the exact two-package PyPI upload packet together, Wesker first.
6. The owner performs the authenticated uploads. Verify the resulting ordinary-index
   installation separately; GitHub release publication is not PyPI publication.

This document is part of the frozen candidate, not a claim that later CI or publication
has already happened. Final run/commit/artifact identities belong in the GitHub release
receipt once observed, without moving tags or replacing already-published artifacts.

## Observed completion and publication

The exact Wesker commit is `60df89b86f4b35a8df2b03c850ebdb988d0e99af`;
Detective is `bf3f87b01bfe30246feb1a103de34463b5f5e32b`, locked to that Wesker
revision. Both complete six-cell 3.12–3.14 Linux/macOS CI matrices passed before
release creation: [Wesker 40077116370](https://github.com/rohanvinaik/Wesker/actions/runs/40077116370),
[Detective 40077952748](https://github.com/rohanvinaik/Detective/actions/runs/40077952748).
Packaging, workflow, CodeQL and SonarCloud checks passed. Both exact-CI guarded
build/sign runs succeeded: [Wesker 40078380799](https://github.com/rohanvinaik/Wesker/actions/runs/40078380799)
and [Detective 40078385460](https://github.com/rohanvinaik/Detective/actions/runs/40078385460).

Both 1.2.2 distributions were subsequently observed on PyPI; their hashes match
the GitHub release assets and clean-checkout candidate files:

| File | SHA256 |
| --- | --- |
| wesker-1.2.2-py3-none-any.whl | 848403927e22e8ec32f0698756a56133c5c95079a216a66ae20dc4954a7f8411 |
| wesker-1.2.2.tar.gz | 8a075f8eb59416a218441cb1ed616b1cb044196ac59866ef48ffb56bdc53218f |
| detective_spec-1.2.2-py3-none-any.whl | 96299335c5fde3681aa603acc98193a092ec50b78a6e72c86005a3a9355fd1e7 |
| detective_spec-1.2.2.tar.gz | f0a19456df1b2d719f42f4413e7c4c8d7357f263b873256e2107033ddab759d7 |

A fresh managed Python 3.14.7 environment installed both ordinary-index packages,
without local wheels, Git overrides or PYTHONPATH. Imports resolve site-packages.
The help → regime → converge shipping fixture reached COMPLETE (operator universe),
17/17 killed, three written tests and fresh isolated reproducibility confirmation.
It is characterization, not review of intended behavior. Full local output/report:
`~/Library/Logs/Detective/pause-2026-10-24/pypi-smoke/`.

The earlier upload attempt from this session lacked a token and sent no files;
the subsequent public-index observation establishes publication independently.
No further upload is needed. The [restart entry point](RESUME_PAIRED_REPAIR_2026-10-24.md)
preserves the remaining repair and certificate obligations.
