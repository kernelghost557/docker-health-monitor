# Docker Health Monitor

Prometheus exporter for Docker Compose services. Monitors container health, restarts, CPU and memory usage.

## Features

- 🔍 Auto-discovers `docker-compose.yml` in current or specified directory
- 📊 Exposes Prometheus metrics on `/metrics` endpoint
- 🖥️ Rich console table view (`docker-health-monitor status`)
- 🎯 Tracks per-service: up/down, restart count, CPU%, memory
- ⚙️ Configurable via YAML or environment variables
- 🐳 Runs as a container itself (Dockerfile included)

## Quick Start

```bash
# Install
pipx install docker-health-monitor
# or
pip install docker-health-monitor

# Run HTTP server (scraped by Prometheus)
docker-health-monitor serve --compose-path /path/to/project

# Or just view status in terminal
docker-health-monitor status --compose-path /path/to/project
```

## Metrics Exposed

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `docker_compose_service_up` | gauge | `service` | 1 if container is running, 0 otherwise |
| `docker_compose_container_state` | gauge | `service`, `state` | 1 if container is in given state |
| `docker_compose_restart_count` | counter | `service` | Number of container restarts |
| `docker_compose_cpu_percent` | gauge | `service` | CPU usage percentage |
| `docker_compose_memory_bytes` | gauge | `service` | Memory usage in bytes |

## Configuration

Create `.docker-health-monitor.yaml`:

```yaml
compose_path: "/path/to/docker-compose.yml"  # optional, auto-discovered
interval: 30  # scrape interval in seconds
include_services: [" jellyfin", "sonarr"]  # optional filter
exclude_services: ["watchtower"]
```

Or environment variables:

```bash
DOCKER_HEALTH_COMPOSE_PATH=/path/to/docker-compose.yml
DOCKER_HEALTH_INTERVAL=30
```

## Integration with Prometheus

```yaml
scrape_configs:
  - job_name: 'docker-compose'
    static_configs:
      - targets: ['localhost:8000']
```

Grafana dashboard JSON is available in [`grafana-dashboard.json`](grafana-dashboard.json). Import it into Grafana to get a ready-made visualization:

- Service Status (green/red)
- CPU Usage % (graph)
- Memory Usage (bytes)
- Container Restarts (rate)
- Service States (table)

---

## Development

```bash
git clone https://github.com/KernelGhost/docker-health-monitor.git
cd docker-health-monitor
poetry install
poetry run pytest
poetry run docker-health-monitor status --compose-path /path/to/docker-compose.yml
```

## Development

```bash
git clone https://github.com/KernelGhost/docker-health-monitor.git
cd docker-health-monitor
poetry install
poetry run pytest
```

---

MIT © KernelGhost