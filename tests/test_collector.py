"""Tests for DockerComposeCollector."""

import json
from unittest.mock import patch, MagicMock

import pytest

from docker_health_monitor.collector import DockerComposeCollector, ServiceMetrics


def fake_docker_ps(format_arg: str) -> str:
    # Simulate docker ps output
    if "{{.Names}}" in format_arg:
        return "testproj_service1_1\ntestproj_service2_1\n"
    return ""


def fake_docker_inspect(container: str) -> dict:
    # Return a minimal inspect structure
    return {
        "State": {
            "Running": True,
            "RestartCount": 1,
            "Status": "running",
        }
    }


def fake_docker_stats(container: str) -> str:
    if container == "testproj_service1_1":
        return "5.2%\t200MiB / 1GiB"
    elif container == "testproj_service2_1":
        return "0.1%\t100MiB / 2GiB"
    return ""


@patch("subprocess.run")
def test_collector_get_metrics(mock_run: MagicMock):
    # Mock subprocess.run calls in order:
    # 1. docker ps -a --format {{.Names}} (to list containers)
    # 2. docker ps -a --format {{.Names}} --filter name=testproj_service1
    # 3. docker inspect testproj_service1_1
    # 4. docker stats --no-stream for service1
    # 5. docker ps -a --filter name=testproj_service2
    # 6. docker inspect service2
    # 7. docker stats service2

    def run_side_effect(cmd, **kwargs):
        if "ps" in cmd and "--format" in cmd:
            if "{{.Names}}" in cmd:
                if "--filter" in cmd:
                    # filter calls
                    if "testproj_service1" in cmd:
                        return MagicMock(returncode=0, stdout="testproj_service1_1\n")
                    elif "testproj_service2" in cmd:
                        return MagicMock(returncode=0, stdout="testproj_service2_1\n")
                else:
                    # initial list
                    return MagicMock(returncode=0, stdout="testproj_service1_1\ntestproj_service2_1\n")
        elif "inspect" in cmd:
            return MagicMock(returncode=0, stdout=json.dumps(fake_docker_inspect(cmd[-1])))
        elif "stats" in cmd:
            container = cmd[-1]
            return MagicMock(returncode=0, stdout=fake_docker_stats(container))
        return MagicMock(returncode=1, stdout="")

    mock_run.side_effect = run_side_effect

    collector = DockerComposeCollector(compose_path=Path("/tmp/docker-compose.yml"))
    collector.project_name = "testproj"
    collector.services = ["service1", "service2"]

    metrics = collector.get_metrics()

    assert len(metrics) == 2
    m1 = metrics[0]
    assert m1.name == "service1"
    assert m1.container_name == "testproj_service1_1"
    assert m1.up is True
    assert m1.restart_count == 1
    assert m1.cpu_percent == 5.2
    assert m1.memory_bytes == 200 * 1024 * 1024

    m2 = metrics[1]
    assert m2.name == "service2"
    assert m2.up is True


def test_parse_memory():
    from docker_health_monitor.collector import DockerComposeCollector
    assert DockerComposeCollector._parse_memory("100MiB") == 100 * 1024 * 1024
    assert DockerComposeCollector._parse_memory("1GiB") == 1024 * 1024 * 1024
    assert DockerComposeCollector._parse_memory("512KiB") == 512 * 1024
    assert DockerComposeCollector._parse_memory("1024B") == 1024
    assert DockerComposeCollector._parse_memory("") == 0