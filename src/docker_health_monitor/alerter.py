"""Alerting system for docker-health-monitor."""

import json
import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

import requests

from .collector import ServiceMetrics

logger = logging.getLogger(__name__)


class AlertStateManager:
    """Manages persistent state for deduplicating alerts (smart alerts).

    Stores last alert status per (service, metric, rule signature) to ensure
    notifications are sent only on state changes, not on every check while condition persists.
    """

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.states: Dict[str, Dict[str, Any]] = {}
        self.load()

    def _make_key(self, service: str, metric: str, rule: AlertRule) -> str:
        """Create a unique key for a rule + service."""
        # Include metric, threshold, comparison, for_states to distinguish different rules
        for_states_str = ",".join(sorted(rule.for_states)) if rule.for_states else ""
        parts = [service, metric, str(rule.threshold), rule.comparison, for_states_str]
        return "|".join(parts)

    def load(self):
        """Load state from file."""
        if not self.state_file.exists():
            self.states = {}
            return
        try:
            with open(self.state_file) as f:
                data = json.load(f)
            # Basic structure: {"states": {...}, "last_cleanup": "..."}
            self.states = data.get("states", {})
            # Optional: clean old entries (older than 30 days)
            last_cleanup = data.get("last_cleanup")
            now = datetime.utcnow()
            cutoff = now - timedelta(days=30)
            if last_cleanup:
                try:
                    last_dt = datetime.fromisoformat(last_cleanup)
                    if now - last_dt > timedelta(days=2):
                        self._purge_old_entries(cutoff)
                except Exception:
                    pass
            # Update last cleanup timestamp on load (we'll save after modifications)
        except Exception as e:
            logger.warning(f"Failed to load alert state: {e}. Starting fresh.")
            self.states = {}

    def _purge_old_entries(self, cutoff: datetime):
        """Remove entries older than cutoff."""
        to_remove = []
        for key, entry in self.states.items():
            try:
                updated = datetime.fromisoformat(entry.get("last_updated", ""))
                if updated < cutoff:
                    to_remove.append(key)
            except Exception:
                pass
        for key in to_remove:
            del self.states[key]
        if to_remove:
            logger.info(f"Purged {len(to_remove)} old alert state entries")

    def save(self):
        """Save state to file."""
        data = {
            "states": self.states,
            "last_cleanup": datetime.utcnow().isoformat()
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save alert state: {e}")

    def should_send(self, service: str, metric: str, value: float, rule: AlertRule, service_state: str) -> bool:
        """Return True if an alert should be sent (state change detection)."""
        key = self._make_key(service, metric, rule)
        entry = self.states.get(key)
        current_trigger = rule.matches(value, service_state)

        if current_trigger:
            if entry and entry.get("last_state") == "alerting":
                # Already in alert state, do not resend
                return False
            else:
                # New alert condition
                return True
        else:
            # Condition not met; if previously alerting, mark as recovered (but don't send alert)
            if entry and entry.get("last_state") == "alerting":
                # Mark as OK
                entry["last_state"] = "ok"
                entry["last_value"] = value
                entry["last_updated"] = datetime.utcnow().isoformat()
                # Save will happen later
            return False

    def record_sent(self, service: str, metric: str, value: float, rule: AlertRule):
        """Record that an alert was sent, updating state to 'alerting'."""
        key = self._make_key(service, metric, rule)
        self.states[key] = {
            "last_value": value,
            "last_state": "alerting",
            "last_updated": datetime.utcnow().isoformat()
        }

    def mark_recovered(self, service: str, metric: str, value: float, rule: AlertRule):
        """Explicitly mark a rule as recovered (optional, used by Alerter after non-trigger)."""
        key = self._make_key(service, metric, rule)
        if key in self.states:
            self.states[key]["last_state"] = "ok"
            self.states[key]["last_value"] = value
            self.states[key]["last_updated"] = datetime.utcnow().isoformat()


@dataclass
class AlertRule:
    """Threshold rule for a metric."""

    metric: str  # "cpu_percent", "memory_bytes", "restart_count"
    threshold: float  # threshold value
    comparison: str = ">"  # ">", ">=", "<", "<=", "==", "!="
    for_states: List[str] = None  # e.g., ["running"], None means all states

    def __post_init__(self):
        if self.for_states is None:
            self.for_states = []

    def matches(self, metric_value: float, service_state: str) -> bool:
        """Check if metric value triggers the rule."""
        if self.for_states and service_state not in self.for_states:
            return False
        if self.comparison == ">":
            return metric_value > self.threshold
        elif self.comparison == ">=":
            return metric_value >= self.threshold
        elif self.comparison == "<":
            return metric_value < self.threshold
        elif self.comparison == "<=":
            return metric_value <= self.threshold
        elif self.comparison == "==":
            return metric_value == self.threshold
        elif self.comparison == "!=":
            return metric_value != self.threshold
        return False


@dataclass
class NotificationChannel(ABC):
    """Base class for notification channels."""

    @abstractmethod
    def send(self, service: str, metric: str, value: float, threshold: float, state: str) -> bool:
        """Send alert notification. Returns success."""
        pass


@dataclass
class SlackChannel(NotificationChannel):
    """Slack notification via incoming webhook."""

    webhook_url: str
    username: str = "Docker Health Monitor"
    icon_emoji: str = ":warning:"
    channel: Optional[str] = None

    def send(self, service: str, metric: str, value: float, threshold: float, state: str) -> bool:
        try:
            text = f"*{service}* alert: {metric} = {value} (threshold {self.comparison} {threshold}), state: {state}"
            payload = {
                "text": text,
                "username": self.username,
                "icon_emoji": self.icon_emoji,
            }
            if self.channel:
                payload["channel"] = self.channel
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"Sent Slack alert for {service}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False


@dataclass
class DiscordChannel(NotificationChannel):
    """Discord notification via webhook."""

    webhook_url: str
    username: str = "Docker Health Monitor"

    def send(self, service: str, metric: str, value: float, threshold: float, state: str) -> bool:
        try:
            text = f"**{service}** alert: {metric} = {value} (threshold {self.comparison} {threshold}), state: {state}"
            payload = {
                "content": text,
                "username": self.username,
            }
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"Sent Discord alert for {service}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False


@dataclass
class TelegramChannel(NotificationChannel):
    """Telegram notification via bot."""

    bot_token: str
    chat_id: str
    parse_mode: str = "HTML"

    def send(self, service: str, metric: str, value: float, threshold: float, state: str) -> bool:
        try:
            text = f"<b>{service}</b> alert: {metric} = {value} (threshold {self.comparison} {threshold}), state: {state}"
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": self.parse_mode,
            }
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"Sent Telegram alert for {service}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False


