"""Prometheus metrics exporter."""

import logging
from datetime import datetime
from typing import Iterable, List

from prometheus_client import REGISTRY, Gauge, Counter, generate_latest

from .collector import ServiceMetrics

logger = logging.getLogger(__name__)

# Define metrics
SERVICE_UP = Gauge(
    "docker_compose_service_up",
    "Service availability (1=up, 0=down)",
    ["service"]
)
CONTAINER_STATE = Gauge(
    "docker_compose_container_state",
    "Container state (1 if in given state, else 0)",
    ["service", "state"]
)
RESTART_COUNT = Gauge(
    "docker_compose_restart_count",
    "Number of container restarts",
    ["service"]
)
CPU_PERCENT = Gauge(
    "docker_compose_cpu_percent",
    "CPU usage percentage",
    ["service"]
)
MEMORY_BYTES = Gauge(
    "docker_compose_memory_bytes",
    "Memory usage in bytes",
    ["service"]
)


class MetricsExporter:
    """Exports metrics in Prometheus text format."""

    def __init__(self):
        # Reset gauges on each scrape? Prometheus client accumulates; we'll set values each time.
        pass

    def update(self, metrics: Iterable[ServiceMetrics]):
        """Update Prometheus metrics from collected data."""
        # To avoid stale state labels, we need to reset all state gauges for each service before setting current state.
        # Define known Docker states (from Docker API). We'll reset for all services in current scrape.
        possible_states = ["running", "exited", "paused", "restarting", "unhealthy", "dead", "created", "removing"]
        # Collect service names from this scrape.
        service_names = [m.name for m in metrics]

        # Clear all state labels for these services.
        for svc in service_names:
            for st in possible_states:
                CONTAINER_STATE.labels(service=svc, state=st).set(0)

        # Set current values.
        for m in metrics:
            SERVICE_UP.labels(service=m.name).set(1 if m.up else 0)
            CONTAINER_STATE.labels(service=m.name, state=m.state).set(1)
            RESTART_COUNT.labels(service=m.name).set(m.restart_count)
            CPU_PERCENT.labels(service=m.name).set(m.cpu_percent)
            MEMORY_BYTES.labels(service=m.name).set(m.memory_bytes)

    def generate(self) -> bytes:
        """Generate Prometheus text exposition format."""
        return generate_latest(REGISTRY)