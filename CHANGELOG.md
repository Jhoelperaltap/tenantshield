# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial repository scaffolding and toolchain configuration (Phase 0).
- Package skeleton with PEP 561 typing marker.
- Smoke test suite with coverage gate at 95%.
- Pre-commit hooks: file hygiene, ruff, mypy, bandit, codespell.

### Decision Records

The following decisions were made during Phase 0 execution and supersede or
clarify statements in `PHASE_0_KICKOFF.md`:

- **DR-001** — `pyproject.toml` `readme` and `[tool.hatch.version]` `path` require
  the referenced files to exist at any uv operation that resolves project metadata,
  including `uv lock`. `src/tenantshield/_version.py` and `README.md` were reclassified
  as build-time plumbing and created during Task 0.2 as minimal stubs, with their
  full content delivered in Tasks 0.3 and 0.6 respectively.
- **DR-002** — `__version__` in `_version.py` is declared without a type annotation
  (`__version__ = "0.0.1a0"`, not `__version__: str = "0.0.1a0"`). Hatchling's default
  regex source does not tolerate annotations, and the type is trivially inferable by
  mypy and pyright. The annotation added no value.
- **DR-003** — Commit signing (SSH/GPG) is deferred until before v0.5.0-alpha. The
  owner will configure local signing keys at that point. No retroactive signing of
  prior commits. ADR-0001 will document this decision formally when `docs/adr/` is
  established in Phase 1.
- **DR-004** — All commits, pull requests, issues, and project artifacts are
  attributed exclusively to human contributors. AI tooling is permitted but not
  credited in any project artifact. See `CONTRIBUTING.md` §Attribution.
- **DR-005** — Linter false positives on non-code content (legacy documentation in
  other languages, test fixtures, examples) are resolved by excluding the specific
  files in the tool's configuration, never by silencing the rule globally. First
  applied to `codespell` against `TENANTSHIELD_ROADMAP.md` in Task 0.5.
