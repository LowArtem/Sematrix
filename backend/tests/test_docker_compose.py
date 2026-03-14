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
    assert f"type: bind\n        source: {ollama_path}\n        target: /root/.ollama" in result.stdout
    assert result.stdout.count(f"source: {assets_path}") == 3
    assert result.stdout.count("target: /data/assets") == 3
