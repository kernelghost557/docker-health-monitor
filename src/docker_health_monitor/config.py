"""Configuration for docker-health-monitor."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml

from .alerter import AlertRule, NotificationChannel, SlackChannel, DiscordChannel, TelegramChannel, EmailChannel


@dataclass
class AlertConfig:
    """Alerting configuration."""

    rules: List[AlertRule] = field(default_factory=list)
    channels: List[NotificationChannel] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "AlertConfig":
        """Load alert config from dictionary."""
        rules_data = data.get("rules", [])
        channels_data = data.get("channels", [])

        rules = []
        for r in rules_data:
            rule = AlertRule(
                metric=r["metric"],
                threshold=r["threshold"],
                comparison=r.get("comparison", ">"),
                for_states=r.get("for_states", []),
            )
            rules.append(rule)

        channels = []
        for c in channels_data:
            ctype = c.get("type")
            if ctype == "slack":
                channels.append(SlackChannel(
                    webhook_url=c["webhook_url"],
                    username=c.get("username", "Docker Health Monitor"),
                    icon_emoji=c.get("icon_emoji", ":warning:"),
                    channel=c.get("channel")
                ))
            elif ctype == "discord":
                channels.append(DiscordChannel(
                    webhook_url=c["webhook_url"],
                    username=c.get("username", "Docker Health Monitor")
                ))
            elif ctype == "telegram":
                channels.append(TelegramChannel(
                    bot_token=c["bot_token"],
                    chat_id=c["chat_id"],
                    parse_mode=c.get("parse_mode", "HTML")
                ))
            elif ctype == "email":
                channels.append(EmailChannel(
                    smtp_host=c["smtp_host"],
                    smtp_port=c.get("smtp_port", 587),
                    username=c.get("username"),
                    password=c.get("password"),
                    from_addr=c.get("from_addr"),
                    to_addrs=c.get("to_addrs", []),
                    use_tls=c.get("use_tls", True)
                ))
        return cls(rules=rules, channels=channels)


@dataclass
class DockerHealthConfig:
    """Main configuration."""

    compose_path: Optional[Path] = None
    interval: int = 30
    include_services: List[str] = field(default_factory=list)
    exclude_services: List[str] = field(default_factory=list)
    alert: AlertConfig = field(default_factory=AlertConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "DockerHealthConfig":
        """Load configuration from YAML file."""
        if config_path is None:
            # Search for config in current dir, home, etc.
            candidates = [
                Path.cwd() / ".docker-health-monitor.yaml",
                Path.cwd() / ".docker-health-monitor.yml",
                Path.home() / ".config" / "docker-health-monitor" / "config.yaml",
                Path.home() / ".docker-health-monitor.yaml",
            ]
            for p in candidates:
                if p.exists():
                    config_path = p
                    break
            else:
                # No config file found, return defaults
                return cls()
        else:
            # Allow string path
            config_path = Path(config_path)
        if not config_path.exists():
            return cls()
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        # Parse main sections
        compose_path_str = data.get("compose_path")
        compose_path = Path(compose_path_str) if compose_path_str else None
        interval = data.get("interval", 30)
        include_services = data.get("include_services", [])
        exclude_services = data.get("exclude_services", [])
        alert_data = data.get("alert", {})
        alert_config = AlertConfig.from_dict(alert_data)
        return cls(
            compose_path=compose_path,
            interval=interval,
            include_services=include_services,
            exclude_services=exclude_services,
            alert=alert_config,
        )
