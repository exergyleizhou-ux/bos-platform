.DEFAULT_GOAL := help
.RECIPEPREFIX := >
SHELL := /bin/bash

COMPOSE := docker compose
BACKEND := $(COMPOSE) exec backend
DB := $(COMPOSE) exec db

BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

.PHONY: up up-build down down-v restart restart-all logs logs-backend logs-celery ps build
.PHONY: migrate migrate-create migrate-history db-shell
.PHONY: test test-cov test-integration test-frontend test-contract test-code test-code-provider test-bos-mechanistic test-benchmarks test-benchmarks-runtime test-benchmarks-operator test-benchmarks-protocol test-benchmarks-release test-benchmarks-media generate-benchmark-docs check-benchmark-docs smoke-bos-mechanistic
.PHONY: lint lint-backend lint-frontend type-check
.PHONY: build-frontend up-otel shell backend-shell redis-cli clean help

up: ## Start the local development stack
> @printf "$(GREEN)Starting BOS Pipeline...$(RESET)\n"
> $(COMPOSE) up -d
> @printf "$(GREEN)Frontend: http://localhost:5173 | API: http://localhost:8000 | Proxy: http://localhost:8080$(RESET)\n"

up-build: ## Rebuild and start the local development stack
> @printf "$(GREEN)Building and starting BOS Pipeline...$(RESET)\n"
> $(COMPOSE) up -d --build

down: ## Stop the local development stack
> @printf "$(RED)Stopping BOS Pipeline...$(RESET)\n"
> $(COMPOSE) down

down-v: ## Stop the stack and remove volumes
> $(COMPOSE) down -v

restart: ## Restart the backend container
> $(COMPOSE) restart backend

restart-all: ## Restart every running service
> $(COMPOSE) restart

logs: ## Tail logs from all services
> $(COMPOSE) logs -f

logs-backend: ## Tail backend logs
> $(COMPOSE) logs -f backend

logs-celery: ## Tail Celery worker logs
> $(COMPOSE) logs -f celery

ps: ## Show service status
> $(COMPOSE) ps

build: ## Build Docker images
> $(COMPOSE) build

migrate: ## Run Alembic migrations in the backend container
> $(BACKEND) alembic upgrade head

migrate-create: ## Create a new Alembic migration (set MSG="...")
> $(BACKEND) alembic revision --autogenerate -m "$(MSG)"

migrate-history: ## Show Alembic migration history
> $(BACKEND) alembic history --verbose

db-shell: ## Open a PostgreSQL shell in the db container
> $(DB) psql -U bos -d bos_pipeline

test: ## Run backend tests
> $(BACKEND) pytest

test-cov: ## Run backend tests with coverage
> $(BACKEND) pytest --cov=app --cov-report=html --cov-report=term-missing

test-integration: ## Run backend integration tests
> $(BACKEND) pytest -m integration

test-frontend: ## Run frontend TypeScript test script
> cd frontend && npm run test

test-contract: ## Run frontend contract tests
> cd frontend && npm run test:contract

test-code: ## Run BOS Code backend integration tests
> $(BACKEND) pytest tests/integration/test_code_router.py -q

test-code-provider: ## Run BOS Code provider/unit tests
> $(BACKEND) pytest tests/unit/test_code_provider.py -q

test-bos-mechanistic: ## Run BOS mechanistic backend/frontend verification slices
> $(BACKEND) pytest tests/unit/test_bos_mechanistic_engine.py tests/unit/test_bos_supervisor_engine.py tests/unit/test_bos_report_service.py tests/integration/test_bos_router_live.py -q
> cd frontend && npm exec vitest run src/api/bosApi.test.ts src/lib/bos-read-model.test.ts src/components/bos/MechanisticContextCard.test.tsx src/components/bos/SignalSupervisorPanel.test.tsx

test-benchmarks: ## Run the BOS benchmark starter suite
> python scripts/bos_code_benchmark.py run

test-benchmarks-runtime: ## Run the runtime benchmark suite
> python scripts/bos_code_benchmark.py run --suite runtime

test-benchmarks-operator: ## Run the operator benchmark suite
> python scripts/bos_code_benchmark.py run --suite operator

test-benchmarks-protocol: ## Run the protocol benchmark suite
> python scripts/bos_code_benchmark.py run --suite protocol

test-benchmarks-release: ## Run the release benchmark suite
> python scripts/bos_code_benchmark.py run --suite release

test-benchmarks-media: ## Run the media benchmark suite
> python scripts/bos_code_benchmark.py run --suite media

generate-benchmark-docs: ## Regenerate benchmark README surfaces from task metadata
> python scripts/bos_code_benchmark.py generate-readme

check-benchmark-docs: ## Verify benchmark README surfaces are in sync with task metadata
> python scripts/bos_code_benchmark.py verify-docs

smoke-bos-mechanistic: ## Run the BOS mechanistic live smoke on Windows
> powershell -ExecutionPolicy Bypass -File scripts/run_bos_mechanistic_live_smoke.ps1

lint: lint-backend lint-frontend ## Run backend and frontend lint checks

lint-backend: ## Run Ruff and mypy for backend code
> $(BACKEND) ruff check app/
> $(BACKEND) mypy app/ --ignore-missing-imports

lint-frontend: ## Run frontend ESLint
> cd frontend && npm run lint

type-check: ## Run frontend TypeScript checking
> cd frontend && npm run type-check

build-frontend: ## Build the frontend bundle
> cd frontend && npm run build

up-otel: ## Start the stack with the OpenTelemetry overlay
> $(COMPOSE) -f docker-compose.yml -f docker-compose.otel.yml up -d
> @printf "$(GREEN)Jaeger UI: http://localhost:16686$(RESET)\n"

shell: ## Open a Python shell in the backend container
> $(BACKEND) python

backend-shell: ## Open a shell in the backend container
> $(BACKEND) sh

redis-cli: ## Open Redis CLI in the redis container
> $(COMPOSE) exec redis redis-cli

clean: ## Remove generated caches, logs, and local database files
> find . -type d -name __pycache__ -prune -exec rm -rf {} +
> find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.tsbuildinfo" -o -name "*.log" -o -name "*.db" -o -name "*.sqlite3" \) -delete
> rm -rf .pytest_cache backend/.pytest_cache backend/.mypy_cache frontend/dist frontend/coverage output

help: ## Show available commands
> @printf "\n$(BLUE)BOS Pipeline v9.0 command list$(RESET)\n"
> @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(RESET) %s\n", $$1, $$2}'
> @printf "\n"
