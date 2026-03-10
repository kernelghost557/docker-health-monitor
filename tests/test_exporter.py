"""Tests for MetricsExporter."""

from unittest.mock import patch
import pytest
from prometheus_client import REGISTRY

from docker_health_monitor.collector import ServiceMetrics
from docker_health_monitor.exporter import MetricsExporter


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear Prometheus registry before each test to avoid duplicate metric errors."""
    # Collect all collectors to unregister
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        REGISTRY.unregister(collector)
    yield
    # Clean up after test
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass


def test_exporter_update_sets_metrics():
    exporter = MetricsExporter()
    metrics = [
        ServiceMetrics(
            name="test_service",
            container_name="test_project_test_service_1",
            up=True,
            state="running",
            restart_count=2,
            cpu_percent=5.5,
            memory_bytes=1024 * 1024 * 512,  # 512 MiB
        )
    ]
    exporter.update(metrics)

    # Check gauge values
    from prometheus_client import Gauge, Counter

    # Find the metrics by name in registry
    # Since we cleared registry, we can fetch by constructing expected metric names
    # However easier: use collector's internal metrics objects? Not accessible.
    # We can check via generate output parsing.
    output = exporter.generate().decode("utf-8")
    assert 'docker_compose_service_up{service="test_service"} 1' in output
    assert 'docker_compose_container_state{service="test_service",state="running"} 1' in output
    assert 'docker_compose_restart_count{service="test_service"} 2.0' in output
    assert 'docker_compose_cpu_percent{service="test_service"} 5.5' in output
    assert 'docker_compose_memory_bytes{service="test_service"} 536870912.0' in output  # 512*1024*1024


def test_exporter_multiple_services():
    exporter = MetricsExporter()
    metrics = [
        ServiceMetrics(
            name="svc1",
            container_name="proj_svc1_1",
            up=True,
            state="running",
            restart_count=0,
            cpu_percent=1.0,
            memory_bytes=1024,
        ),
        ServiceMetrics(
            name="svc2",
            container_name="proj_svc2_1",
            up=False,
            state="exited",
            restart_count=5,
            cpu_percent=0.0,
            memory_bytes=0,
        ),
    ]
    exporter.update(metrics)
    output = exporter.generate().decode("utf-8")
    assert 'docker_compose_service_up{service="svc1"} 1' in output
    assert 'docker_compose_service_up{service="svc2"} 0' in output
    assert 'docker_compose_restart_count{service="svc2"} 5.0' in output


def test_restart_count_is_gauge_not_counter():
    """Ensure restart_count metric is a Gauge, not a Counter."""
    from docker_health_monitor.exporter import RESTART_COUNT
    assert isinstance(RESTART_COUNT, Gauge)
