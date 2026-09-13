# Contributing

Issues and pull requests are welcome. For anything bigger than a small fix, open an issue first, so the
approach is agreed before the work is done.

Security problems go through the private channel in [SECURITY.md](./SECURITY.md), not an issue.

## Setup

Detective is developed alongside [Wesker](https://github.com/rohanvinaik/Wesker), its mutation engine.
For development, `uv` resolves Wesker from its `main` branch:

```bash
uv sync
```

To work on both at once, put local checkouts of both on `PYTHONPATH`; it takes precedence over the
installed copy:

```bash
export PYTHONPATH=/path/to/Detective:/path/to/Wesker
```

## Checks

CI runs these on every push; running them first saves a round trip.

```bash
uv run ruff check Detective tests
uv run ruff format --check .
uv run pytest
uvx zizmor@1.30.1 .     # when you touch .github/
```

The suite treats warnings as errors. A new warning is something to fix, not to silence.

`uvx pre-commit install` runs ruff and zizmor on every commit (see `.pre-commit-config.yaml`).

## Tests

Tests under `tests/detective/` are written by Detective itself. They are characterizations: they pin what
a function currently does. Regenerate them with `detective converge` rather than editing them by hand.

A generated test pins whatever the code does, bugs included, so every behaviour change also gets a
hand-written test that states the intended behaviour.

## Dependencies

The runtime surface is deliberately small: Wesker, pytest and ruff. A new dependency needs a reason in the
pull request.
