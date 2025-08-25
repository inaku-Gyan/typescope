.DEFAULT_GOAL := .all-checks

code_src = src tests


.PHONY: help  ## Display the help message
help:
	@grep -E \
		'^.PHONY: .*?## .*$$' $(MAKEFILE_LIST) | \
		sort | \
		awk 'BEGIN {FS = ".PHONY: |## "}; {printf "\033[36m%-19s\033[0m %s\n", $$2, $$3}'


.PHONY: .requires-uv  ## Ensure that uv is installed
.requires-uv:
	@uv -V || echo 'Please install uv: https://docs.astral.sh/uv/getting-started/installation/'


.PHONY: install  ## Install the dependencies for local development
install: .requires-uv
	uv sync --dev
	uv run pre-commit install


.PHONY: format  ## Auto-format python source files
format: .requires-uv
	uv run ruff check --fix $(code_src)
	uv run ruff format $(code_src)


.PHONY: lint  ## Lint python source files
lint: .requires-uv
	uv run ruff check $(code_src)
	uv run ruff format --check $(code_src)


.PHONY: typecheck  ## Perform type-checking
typecheck: .requires-uv
	uv run pyright $(code_src)


.PHONY: test  ## Run the test suite
test: .requires-uv
	uv run pytest


.PHONY: testcov  ## Run the test suite with coverage reporting
testcov: .requires-uv
	uv run pytest --cov=typescope


.PHONY: .all-checks  ## Run the standard set of checks performed in CI
.all-checks: typecheck lint test
	@echo "All checks passed!"


.PHONY: clean  ## Clean up all build artifacts and uninstall the package
clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]'`
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -f .coverage
	rm -rf htmlcov
	rm -f coverage.xml
	rm -rf build
	rm -rf dist
