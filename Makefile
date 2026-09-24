# research-institution development helpers.
#
# Common workflows:
#   make help                 - show available targets
#   make lint                 - run ruff check
#   make format               - apply ruff format
#   make typecheck            - run pyright strict
#   make test                 - run unit tests
#   make check-prime-directive - run the prime-directive grep (CI gate)
#   make clean                - delete __pycache__, *.pyc, tool caches, build artifacts
#
# Mirrors the Makefile shape in math/ and pi_monitor/ so the institution's
# four repos share a consistent developer surface.

.PHONY: help lint format typecheck test check-prime-directive clean

help:
	@echo "Targets:"
	@echo "  help                  - show this message"
	@echo "  lint                  - ruff check src tests research_institution"
	@echo "  format                - apply ruff format"
	@echo "  typecheck             - pyright strict"
	@echo "  test                  - pytest"
	@echo "  check-prime-directive - run prime-directive grep gate"
	@echo "  clean                 - delete __pycache__, *.pyc, tool caches, build artifacts"

lint:
	ruff check src tests research_institution

format:
	ruff format src tests research_institution

typecheck:
	pyright

test:
	pytest

check-prime-directive:
	bash scripts/check-prime-directive.sh

clean:
	@echo "Cleaning research-institution build artifacts..."
	rm -rf build/ dist/ .pytest_cache/ .ruff_cache/ .coverage htmlcov/ .mypy_cache/
	find . -type d -name __pycache__ -not -path '*/.venv/*' -not -path '*/.git/*' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -not -path '*/.venv/*' -not -path '*/.git/*' -delete
	@echo "Done. (.venv/ preserved.)"
