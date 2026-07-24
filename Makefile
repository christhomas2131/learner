# Learner — developer commands.
# Native equivalents (no Make) are documented in the README for Windows/macOS/Linux.

BACKEND := backend
FRONTEND := frontend
VENV := $(BACKEND)/.venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help install install-backend install-frontend dev backend frontend \
        migrate seed test test-backend test-frontend test-e2e lint format \
        typecheck build clean worker-list

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install backend + frontend deps

install-backend: ## Create venv and install backend (with dev extras)
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e "$(BACKEND)[dev]"

install-frontend: ## Install frontend deps
	cd $(FRONTEND) && npm install

backend: ## Run the backend API (http://localhost:8000)
	cd $(BACKEND) && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend: ## Run the frontend (http://localhost:3000)
	cd $(FRONTEND) && npm run dev

dev: ## Run backend + frontend together
	@echo "Starting backend and frontend…"
	@$(MAKE) -j2 backend frontend

migrate: ## Apply database migrations
	cd $(BACKEND) && .venv/bin/alembic upgrade head

seed: ## Seed demo data
	cd $(BACKEND) && .venv/bin/python -m app.cli seed

worker-list: ## List pending premium (Claude Code) questions
	cd $(BACKEND) && .venv/bin/python -m app.cli worker-list

test: test-backend test-frontend ## Run backend + frontend unit tests

test-backend: ## Run backend tests
	cd $(BACKEND) && .venv/bin/pytest -q

test-frontend: ## Run frontend unit tests
	cd $(FRONTEND) && npm run test

test-e2e: ## Run Playwright E2E tests (requires browsers: npx playwright install)
	cd $(FRONTEND) && npm run test:e2e

lint: ## Lint backend + frontend
	cd $(BACKEND) && .venv/bin/ruff check app
	cd $(FRONTEND) && npx eslint .

format: ## Format backend (ruff)
	cd $(BACKEND) && .venv/bin/ruff format app

typecheck: ## Type-check backend (mypy) + frontend (tsc)
	cd $(BACKEND) && .venv/bin/mypy app || true
	cd $(FRONTEND) && npx tsc --noEmit

build: ## Production build of the frontend
	cd $(FRONTEND) && npm run build

desktop: ## Launch the Electron desktop app (spawns backend + frontend in a window)
	cd desktop && npm install && npm start

clean: ## Remove caches, build output, and local databases
	rm -rf $(FRONTEND)/.next $(FRONTEND)/node_modules/.cache
	find $(BACKEND) -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -f $(BACKEND)/*.db
