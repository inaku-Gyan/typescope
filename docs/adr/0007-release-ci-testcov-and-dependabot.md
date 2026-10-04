# ADR-0007: Preserve release, CI, testcov, and dependency-update capabilities

## Status

Accepted

## Context

The old repository established a PyPI package and a visible coverage workflow, but its Makefile,
pre-commit setup, and release automation are not the implementation to preserve. The
reconstruction needs explicit acceptance criteria for artifacts, supported runtimes, CI quality
gates, coverage reports, OIDC publication, and dependency maintenance.

## Decision

### Package and support baseline

The package remains named `typescope` and the first reconstruction supports Python 3.11, 3.12,
and 3.13 on Linux, macOS, and Windows. A formal release produces both a wheel and a source
distribution. The wheel remains platform-independent while the implementation is pure Python.
Adding a newer Python version requires a separate compatibility check and matrix update.

The project metadata version is the sole build version source. Release tags use `v<version>` and
the release workflow rejects a tag whose version does not equal the built metadata version.
Published versions are immutable; a correction is a new version.

### CI and developer commands

The CI design has four responsibilities:

- **quality** runs Ruff and Pyrefly;
- **test** runs pytest on the 3 x 3 Python/platform matrix;
- **dist** builds both artifacts, checks metadata, installs each artifact in a clean environment,
  and runs an import/API smoke test;
- **publish** runs only for a protected version tag after test and dist succeed.

The repository's standard local entry points are `just check`, `just test`, `just testcov`,
`just build`, `just verify-dist`, and `just release-check`. The old Makefile and pre-commit
configuration are removed rather than treated as compatibility surfaces.

### Testcov

`just testcov` runs pytest with coverage for `typescope`, fails below 70%, prints a terminal
summary, and writes `coverage.xml`. Every test-matrix job enforces the threshold. The XML is
retained as a CI artifact; one designated job uploads it to Codecov to avoid duplicate reports.
Codecov transport or service failure is a warning and does not hide a test or threshold failure.
The version-controlled `codecov.yml` keeps project and patch status targets at the same 70%
minimum instead of inheriting a moving target from the previous commit's coverage.
HTML output is optional local convenience and is not a release gate.

### OIDC publication

Publication is triggered only by a protected `v<version>` tag. The publish job uses the minimum
`id-token: write` permission and PyPI Trusted Publishing/OIDC through a protected PyPI
environment. It does not use or read a PyPI API token. Ordinary branches, pull requests, and
manual validation runs never upload to PyPI. Before upload, the job validates both artifacts,
their metadata, clean installation, and the smoke test. A GitHub Release may record a successful
publication but is not a second distribution channel.

### Dependabot

The repository contains a version-controlled `.github/dependabot.yml` configuration using the
official `uv` and `github-actions` ecosystems. Both run weekly from the repository root. The uv
entry updates `pyproject.toml`/`uv.lock`; the actions entry updates workflow action references.
There is no parallel `pip` or `pre-commit` entry.

Patch and minor updates are grouped separately for Python dependencies and GitHub Actions;
major updates remain individual pull requests for review. A three-day cooldown applies to version
updates. Security updates may open independently. Dependabot pull requests use these labels:
`dependencies`, `dependencies:python`, and `dependencies:github-actions`; branches use the
`dependabot/<ecosystem>/...` namespace; commit/PR prefixes are `deps` and `deps-dev` with the
update scope included. Dependabot never creates release tags and has no OIDC publication
permission. Its pull requests must pass the normal quality, test, and distribution checks.

## Consequences

- PyPI wheel/sdist output, runtime support, and coverage reporting remain reviewable acceptance
  criteria while the old implementation and local workflow files can be discarded.
- OIDC and environment protection keep package publication separate from ordinary CI.
- Dependabot updates are recognizable and grouped without confusing maintenance branches with
  release tags.
- Codecov remains a visible report channel while tests and the 70% threshold remain the actual
  quality gate.
- The 70% threshold is a first-reconstruction minimum, not a permanent ceiling; raising it
  requires an explicit acceptance-standard update.

## Alternatives considered

- Preserve Makefile and pre-commit as compatibility layers: rejected because the new toolchain
  uses justfile, Ruff, and Pyrefly and no old developer interface is required.
- Publish from every successful branch: rejected because it would mix validation with an
  irreversible package action.
- Use a PyPI API token: rejected because Trusted Publishing/OIDC provides the intended protected
  release path.
- Configure both uv and pip in Dependabot: rejected because duplicate managers would create
  competing dependency PRs for the same Python project.
- Let Codecov transport failure determine test success: rejected because coverage threshold and
  report upload are separate capabilities.
