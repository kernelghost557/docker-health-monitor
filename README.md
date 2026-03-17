# 🩺 Docker Health Monitor

**Prometheus exporter + console status + alerting for Docker Compose stacks.**

Показывает здоровье, CPU, память, рестарты контейнеров. Авто-дискавер `docker-compose.yml`. Готов к Grafana dashboards. Теперь с алертами через Slack, Telegram, Discord. Исправлена метрика `container_state` — теперь точное отображение состояний без накопления.

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

- ✅ Running / unhealthy / exited (точное состояние, без артефактов)
- ⚡ CPU / RAM usage per service
- 🔄 Restart counts
- 📈 Графики в Grafana
- 🚨 **Alerts** to Slack / Telegram / Discord when thresholds breached
- 📺 **Live watch mode** для непрерывного мониторинга прямо в терминале
- ⭐ **Favorites filter**: Мониторинг только избранных сервисов
- 🧠 **Smart alerts**: Алерты только при изменении состояния, без спама

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
      for_states: ["running"]
    - metric: memory_bytes
      threshold: 1073741824  # 1GB
      comparison: ">"
    - metric: restart_count
      threshold: 3
      comparison: ">="
    - metric: up
      threshold: 0
      comparison: "=="

  # Notification channels
  channels:
    - type: slack
      webhook_url: "https://hooks.slack.com/services/..."
      username: "Docker Bot"
      icon_emoji: ":rotating_light:"

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

# Optional filtering
include_services: []      # Only include these services (if empty, all)
exclude_services: []      # Exclude these services
favorite_services: []     # Mark services as favorites for special attention
favorites_only: false     # If true, monitor only favorites (ignores include/exclude)

# Smart alerts (state-change deduplication)
smart_alerts: false       # Send alerts only on state changes, not while condition persists
state_file: ""            # Path to store alert state (default: ~/.docker-health-monitor-state.json)
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
| `docker_compose_container_state` | gauge | `service`, `state` | 1 if container in given state (running, exited, unhealthy…). Исправлено: устаревшие состояния сбрасываются, метрика всегда отражает текущее состояние. |
| `docker_compose_restart_count` | gauge | `service` | How many times container restarted |
| `docker_compose_cpu_percent` | gauge | `service` | CPU usage % |
| `docker_compose_memory_bytes` | gauge | `service` | Memory usage in bytes |

**Prometheus config:**
```yaml
scrape_configs:
  - job_name: 'docker-compose'
    static_configs:
      - targets: ['localhost:8000']
```

---

## ⚙️ Configuration

### Option 1: YAML file (`.docker-health-monitor.yaml`)
```yaml
compose_path: "/opt/media/docker-compose.yml"
interval: 30
include_services: ["jellyfin", "sonarr"]   # optional filter
exclude_services: ["watchtower"]
favorite_services: ["jellyfin"]            # mark favorites
favorites_only: false                      # monitor only favorites?
smart_alerts: false                        # deduplicate alerts on state changes
state_file: ""                             # path for alert state (default: ~/.docker-health-monitor-state.json)
alert:
  rules: [...]
  channels: [...]
```

### Option 2: Environment variables
```bash
export DOCKER_HEALTH_COMPOSE_PATH="/opt/media/docker-compose.yml"
export DOCKER_HEALTH_INTERVAL=15
export DOCKER_HEALTH_INCLUDE_SERVICES="jellyfin,sonarr,radarr"
export DOCKER_HEALTH_EXCLUDE_SERVICES="watchtower"
export DOCKER_HEALTH_FAVORITE_SERVICES="jellyfin"
export DOCKER_HEALTH_FAVORITES_ONLY="false"
export DOCKER_HEALTH_SMART_ALERTS="false"
export DOCKER_HEALTH_STATE_FILE=""
```
Note: Alert config cannot be set via env vars; use YAML file.

---

## 🧠 Smart Alerts (Deduplication)

When `smart_alerts: true` is enabled, the monitor will send notifications only when an alert condition **starts** or **changes** (e.g., from OK to alerting). It will not resend the same alert on every check while the condition persists. This prevents notification spam.

A small state file (default `~/.docker-health-monitor-state.json`) keeps track of the last known state per rule. The state is automatically cleaned up after 30 days.

**How it works:**
- For each service + metric + rule, we remember the last value and whether it was alerting.
- If the rule is still triggered on the next run, no new alert is sent.
- When the metric returns to normal, the state is cleared, so the next trigger will fire again.
- If the monitor itself restarts, it uses the saved state to continue deduplication.

Enable it in config:

```yaml
smart_alerts: true
# optional custom path
state_file: "/path/to/state.json"
```

---

## 📺 Live Watch Mode

Use `watch` command for continuous monitoring with auto-refreshing table:

```bash
docker-health-monitor watch --compose-path /path/to/docker-compose.yml --interval 5
```

Press `Ctrl+C` to stop.

---

## 🎨 Grafana Dashboard

Готовый JSON дашборд в файле [`grafana-dashboard.json`](grafana-dashboard.json).

**Что показывает:**
- 🟢/🔴 Service status
- 📈 CPU Usage %
- 💾 Memory Usage
- 🔄 Container Restarts
- 📋 Service States

**Импорт:**
1. Grafana → + → Import
2. Загрузи `grafana-dashboard.json` или вставь JSON
3. Выбери Prometheus data source
4. Готово

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

To run monitor instead:
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

python3 -m venv .venv
. .venv/bin/activate
pip install -e .

pytest --cov
ruff check src tests
mypy src tests
```

### Project structure
```
docker-health-monitor/
├── src/docker_health_monitor/
│   ├── collector.py
│   ├── exporter.py
│   ├── alerter.py
│   ├── config.py
│   ├── cli.py
│   └── __init__.py
├── tests/
├── .github/workflows/ci.yml
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
| `monitor` | Check health and send alerts | `docker-health-monitor monitor --config .docker-health-monitor.yaml` |
| `watch` | Live monitoring with auto-refresh | `docker-health-monitor watch --interval 5` |
| `--help` | Show help | `docker-health-monitor --help` |

---

## 📜 License

MIT © [kernelghost557](https://github.com/kernelghost557)

---

## 🙋 Support

- Issues: https://github.com/kernelghost557/docker-health-monitor/issues
- Discussions: https://github.com/kernelghost557/docker-health-monitor/discussions
