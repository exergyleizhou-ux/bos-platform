# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# BOS Pipeline v9.0 �� Makefile
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.DEFAULT_GOAL := help
SHELL := /bin/bash

# ���� Variables ����
COMPOSE := docker compose
BACKEND := $(COMPOSE) exec backend
FRONTEND := $(COMPOSE) exec frontend
DB := $(COMPOSE) exec db

# ���� Colors ����
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Docker Compose
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: up down restart logs ps build pull

up: ## Start all services
    @echo "$(GREEN)?? Starting BOS Pipeline...$(RESET)"
    $(COMPOSE) up -d
    @echo "$(GREEN)? Services started. API: http://localhost:8000 | Frontend: http://localhost:3000$(RESET)"

up-build: ## Start with rebuild
    @echo "$(GREEN)?? Building and starting...$(RESET)"
    $(COMPOSE) up -d --build

down: ## Stop all services
    @echo "$(RED)?? Stopping BOS Pipeline...$(RESET)"
    $(COMPOSE) down

down-v: ## Stop and remove volumes
    $(COMPOSE) down -v

restart: ## Restart backend
    @echo "$(YELLOW)?? Restarting backend...$(RESET)"
    $(COMPOSE) restart backend

restart-all: ## Restart all services
    $(COMPOSE) restart

logs: ## Tail all logs
    $(COMPOSE) logs -f

logs-backend: ## Tail backend logs
    $(COMPOSE) logs -f backend

logs-worker: ## Tail Celery worker logs
    $(COMPOSE) logs -f celery-worker

ps: ## Show running containers
    $(COMPOSE) ps

build: ## Build all images
    $(COMPOSE) build

pull: ## Pull latest images
    $(COMPOSE) pull

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Database
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: migrate migrate-create migrate-downgrade seed db-shell db-reset

migrate: ## Run Alembic migrations
    @echo "$(BLUE)?? Running migrations...$(RESET)"
    $(BACKEND) alembic upgrade head

migrate-create: ## Create new migration (usage: make migrate-create MSG="add users table")
    $(BACKEND) alembic revision --autogenerate -m "$(MSG)"

migrate-downgrade: ## Downgrade one migration
    $(BACKEND) alembic downgrade -1

migrate-history: ## Show migration history
    $(BACKEND) alembic history --verbose

seed: ## Seed demo data
    @echo "$(BLUE)?? Seeding demo data...$(RESET)"
    $(BACKEND) python -m scripts.seed_data

db-shell: ## Open PostgreSQL shell
    $(DB) psql -U bos -d bos_pipeline

db-reset: ## Reset database (drop + recreate + migrate + seed)
    @echo "$(RED)??  Resetting database...$(RESET)"
    $(DB) psql -U bos -c "DROP DATABASE IF EXISTS bos_pipeline;"
    $(DB) psql -U bos -c "CREATE DATABASE bos_pipeline;"
    $(BACKEND) alembic upgrade head
    $(BACKEND) python -m scripts.seed_data
    @echo "$(GREEN)? Database reset complete$(RESET)"

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Backend Testing
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: test test-cov test-fast test-verbose test-watch

test: ## Run backend tests
    @echo "$(BLUE)?? Running backend tests...$(RESET)"
    $(BACKEND) pytest

test-cov: ## Run tests with coverage
    @echo "$(BLUE)?? Running tests with coverage...$(RESET)"
    $(BACKEND) pytest --cov=app --cov-report=html --cov-report=term-missing

test-fast: ## Run tests (skip slow)
    $(BACKEND) pytest -m "not slow"

test-verbose: ## Run tests with verbose output
    $(BACKEND) pytest -v --tb=long

test-watch: ## Run tests in watch mode
    $(BACKEND) ptw -- --tb=short

test-integration: ## Run integration tests only
    $(BACKEND) pytest -m integration

test-chaos: ## Run chaos engineering tests
    $(BACKEND) pytest -m chaos

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Frontend Testing
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: test-frontend test-frontend-coverage

test-frontend: ## Run frontend Vitest tests
    @echo "$(BLUE)?? Running frontend Vitest tests...$(RESET)"
    cd frontend && npm run test

test-frontend-coverage: ## Run frontend tests with coverage
    @echo "$(BLUE)?? Running frontend tests with coverage...$(RESET)"
    cd frontend && npm run test:coverage

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# E2E Testing
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: e2e e2e-headed e2e-report

e2e: ## Run Playwright E2E tests
    @echo "$(BLUE)?? Running E2E tests...$(RESET)"
    cd e2e && npx playwright test

e2e-headed: ## Run E2E tests with browser visible
    cd e2e && npx playwright test --headed

