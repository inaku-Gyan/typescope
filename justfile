set shell := ["bash", "-euo", "pipefail", "-c"]

python_sources := "src tests scripts"

default: check

# Format source and test code in place.
format:
    uv run ruff format {{python_sources}}
    uv run ruff check --fix {{python_sources}}

# Check formatting and lint rules without changing files.
lint:
    uv run ruff format --check {{python_sources}}
    uv run ruff check {{python_sources}}

# Run the project's static type checker.
typecheck:
    uv run pyrefly check src tests

# Run tests without coverage instrumentation.
test:
    uv run pytest

# Run tests, enforce the 70% baseline, and write the CI XML report.
testcov:
    uv run pytest --cov=typescope --cov-fail-under=70 --cov-report=term-missing --cov-report=xml:coverage.xml

# Build both the wheel and source distribution.
build:
    uv build --clear --out-dir dist

# Install both artifacts into isolated environments and run the public API smoke test.
verify-dist:
    uv run python scripts/verify_dist.py dist

# Validate an optional v<version> tag against metadata and built artifacts.
release-check tag="": build verify-dist
    uv run python scripts/release_check.py "{{tag}}"

# Run the same local gates used by CI, including distribution verification.
check: lint typecheck testcov build verify-dist

# Explicit alias for CI-equivalent local verification.
ci: check

clean:
    rm -rf .coverage .pytest_cache .ruff_cache coverage.xml dist htmlcov
