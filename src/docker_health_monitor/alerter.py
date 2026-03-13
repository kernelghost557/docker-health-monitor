"""Alerting system for docker-health-monitor."""

import json
import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

import requests

from .collector import ServiceMetrics

logger = logging.getLogger(__name__)


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

    def __init__(self, rules: List[AlertRule], channels: List[NotificationChannel]):
        self.rules = rules
        self.channels = channels

    def check_and_alert(self, metrics: List[ServiceMetrics]) -> int:
        """Check all metrics against rules, send alerts for violations. Returns number of alerts sent."""
        alerts_sent = 0
        for m in metrics:
            for rule in self.rules:
                if rule.metric == "cpu_percent" and rule.matches(m.cpu_percent, m.state):
                    logger.warning(f"Alert triggered: {m.name} CPU {m.cpu_percent}% {rule.comparison} {rule.threshold}%")
                    for ch in self.channels:
                        if ch.send(m.name, "CPU %", m.cpu_percent, rule.threshold, m.state):
                            alerts_sent += 1
                elif rule.metric == "memory_bytes" and rule.matches(m.memory_bytes, m.state):
                    logger.warning(f"Alert triggered: {m.name} Memory {m.memory_bytes} bytes {rule.comparison} {rule.threshold} bytes")
                    for ch in self.channels:
                        if ch.send(m.name, "Memory bytes", m.memory_bytes, rule.threshold, m.state):
                            alerts_sent += 1
                elif rule.metric == "restart_count" and rule.matches(m.restart_count, m.state):
                    logger.warning(f"Alert triggered: {m.name} Restarts {m.restart_count} {rule.comparison} {rule.threshold}")
                    for ch in self.channels:
                        if ch.send(m.name, "Restart count", m.restart_count, rule.threshold, m.state):
                            alerts_sent += 1
                elif rule.metric == "up" and rule.matches(1 if m.up else 0, m.state):
                    logger.warning(f"Alert triggered: {m.name} is down (up=0)")
                    for ch in self.channels:
                        if ch.send(m.name, "Service down", 0, rule.threshold, m.state):
                            alerts_sent += 1
        return alerts_sent
