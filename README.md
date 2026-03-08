# 🩺 Docker Health Monitor

**Prometheus exporter + console status for Docker Compose stacks.**

Показывает здоровье, CPU, память, рестарты контейнеров. Авто-дискавер `docker-compose.yml`. Готов к Grafana dashboards.

---

<div align="center">

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?logo=python)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub repo](https://img.shields.io/github/stars/KernelGhost/docker-health-monitor?style=social)](https://github.com/KernelGhost/docker-health-monitor)

</div>

---

## ✨ Why this exists

Если у тебя дома/в тестовом стенде крутится `docker-compose.yml`, а хочешь видеть:

- ✅ Running / unhealthy / exited
- ⚡ CPU / RAM usage per service
- 🔄 Restart counts
- 📈 Графики в Grafana

— это инструмент. Ничего лишнего, только метрики.

---

## 🚀 Quick Start (3 commands)

```bash
# 1. Install (pipx recommended)
pipx install docker-health-monitor

# 2. Run HTTP exporter (scraped by Prometheus)
docker-health-monitor serve --compose-path /path/to/docker-compose.yml

# 3. Or just check status in terminal
docker-health-monitor status --compose-path /path/to/docker-compose.yml
```

**Пример вывода `status`:**
```
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━┓
┃ Service           ┃ State  ┃ CPU %    ┃ RAM   ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━┩
│ jellyfin          │ healthy│ 2.3      │ 450M  │
│ sonarr            │ healthy│ 0.4      │ 180M  │
│ radarr            │ healthy│ 0.6      │ 220M  │
│ qbittorrent       │ running│ 8.1      │ 1.2G  │
└───────────────────┴────────┴──────────┴───────┘
```

---

## 📊 Exposed Metrics (Prometheus)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `docker_compose_service_up` | gauge | `service` | 1 if running, 0 otherwise |
| `docker_compose_container_state` | gauge | `service`, `state` | 1 if container in given state (running, exited, unhealthy…) |
| `docker_compose_restart_count` | counter | `service` | How many times container restarted |
| `docker_compose_cpu_percent` | gauge | `service` | CPU usage % |
| `docker_compose_memory_bytes` | gauge | `service` | Memory usage in bytes |

**Prometheus config:**
```yaml
scrape_configs:
  - job_name: 'docker-compose'
    static_configs:
      - targets: ['localhost:8000']  # expose порт по умолчанию
```

---

## ⚙️ Configuration

### Option 1: YAML file (`.docker-health-monitor.yaml`)
```yaml
compose_path: "/opt/media/docker-compose.yml"  # если не указан — ищет в текущей dir и выше
interval: 30                                    # scrape interval в секундах
include_services: ["jellyfin", "sonarr"]       # только эти сервисы (опционально)
exclude_services: ["watchtower"]               # исключить эти сервисы
```

### Option 2: Environment variables
```bash
export DOCKER_HEALTH_COMPOSE_PATH="/opt/media/docker-compose.yml"
export DOCKER_HEALTH_INTERVAL=15
export DOCKER_HEALTH_INCLUDE_SERVICES="jellyfin,sonarr,radarr"
export DOCKER_HEALTH_EXCLUDE_SERVICES="watchtower"
```

---

## 🎨 Grafana Dashboard

Готовый JSON дашборд в файле [`grafana-dashboard.json`](grafana-dashboard.json).

**Что показывает:**
- 🟢/🔴 Service status (green/red)
- 📈 CPU Usage % (graph)
- 💾 Memory Usage (bytes)
- 🔄 Container Restarts (rate)
- 📋 Service States (table)

**Импорт:**
1. Открой Grafana → + → Import
2. Загрузи `grafana-dashboard.json` или paste JSON
3. Выбери Prometheus data source
4. Enjoy!

---

## 🐳 Run as a container

```bash
docker run -d \
  --name docker-health-monitor \
  -p 8000:8000 \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /path/to/docker-compose.yml:/compose.yml:ro \
  -e DOCKER_HEALTH_COMPOSE_PATH=/compose.yml \
  kernelghost/docker-health-monitor:latest
```

---

## 🛠️ Development

```bash
git clone https://github.com/KernelGhost/docker-health-monitor.git
cd docker-health-monitor

poetry install
poetry run pytest
poetry run docker-health-monitor status --compose-path ../your-compose.yml
```

**Project structure:**
```
docker-health-monitor/
├── src/docker_health_monitor/
│   ├── collector.py   # сбор метрик через Docker SDK
│   ├── exporter.py    # HTTP endpoint (/metrics) для Prometheus
│   ├── cli.py         # CLI (click): status, serve
│   └── __init__.py
├── tests/
├── Dockerfile
├── docker-compose.yml
├── grafana-dashboard.json
├── pyproject.toml
└── README.md
```

---

## 📦 CLI Reference

| Command | Description | Example |
|---------|-------------|---------|
| `status` | Print table of services | `docker-health-monitor status --compose-path ./docker-compose.yml` |
| `serve` | Run HTTP server exposing `/metrics` | `docker-health-monitor serve --port 8000 --interval 30` |
| `--help` | Show help | `docker-health-monitor --help` |

---

## 📜 License

MIT © [KernelGhost](https://github.com/KernelGhost)

---

## 🙋 Support

- Issues: https://github.com/KernelGhost/docker-health-monitor/issues
- Discussions: https://github.com/KernelGhost/docker-health-monitor/discussions
