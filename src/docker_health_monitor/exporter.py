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
        # Reset previous values: we'll set all known labels to 0 first? Simpler: just set new values.
        # For Counter we add delta; for Gauges we set.
        # We'll accumulate counter increments across scrapes, so need to track previous values? 
        # Simpler: Counter we add diff; but for MVP just set() is okay for gauges, and inc for counter.
        # To avoid re-registering, we just set values on global metrics.
        for m in metrics:
            SERVICE_UP.labels(service=m.name).set(1 if m.up else 0)
            # Container state: set 1 for current state, 0 for others we care? We'll export multiple labels for each state.
            # For simplicity, expose one metric per service for its current state as value 1.
            # But Prometheus best: gauge with state label, set 1 if matches.
            CONTAINER_STATE.labels(service=m.name, state=m.state).set(1)
            # Zero out other states? Not necessary if using 'state' label - each combination is separate.
            RESTART_COUNT.labels(service=m.name).set(m.restart_count)
            CPU_PERCENT.labels(service=m.name).set(m.cpu_percent)
            MEMORY_BYTES.labels(service=m.name).set(m.memory_bytes)

    def generate(self) -> bytes:
        """Generate Prometheus text exposition format."""
        return generate_latest(REGISTRY)