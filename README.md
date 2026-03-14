
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
- The compose services are `postgres`, `redis`, `ollama`, `ollama-init`, `backend`, `worker`, `beat`, and `frontend`.
- The `ollama` service is configured for GPU passthrough and pins the required stability settings: `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_NUM_PARALLEL=1`, and `OLLAMA_CONTEXT_LENGTH=4096`.
- `ollama-init` waits for the Ollama API, then ensures the required MVP models `qwen3.5:9b` and `bge-m3` are pulled automatically before the backend and Celery services start.
- The backend exposes a temporary health endpoint at `http://localhost:8000/api/health`.
- Docker publishes only the UI and API, and both are bound to `127.0.0.1` by default.
- Persistent runtime data is bind-mounted under `./data/postgres`, `./data/ollama`, and `./data/assets`.