e2e-report: ## Show E2E test report
    cd e2e && npx playwright show-report

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Load Testing
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: loadtest-k6 loadtest-k6-health loadtest-locust

loadtest-k6: ## Run k6 load test (SER endpoint)
    @echo "$(RED)?? Running k6 load test...$(RESET)"
    k6 run loadtest/k6_ser.js

loadtest-k6-health: ## Run k6 health check load test
    @echo "$(RED)?? Running k6 health check load test...$(RESET)"
    k6 run loadtest/k6_health.js

loadtest-locust: ## Run Locust load test (UI at http://localhost:8089)
    @echo "$(RED)?? Running Locust load test...$(RESET)"
    cd loadtest && locust -f locustfile.py --host http://localhost:8000

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# All Tests
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: test-all

test-all: test test-frontend e2e ## Run ALL tests (backend + frontend + E2E)
    @echo "$(GREEN)? All tests passed$(RESET)"

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Linting & Formatting
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: lint lint-backend lint-frontend format format-backend format-frontend typecheck

lint: lint-backend lint-frontend ## Lint all code

lint-backend: ## Lint backend (ruff + mypy)
    @echo "$(BLUE)?? Linting backend...$(RESET)"
    $(BACKEND) ruff check app/
    $(BACKEND) mypy app/ --ignore-missing-imports

lint-frontend: ## Lint frontend (eslint)
    @echo "$(BLUE)?? Linting frontend...$(RESET)"
    cd frontend && npm run lint

format: format-backend format-frontend ## Format all code

format-backend: ## Format backend (black + ruff)
    $(BACKEND) black app/ tests/
    $(BACKEND) ruff check app/ --fix

format-frontend: ## Format frontend (prettier)
    cd frontend && npm run format

typecheck: ## TypeScript type checking
    cd frontend && npm run typecheck

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Storybook
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: storybook storybook-build

storybook: ## Start Storybook on http://localhost:6006
    @echo "$(BLUE)?? Starting Storybook...$(RESET)"
    cd frontend && npm run storybook

storybook-build: ## Build static Storybook
    @echo "$(BLUE)?? Building static Storybook...$(RESET)"
    cd frontend && npm run build-storybook

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Documentation
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: docs docs-build

docs: ## Serve MkDocs locally
    @echo "$(BLUE)?? Serving docs at http://localhost:8001...$(RESET)"
    cd docs && mkdocs serve -a 0.0.0.0:8001

docs-build: ## Build static docs
    cd docs && mkdocs build

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Production Build
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: build-prod build-frontend

build-prod: ## Production build (backend + frontend)
    @echo "$(GREEN)???  Building for production...$(RESET)"
    $(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml build

build-frontend: ## Build frontend for production
    cd frontend && npm run build

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Deployment
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: deploy-staging deploy-prod

deploy-staging: ## Deploy to staging
    @echo "$(YELLOW)?? Deploying to staging...$(RESET)"
    helm upgrade --install bos-pipeline-staging ./helm/bos-pipeline \
        --namespace bos-staging --create-namespace \
        --values helm/bos-pipeline/values-staging.yaml

deploy-prod: ## Deploy to production
    @echo "$(GREEN)?? Deploying to production...$(RESET)"
    helm upgrade --install bos-pipeline ./helm/bos-pipeline \
        --namespace bos-production --create-namespace \
        --values helm/bos-pipeline/values-production.yaml

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Utilities
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: shell backend-shell redis-cli clean

shell: ## Open backend Python shell
    $(BACKEND) python

backend-shell: ## Open backend bash shell
    $(BACKEND) bash

redis-cli: ## Open Redis CLI
    $(COMPOSE) exec redis redis-cli

clean: ## Remove all build artifacts
    @echo "$(RED)?? Cleaning...$(RESET)"
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
    rm -rf frontend/dist frontend/dist-storybook frontend/coverage
    @echo "$(GREEN)? Clean complete$(RESET)"

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# OpenTelemetry Stack
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: up-otel

up-otel: ## Start with OpenTelemetry (Jaeger + Collector)
    @echo "$(BLUE)?? Starting with OpenTelemetry stack...$(RESET)"
    $(COMPOSE) -f docker-compose.yml -f docker-compose.otel.yml up -d
    @echo "$(GREEN)? Jaeger UI: http://localhost:16686$(RESET)"

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Help
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

.PHONY: help

help: ## Show this help message
    @echo ""
    @echo "$(BLUE)BOS Pipeline v9.0 �� Available Commands$(RESET)"
    @echo "�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T"
    @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
        awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
    @echo ""
