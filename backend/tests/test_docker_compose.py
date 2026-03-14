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
