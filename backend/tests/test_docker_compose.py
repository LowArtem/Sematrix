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
