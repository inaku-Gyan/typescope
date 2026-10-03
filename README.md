# TypeScope

[![CI](https://github.com/inaku-Gyan/typescope/actions/workflows/ci.yml/badge.svg)](https://github.com/inaku-Gyan/typescope/actions/workflows/ci.yml)
[![coverage](https://img.shields.io/codecov/c/github/inaku-Gyan/typescope)](https://codecov.io/gh/inaku-Gyan/typescope)
[![pypi](https://img.shields.io/pypi/v/typescope.svg)](https://pypi.org/project/typescope/)
![support-version](https://img.shields.io/pypi/pyversions/typescope)
[![license](https://img.shields.io/github/license/inaku-Gyan/typescope)](https://github.com/inaku-Gyan/typescope/blob/master/LICENSE)
[![commit](https://img.shields.io/github/last-commit/inaku-Gyan/typescope)](https://github.com/inaku-Gyan/typescope/commits/master)

A library for runtime type-level assignability check.

## Development

Install the locked development environment with `uv sync --dev`. The supported local entry
points are:

- `just check` runs Ruff, Pyrefly, the 70% coverage gate, and distribution verification.
- `just test` runs the test suite without coverage instrumentation.
- `just testcov` writes the machine-readable `coverage.xml` report.
- `just build` creates the wheel and source distribution in `dist/`.
- `just verify-dist` installs both artifacts into isolated environments and runs an API smoke test.
- `just release-check v0.0.3` validates a version tag against the built metadata.

Releases are made from protected `v<version>` tags. GitHub Actions validates both artifacts before
publishing through PyPI Trusted Publishing (OIDC); ordinary branches and manual validation runs do
not publish packages.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