@dataclass
class EmailChannel(NotificationChannel):
    """Email notification via SMTP."""

    smtp_host: str
    smtp_port: int = 587
    username: str = None
    password: str = None
    from_addr: str = None
    to_addrs: List[str] = None
    use_tls: bool = True

    def send(self, service: str, metric: str, value: float, threshold: float, state: str) -> bool:
        try:
            subject = f"[Alert] {service} - {metric} threshold exceeded"
            body = f"Service: {service}\nMetric: {metric}\nCurrent value: {value}\nThreshold: {self.comparison} {threshold}\nState: {state}\n"
            msg = MIMEText(body)
            msg["Subject"] = subject
            if self.from_addr:
                msg["From"] = self.from_addr
            if self.to_addrs:
                msg["To"] = ", ".join(self.to_addrs)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(msg)
            logger.info(f"Sent email alert for {service}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False


class Alerter:
    """Evaluates metrics against rules and sends notifications."""

    def __init__(self, rules: List[AlertRule], channels: List[NotificationChannel], state_manager: Optional[AlertStateManager] = None):
        self.rules = rules
        self.channels = channels
        self.state_manager = state_manager

    def check_and_alert(self, metrics: List[ServiceMetrics]) -> int:
        """Check all metrics against rules, send alerts for violations. Returns number of alerts sent."""
        alerts_sent = 0
        for m in metrics:
            for rule in self.rules:
                triggered = False
                if rule.metric == "cpu_percent" and rule.matches(m.cpu_percent, m.state):
                    triggered = True
                    metric_value = m.cpu_percent
                    metric_name = "CPU %"
                elif rule.metric == "memory_bytes" and rule.matches(m.memory_bytes, m.state):
                    triggered = True
                    metric_value = m.memory_bytes
                    metric_name = "Memory bytes"
                elif rule.metric == "restart_count" and rule.matches(m.restart_count, m.state):
                    triggered = True
                    metric_value = m.restart_count
                    metric_name = "Restart count"
                elif rule.metric == "up" and rule.matches(1 if m.up else 0, m.state):
                    triggered = True
                    metric_value = 0
                    metric_name = "Service down"
                else:
                    # No trigger for this rule; if we have state manager, mark as recovered if needed
                    if self.state_manager:
                        self.state_manager.mark_recovered(m.name, rule.metric, 0, rule)
                    continue

                if triggered:
                    # Smart alert: check if we should send based on state change
                    if self.state_manager and not self.state_manager.should_send(m.name, rule.metric, metric_value, rule, m.state):
                        continue  # skip duplicate
                    logger.warning(f"Alert triggered: {m.name} {metric_name} = {metric_value} (threshold {rule.comparison} {rule.threshold}), state: {m.state}")
                    for ch in self.channels:
                        if ch.send(m.name, metric_name, metric_value, rule.threshold, m.state):
                            alerts_sent += 1
                    if self.state_manager:
                        self.state_manager.record_sent(m.name, rule.metric, metric_value, rule)
                else:
                    # Not triggered; ensure state is ok
                    if self.state_manager:
                        self.state_manager.mark_recovered(m.name, rule.metric, 0, rule)
        # Save state after processing
        if self.state_manager:
            self.state_manager.save()
        return alerts_sent
