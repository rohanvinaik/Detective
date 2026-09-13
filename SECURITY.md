# Security policy

## Reporting a vulnerability

Report security issues privately: open this repository's **Security** tab and choose **Report a
vulnerability** (<https://github.com/rohanvinaik/Detective/security/advisories/new>). Please don't open
a public issue for anything you believe is exploitable.

A useful report says what you ran, what happened, and what you expected; a minimal reproduction is best.
Detective is maintained by one person. Reports are answered as quickly as is realistic, and there is no
bug bounty.

## Supported versions

Fixes land on `main` and ship in the next release of `detective-spec`. Only the latest release is
supported.

## What Detective executes, by design

Detective runs the code you point it at. `diagnose`, `audit` and `converge` import the target module and
run that repository's test suite in-process, and Wesker compiles and executes mutants of the target
function. Running Detective on a repository therefore needs the same trust as running its tests: do not
point it at code you would not run.

What it writes:

- generated tests under the target repository's `tests/detective/`
- caches, ledgers, receipts and reports under `.detective/` and `.wesker/`
- the pytest configuration, when you run `regime --migrate`
- your source, only through `decompose --apply`, and only where the rewrite is proven
  behaviour-preserving

Neither Detective nor Wesker imports a network client.

In scope is anything beyond that: executing code outside the repository it was pointed at, writing outside
the places listed above, or sending data off the machine.
