PYTHON  := python3
VENV    := .venv
BIN     := $(VENV)/bin
PIP     := $(BIN)/pip
PYTEST  := $(BIN)/pytest
PYTHON_VENV := $(BIN)/python

.DEFAULT_GOAL := help

# ─── Setup ────────────────────────────────────────────────────────────────────

.PHONY: venv
venv:  ## Create virtual environment
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel

.PHONY: install
install: venv  ## Install all dependencies into venv
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

.PHONY: install-dev
install-dev: install  ## Install with dev/test extras
	$(PIP) install pytest pytest-asyncio pytest-cov respx httpx

# ─── Run ──────────────────────────────────────────────────────────────────────

.PHONY: run
run:  ## Start bot + terminal dashboard (paper mode)
	$(PYTHON_VENV) main.py run --paper

.PHONY: web
web:  ## Start bot + web dashboard at localhost:8080 (paper mode)
	$(PYTHON_VENV) main.py web --paper

.PHONY: both
both:  ## Start bot + terminal dashboard + web dashboard (paper mode)
	$(PYTHON_VENV) main.py both --paper

.PHONY: run-live
run-live:  ## Start bot in LIVE trading mode (real money — be careful)
	$(PYTHON_VENV) main.py run --live

.PHONY: web-live
web-live:  ## Start web dashboard in LIVE trading mode
	$(PYTHON_VENV) main.py web --live

# ─── Test ─────────────────────────────────────────────────────────────────────

.PHONY: test
test:  ## Run full test suite with coverage
	$(PYTEST) --cov=src/timefm_trader --cov-report=term-missing -v

.PHONY: test-unit
test-unit:  ## Run unit tests only
	$(PYTEST) tests/unit/ -v

.PHONY: test-integration
test-integration:  ## Run integration tests only
	$(PYTEST) tests/integration/ -v

.PHONY: test-fast
test-fast:  ## Run tests without coverage (faster)
	$(PYTEST) tests/ -v --no-cov

# ─── Lint / Format ────────────────────────────────────────────────────────────

.PHONY: lint
lint:  ## Run ruff linter
	$(BIN)/ruff check src/ tests/ main.py

.PHONY: format
format:  ## Auto-format with ruff
	$(BIN)/ruff format src/ tests/ main.py

.PHONY: typecheck
typecheck:  ## Run mypy type checker
	$(BIN)/mypy src/timefm_trader/ --ignore-missing-imports

# ─── Env ──────────────────────────────────────────────────────────────────────

.PHONY: env
env:  ## Copy .env.example to .env (fill in your keys)
	@if [ ! -f .env ]; then cp .env.example .env && echo ".env created — fill in your API keys"; \
	else echo ".env already exists"; fi

# ─── Clean ────────────────────────────────────────────────────────────────────

.PHONY: clean
clean:  ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov dist build *.egg-info

.PHONY: clean-venv
clean-venv: clean  ## Remove venv too (full reset)
	rm -rf $(VENV)

# ─── Help ─────────────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
