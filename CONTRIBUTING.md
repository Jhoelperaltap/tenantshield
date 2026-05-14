# Contributing to TenantShield

Contributions are welcome under the workflow defined below. Every change — code, tests, docs — goes through the same gates.

## Getting Started

```sh
git clone <repo-url>
cd tenantshield
uv sync --all-extras --dev
uv run pre-commit install
```

The last command is required. It activates the local hooks so that your commits are validated before they leave your machine. Without it, the CI gate will be the first thing to tell you that a hook would have failed.

## Running Quality Gates

The full local battery:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pyright src/tenantshield
uv run pre-commit run --all-files
```

All commands must exit cleanly. Coverage must be ≥ 95% (the pytest gate enforces this automatically).

## Commit Convention

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/). The allowed types are:

- `feat` — new feature or public API addition.
- `fix` — bug fix.
- `chore` — repository maintenance, dependency bumps, tooling.
- `docs` — documentation changes only.
- `test` — tests only.
- `refactor` — code change that neither adds a feature nor fixes a bug.
- `perf` — performance improvement.
- `build` — build system, packaging, lockfile updates.
- `ci` — continuous integration configuration.

Examples:

- `feat(context): add tenant_scope async context manager`
- `fix(django): correct join detection across nullable FKs`
- `chore: bump ruff to 0.16.0`
- `docs: clarify deny-by-default semantics in README`
- `test: add property-based tests for scope nesting`
- `refactor(audit): extract sink interface into its own module`
- `perf(sqlalchemy): cache compiled tenant filter`
- `build: pin hatchling to 1.27`
- `ci: add matrix entry for Python 3.13`

## Pull Request Policy

- PRs are capped at 400 lines of diff. Larger changes must be explicit refactors and labelled as such in the PR description.
- Every PR includes tests. A bug fix without a regression test is rejected automatically.
- Coverage cannot decrease. The CI gate blocks PRs that lower it.
- `CHANGELOG.md` is updated under `[Unreleased]` in the same PR.
- Public API or workflow changes update the relevant docs in the same PR.
- `# TODO:` comments require an associated issue reference, e.g. `# TODO: ... (#123)`. Unreferenced TODOs are rejected.

## Attribution

All commits, pull requests, and contributions to this repository are attributed
exclusively to their human authors. AI-assisted tooling (code completion,
refactoring assistants, generation tools, etc.) is permitted as a productivity
aid, but tool usage MUST NOT be credited in commit trailers, PR descriptions,
or any other project artifact.

Contributions are the responsibility — and the work — of the human submitting them.
