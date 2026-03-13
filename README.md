# 🩺 Docker Health Monitor

**Prometheus exporter + console status + alerting for Docker Compose stacks.**

Показывает здоровье, CPU, память, рестарты контейнеров. Авто-дискавер `docker-compose.yml`. Готов к Grafana dashboards. Теперь с алертами через Slack, Telegram, Discord.

---

<div align="center">

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?logo=python)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub repo](https://img.shields.io/github/stars/kernelghost557/docker-health-monitor?style=social)](https://github.com/kernelghost557/docker-health-monitor)
[![CI](https://github.com/kernelghost557/docker-health-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/kernelghost557/docker-health-monitor/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/kernelghost557/docker-health-monitor/branch/main/graph/badge.svg)](https://codecov.io/gh/kernelghost557/docker-health-monitor)

</div>

---

## ✨ Why this exists

Если у тебя дома/в тестовом стенде крутится `docker-compose.yml`, а хочешь видеть:

- ✅ Running / unhealthy / exited
- ⚡ CPU / RAM usage per service
- 🔄 Restart counts
- 📈 Графики в Grafana
- 🚨 **Alerts** to Slack / Telegram / Discord when thresholds breached

— это инструмент. Ничего лишнего, только метрики и уведомления.

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

## 🚨 Alerts

You can configure alert thresholds and notification channels. Then run `docker-health-monitor monitor` periodically (cron) to check and send alerts.

### Configuration file (`.docker-health-monitor.yaml`)

```yaml
# Path to docker-compose.yml (optional, auto-detected if omitted)
compose_path: "/opt/media/docker-compose.yml"

# Alerting rules
alert:
  rules:
    - metric: cpu_percent
      threshold: 80.0
      comparison: ">"
      # optional: only alert when service is in these states
      for_states: ["running"]
    - metric: memory_bytes
      threshold: 1073741824  # 1GB in bytes
      comparison: ">"
    - metric: restart_count
      threshold: 3
      comparison: ">="
    - metric: up
      threshold: 1
      comparison: "=="
      for_states: []  # if service is not up (up=0) triggers when comparison "==" 1 fails? Actually we'd check up==0 separately. Better: use metric "up" with threshold 0 and comparison "==" to alert when down.
      # Alternatively simpler: just check if up==0 via rule:
      # metric: up, threshold: 0, comparison: "=="
    # Example: alert if service is down:
    - metric: up
      threshold: 0
      comparison: "=="

  # Notification channels
  channels:
    - type: slack
      webhook_url: "https://hooks.slack.com/services/..."
      username: "Docker Bot"
      icon_emoji: ":rotating_light:"
      # channel: "#alerts"  # optional, overrides webhook default

    - type: discord
      webhook_url: "https://discord.com/api/webhooks/..."
      username: "Docker Monitor"

    - type: telegram
      bot_token: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
      chat_id: "123456789"

    - type: email
      smtp_host: "smtp.gmail.com"
      smtp_port: 587
      username: "user@gmail.com"
      password: "app_password"
      from_addr: "monitor@example.com"
      to_addrs: ["admin@example.com"]
      use_tls: true
```

### Run monitor manually

```bash
docker-health-monitor monitor --config .docker-health-monitor.yaml
```

### Schedule with cron

```bash
# Every 5 minutes
*/5 * * * * docker-health-monitor monitor --config /opt/docker/.docker-health-monitor.yaml --json >/dev/null 2>&1
```

The `--json` flag suppresses table output when run from cron.

---

## 📊 Exposed Metrics (Prometheus)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `docker_compose_service_up` | gauge | `service` | 1 if running, 0 otherwise |
| `docker_compose_container_state` | gauge | `service`, `state` | 1 if container in given state (running, exited, unhealthy…) |
| `docker_compose_restart_count` | gauge | `service` | How many times container restarted (absolute value) |
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
alert:                                           # alert configuration as shown above
  rules: [...]
  channels: [...]
```

### Option 2: Environment variables
```bash
export DOCKER_HEALTH_COMPOSE_PATH="/opt/media/docker-compose.yml"
export DOCKER_HEALTH_INTERVAL=15
export DOCKER_HEALTH_INCLUDE_SERVICES="jellyfin,sonarr,radarr"
export DOCKER_HEALTH_EXCLUDE_SERVICES="watchtower"
```
Note: Alert config cannot be set via env vars yet; use YAML file.

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
  -v /path/to/.docker-health-monitor.yaml:/config.yaml:ro \
  -e DOCKER_HEALTH_COMPOSE_PATH=/compose.yml \
  -e DOCKER_HEALTH_CONFIG=/config.yaml \
  kernelghost/docker-health-monitor:latest
```

The container will run the exporter on port 8000. To run monitor instead, use:
```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /path/to/docker-compose.yml:/compose.yml:ro \
  -v /path/to/.docker-health-monitor.yaml:/config.yaml:ro \
  kernelghost/docker-health-monitor:latest monitor --config /config.yaml
```

---

## 🛠️ Development

```bash
git clone https://github.com/kernelghost557/docker-health-monitor.git
cd docker-health-monitor

# Install dependencies (venv)
python3 -m venv .venv
. .venv/bin/activate
pip install -e .

# Run tests
pytest --cov

# Lint
ruff check src tests

# Type checking
mypy src tests
```

### Project structure
```
docker-health-monitor/
├── src/docker_health_monitor/
│   ├── collector.py   # сбор метрик через Docker CLI
│   ├── exporter.py    # HTTP endpoint (/metrics) для Prometheus
│   ├── alerter.py     # проверка правил и отправка уведомлений
│   ├── config.py      # конфигурация (incl. alert)
│   ├── cli.py         # CLI (click): status, serve, monitor
│   └── __init__.py
├── tests/
│   ├── test_collector.py
│   ├── test_exporter.py
│   └── test_alerter.py   # coming soon
├── .github/workflows/ci.yml
├── Dockerfile
├── docker-compose.yml
├── grafana-dashboard.json
├── pyproject.toml
├── .pre-commit-config.yaml
└── README.md (this file)
```

---

## 📦 CLI Reference

| Command | Description | Example |
|---------|-------------|---------|
| `status` | Print table of services | `docker-health-monitor status --compose-path ./docker-compose.yml` |
| `serve` | Run HTTP server exposing `/metrics` | `docker-health-monitor serve --port 8000 --interval 30` |
| `monitor` | Check health and send alerts | `docker-health-monitor monitor --config .docker-health-monitor.yaml` |
| `--help` | Show help | `docker-health-monitor --help` |

---

## 📜 License

MIT © [kernelghost557](https://github.com/kernelghost557)

---

## 🙋 Support

- Issues: https://github.com/kernelghost557/docker-health-monitor/issues
- Discussions: https://github.com/kernelghost557/docker-health-monitor/discussions

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `docker_compose_service_up` | gauge | `service` | 1 if running, 0 otherwise |
| `docker_compose_container_state` | gauge | `service`, `state` | 1 if container in given state (running, exited, unhealthy…) |
| `docker_compose_restart_count` | gauge | `service` | How many times container restarted (absolute value) |
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
git clone https://github.com/kernelghost557/docker-health-monitor.git
cd docker-health-monitor

poetry install
poetry run pytest
poetry run docker-health-monitor status --compose-path ../your-compose.yml
```

### Quality checks

- **Linting:** `poetry run ruff check src tests`
- **Type checking:** `poetry run mypy src tests`
- **Tests with coverage:** `poetry run pytest --cov`
- **Pre-commit hooks:** After `pre-commit install`, hooks will run on commit (ruff, mypy, pytest).

### CI/CD

GitHub Actions workflow runs on every push and PR:
- Ruff linting
- Mypy type checking
- Pytest with coverage
- Upload coverage to Codecov

### Project structure
```
docker-health-monitor/
├── src/docker_health_monitor/
│   ├── collector.py   # сбор метрик через Docker CLI
│   ├── exporter.py    # HTTP endpoint (/metrics) для Prometheus
│   ├── cli.py         # CLI (click): status, serve
│   └── __init__.py
├── tests/
│   └── test_collector.py
├── .github/
│   └── workflows/
│       └── ci.yml
├── Dockerfile
├── docker-compose.yml
├── grafana-dashboard.json
├── pyproject.toml
├── .pre-commit-config.yaml
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

MIT © [kernelghost557](https://github.com/kernelghost557)

---

## 🙋 Support

- Issues: https://github.com/kernelghost557/docker-health-monitor/issues
- Discussions: https://github.com/kernelghost557/docker-health-monitor/discussions
