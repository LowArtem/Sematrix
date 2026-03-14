from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_compose_defines_required_services() -> None:
    result = subprocess.run(
        ["docker", "compose", "config", "--services"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    services = set(result.stdout.splitlines())

    assert services == {
        "postgres",
        "redis",
        "ollama",
        "ollama-init",
        "backend",
        "worker",
        "beat",
        "frontend",
    }


def test_compose_publishes_frontend_and_backend_to_localhost_only() -> None:
    result = subprocess.run(
        ["docker", "compose", "config"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert 'host_ip: 127.0.0.1\n        target: 8000\n        published: "8000"' in result.stdout
    assert 'host_ip: 127.0.0.1\n        target: 80\n        published: "8080"' in result.stdout


def test_compose_uses_fixed_host_data_directories() -> None:
    result = subprocess.run(
        ["docker", "compose", "config"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    postgres_path = REPO_ROOT / "data" / "postgres"
    ollama_path = REPO_ROOT / "data" / "ollama"
    assets_path = REPO_ROOT / "data" / "assets"

    assert f"type: bind\n        source: {postgres_path}\n        target: /var/lib/postgresql/data" in result.stdout
    assert result.stdout.count(f"source: {ollama_path}") == 2
    assert result.stdout.count("target: /root/.ollama") == 2
    assert result.stdout.count(f"source: {assets_path}") == 3
    assert result.stdout.count("target: /data/assets") == 3


def test_compose_pins_ollama_gpu_and_stability_settings() -> None:
    result = subprocess.run(
        ["docker", "compose", "config"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "driver: nvidia" in result.stdout
    assert "capabilities:\n                - gpu" in result.stdout
    assert "count: -1" in result.stdout
    assert 'OLLAMA_FLASH_ATTENTION: "1"' in result.stdout
    assert "OLLAMA_KV_CACHE_TYPE: q8_0" in result.stdout
    assert 'OLLAMA_NUM_PARALLEL: "1"' in result.stdout
    assert 'OLLAMA_CONTEXT_LENGTH: "4096"' in result.stdout


def test_compose_initializes_required_ollama_models_before_model_clients_start() -> None:
    result = subprocess.run(
        ["docker", "compose", "config"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    scripts_path = REPO_ROOT / "scripts"

    assert "OLLAMA_HOST: http://ollama:11434" in result.stdout
    assert "OLLAMA_INIT_MODELS: qwen3.5:9b bge-m3" in result.stdout
    assert "- /scripts/ollama-init.sh" in result.stdout
    assert f"source: {scripts_path}" in result.stdout
    assert result.stdout.count("condition: service_completed_successfully") == 3


def test_frontend_runtime_builds_vite_bundle_and_proxies_api_prefix() -> None:
    dockerfile = (REPO_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    nginx_config = (REPO_ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")

    assert "FROM node:24-bookworm-slim AS build" in dockerfile
    assert "RUN npm run build" in dockerfile
    assert "COPY --from=build /app/frontend/dist /usr/share/nginx/html" in dockerfile
    assert "location /api/" in nginx_config
    assert "proxy_pass http://backend:8000/api/;" in nginx_config
    assert "try_files $uri $uri/ /index.html;" in nginx_config
