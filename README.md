
# Sematrix

This repository starts with the MVP directory layout required by the project specification.

## Repository layout

- `backend/app/api` - FastAPI HTTP layer only
- `backend/app/core` - configuration, dependencies, and logging
- `backend/app/domain` - domain services and business logic
- `backend/app/infra` - repositories and local/external clients
- `backend/app/workers` - Celery entrypoints
- `backend/alembic` - database migrations
- `backend/tests` - backend test suite
- `frontend` - React SPA
- `scripts` - local utility scripts
- `infra` - container and deployment configuration

## Runtime scaffold

- `docker compose up --build` starts the current local stack baseline.
- The compose services are `postgres`, `redis`, `ollama`, `backend`, `worker`, `beat`, and `frontend`.
- The backend exposes a temporary health endpoint at `http://localhost:8000/api/health`.
- Docker publishes only the UI and API, and both are bound to `127.0.0.1` by default.
