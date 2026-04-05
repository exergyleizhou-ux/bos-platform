# ?? BOS Pipeline v9.0

**Bioconversion Operating System** �� A production-grade, multi-tenant SaaS platform for insect bioconversion operations.

---

## Overview

BOS Pipeline is a full-stack scientific computing platform that provides:

- **34 Scientific Engines** �� SER, Monte Carlo, LCA, TEA, GHG, Water, Energy, Risk, Digital Twin, GP Calibration, Anomaly Detection, Flight Envelope, PID Control, and more
- **Multi-Tenant Architecture** �� PostgreSQL Row-Level Security (RLS) with tenant isolation
- **Role-Based Access Control** �� 5 roles: admin, scientist, operator, viewer, billing
- **Real-Time Monitoring** �� WebSocket streaming, OpenTelemetry distributed tracing, Sentry error tracking
- **Enterprise Features** �� Feature flags, API keys, webhooks, GDPR compliance, Stripe billing
- **Internationalization** �� 5 languages (EN, ZH, JA, DE, FR) with runtime switching

## Tech Stack

| Layer | Technology |
|:------|:-----------|
| Backend | FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Redis, Celery |
| Frontend | Vue 3, TypeScript, Pinia, Vue-i18n, ECharts, Storybook |
| Infrastructure | Docker, Helm 3, Kubernetes, ArgoCD, Nginx |
| Observability | OpenTelemetry, Jaeger, Prometheus, Grafana, Sentry |
| CI/CD | GitHub Actions, Playwright E2E, k6 + Locust load tests |

## Quick Start

### Prerequisites

- Docker & Docker Compose v2
- Node.js 18+ (for frontend development)
- Python 3.11+ (for backend development)

### Development (Docker Compose)

```bash
# Clone the repository
git clone https://github.com/your-org/bos-pipeline.git
cd bos-pipeline

# Copy environment variables
cp .env.example .env

# Start all services
make up

# Run database migrations
make migrate

# Seed demo data
make seed
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Storybook: http://localhost:6006 (run `make storybook`)

### Default Credentials

| Username | Password | Role |
|:---------|:---------|:-----|
| admin | admin123 | admin |
| scientist | sci123 | scientist |
| operator | op123 | operator |

## Project Structure

```
bos-pipeline/
������ backend/                 # FastAPI application
��   ������ app/
��   ��   ������ engine/          # 34 scientific computation engines
��   ��   ������ routers/         # API endpoints (~145 routes)
��   ��   ������ services/        # Business logic layer
��   ��   ������ tasks/           # Celery async tasks
��   ��   ������ telemetry/       # OpenTelemetry instrumentation
��   ��   ������ feature_flags/   # Feature flag service
��   ��   ������ models.py        # SQLAlchemy models
��   ��   ������ config.py        # Settings (pydantic)
��   ��   ������ main.py          # FastAPI app factory
��   ������ alembic/             # Database migrations
��   ������ tests/               # 70 test files
��   ������ scripts/             # Utility scripts
������ frontend/                # Vue 3 + TypeScript
��   ������ src/
��   ��   ������ components/      # 19 reusable components
��   ��   ������ pages/           # 27 page views
��   ��   ������ stores/          # 10 Pinia stores
��   ��   ������ i18n/            # 5 language files
��   ��   ������ stories/         # 14 Storybook stories
��   ��   ������ __tests__/       # 14 Vitest test files
��   ������ .storybook/          # Storybook configuration
������ helm/                    # Helm chart for Kubernetes
������ deploy/                  # Deployment configs
������ loadtest/                # k6 + Locust load tests
������ docs/                    # MkDocs documentation
������ e2e/                     # Playwright E2E tests
������ nginx/                   # Nginx reverse proxy config
������ monitoring/              # Prometheus + Grafana
������ .github/                 # CI/CD workflows
```

## Make Targets

```bash
make up              # Start Docker Compose stack
make down            # Stop stack
make restart         # Restart backend
make logs            # Tail logs
make migrate         # Run Alembic migrations
make seed            # Seed demo data
make test            # Run backend tests
make test-frontend   # Run frontend Vitest tests
make test-all        # Run all tests (backend + frontend + E2E)
make e2e             # Run Playwright E2E tests
make lint            # Lint backend + frontend
make format          # Format code
make loadtest-k6     # Run k6 load test
make loadtest-locust # Run Locust load test (UI)
make storybook       # Start Storybook dev server
make docs            # Serve MkDocs locally
make build           # Production build
make deploy-staging  # Deploy to staging
make deploy-prod     # Deploy to production
```

## API Documentation

Interactive API documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc) when the backend is running.

Key API groups:
- `/api/auth/` �� Authentication & user management
- `/api/batches/` �� Batch CRUD with pagination & filtering
- `/api/ser/` �� System Efficiency Ratio computation
- `/api/simulation/` �� Monte Carlo simulation
- `/api/ghg/` �� Greenhouse gas balance
- `/api/water/` �� Water footprint
- `/api/energy/` �� Energy balance
- `/api/tea/` �� Techno-economic analysis
- `/api/lca/` �� Life cycle assessment
- `/api/risk/` �� Contaminant risk assessment
- `/api/twin/` �� Digital twin management
- `/api/flight/` �� Flight envelope checks
- `/api/calibration/` �� Gaussian process calibration
- `/api/anomaly/` �� Anomaly detection
- `/api/admin/` �� Admin panel
- `/api/billing/` �� Stripe billing
- `/api/webhooks/` �� Webhook management
- `/api/api-keys/` �� API key management
- `/api/export/` �� Data export (CSV, JSON, XLSX, Parquet)
- `/api/gdpr/` �� GDPR compliance endpoints

## Testing

```bash
# Backend unit + integration tests
make test

# With coverage report
make test-cov

# Frontend tests
make test-frontend

# E2E tests
make e2e

# Load tests
make loadtest-k6
```

## Deployment

### Kubernetes (Helm)

```bash
helm install bos-pipeline ./helm/bos-pipeline \
  --namespace bos \
  --create-namespace \
  --values helm/bos-pipeline/values-production.yaml
```

### ArgoCD (GitOps)

```bash
kubectl apply -f deploy/argocd-app.yaml
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License �� see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Black Soldier Fly (BSF) research community
- FAO guidelines on insect farming
- EU Novel Food Regulation references
