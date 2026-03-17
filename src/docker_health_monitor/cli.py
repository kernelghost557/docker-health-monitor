"""Command-line interface for docker-health-monitor."""

import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.live import Live
from rich.table import Table
from socketserver import ThreadingMixIn

from .collector import DockerComposeCollector
from .exporter import MetricsExporter
from .config import DockerHealthConfig
from .alerter import Alerter, AlertStateManager

console = Console()
logging.basicConfig(level=logging.INFO, format="%(message)s")


@click.group()
@click.version_option(package_name="docker-health-monitor")
def main():
    """Docker Health Monitor — Prometheus exporter for Docker Compose."""
    pass


@main.command()
@click.option("--compose-path", type=click.Path(path_type=Path), help="Path to docker-compose.yml")
@click.option("--json/--no-json", default=False, help="Output raw JSON instead of table")
def status(compose_path: Optional[Path], json: bool):
    """Show health status of Docker Compose services."""
    collector = DockerComposeCollector(compose_path=compose_path)
    try:
        metrics = collector.get_metrics()
    except Exception as e:
        console.print(f"[red]Error collecting metrics:[/red] {e}")
        sys.exit(1)

    if json:
        # Output as JSON lines
        for m in metrics:
            print(json.dumps({
                "service": m.name,
                "container": m.container_name,
                "up": m.up,
                "state": m.state,
                "restart_count": m.restart_count,
                "cpu_percent": m.cpu_percent,
                "memory_bytes": m.memory_bytes,
            }))
        return

    table = Table(title="Docker Compose Services")
    table.add_column("Service", style="cyan")
    table.add_column("Container", style="magenta")
    table.add_column("Up", justify="center")
    table.add_column("State", style="yellow")
    table.add_column("Restarts", justify="right")
    table.add_column("CPU %", justify="right")
    table.add_column("Memory", justify="right")

    for m in metrics:
        up_str = "[green]●[/green]" if m.up else "[red]○[/red]"
        state_color = "green" if m.up else "red"
        mem_mb = m.memory_bytes / (1024*1024)
        mem_str = f"{mem_mb:.1f} MiB"
        table.add_row(
            m.name,
            m.container_name,
            up_str,
            f"[{state_color}]{m.state}[/{state_color}]",
            str(m.restart_count),
            f"{m.cpu_percent:.2f}%",
            mem_str,
        )

    console.print(table)


@main.command()
@click.option("--compose-path", type=click.Path(path_type=Path), help="Path to docker-compose.yml")
@click.option("--port", default=8000, type=int, help="Port to listen on")
def serve(compose_path: Optional[Path], port: int):
    """Start HTTP server exposing Prometheus metrics."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    collector = DockerComposeCollector(compose_path=compose_path)
    exporter = MetricsExporter()

    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        """Handle requests in separate threads."""
        pass

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/metrics":
                try:
                    metrics = collector.get_metrics()
                    exporter.update(metrics)
                    data = exporter.generate()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; version=0.0.4")
                    self.end_headers()
                    self.wfile.write(data)
                except Exception as e:
                    logger.error(f"Error generating metrics: {e}")
                    self.send_error(500, str(e))
            elif self.path == "/healthz":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_error(404, "Not Found")

        def log_message(self, fmt, *args):
            # Suppress default logs; we'll use our own if needed
            pass

    console.print(f"[green]Starting server on http://0.0.0.0:{port}/metrics[/green]")
    server = ThreadedHTTPServer(("0.0.0.0", port), Handler)
    # Graceful shutdown on SIGTERM/SIGINT
    def signal_handler(signum, frame):
        console.print("\n[yellow]Received shutdown signal. Stopping server...[/yellow]")
        server.shutdown()
        console.print("[green]Server stopped.[/green]")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        server.serve_forever()
    except Exception as e:
        console.print(f"[red]Server error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.option("--compose-path", type=click.Path(path_type=Path), help="Path to docker-compose.yml")
@click.option("--interval", default=5, type=int, help="Refresh interval in seconds")
def watch(compose_path: Optional[Path], interval: int):
    """Continuously monitor services with live updating table."""
    collector = DockerComposeCollector(compose_path=compose_path)

    def make_table():
        try:
            metrics = collector.get_metrics()
        except Exception as e:
            table = Table(title=f"Error: {e}")
            return table

        table = Table(title=f"Docker Compose Services (live, refresh every {interval}s)")
        table.add_column("Service", style="cyan")
        table.add_column("Container", style="magenta")
        table.add_column("Up", justify="center")
        table.add_column("State", style="yellow")
        table.add_column("Restarts", justify="right")
        table.add_column("CPU %", justify="right")
        table.add_column("Memory", justify="right")

        for m in metrics:
            up_str = "[green]●[/green]" if m.up else "[red]○[/red]"
            state_color = "green" if m.up else "red"
            mem_mb = m.memory_bytes / (1024*1024)
            mem_str = f"{mem_mb:.1f} MiB"
            table.add_row(
                m.name,
                m.container_name,
                up_str,
                f"[{state_color}]{m.state}[/{state_color}]",
                str(m.restart_count),
                f"{m.cpu_percent:.2f}%",
                mem_str,
            )
        return table

    try:
        with Live(make_table(), refresh_per_second=1/interval, screen=True):
            while True:
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user[/yellow]")
        sys.exit(0)


@main.command()
@click.option("--compose-path", type=click.Path(path_type=Path), help="Path to docker-compose.yml")
@click.option("--config", "config_path", type=click.Path(path_type=Path), help="Path to config file")
@click.option("--json/--no-json", default=False, help="Output raw JSON instead of table")
def monitor(compose_path: Optional[Path], config_path: Optional[Path], json: bool):
    """Check service health and send alerts if thresholds exceeded."""
    # Load config
    cfg = DockerHealthConfig.load(config_path) if config_path else DockerHealthConfig()
    # Override compose_path from CLI if provided
    if compose_path:
        cfg.compose_path = compose_path

    collector = DockerComposeCollector(compose_path=cfg.compose_path)
    try:
        metrics = collector.get_metrics()
    except Exception as e:
        console.print(f"[red]Error collecting metrics:[/red] {e}")
        sys.exit(1)

    # Apply include/exclude filters
    if cfg.include_services:
        metrics = [m for m in metrics if m.name in cfg.include_services]
    if cfg.exclude_services:
        metrics = [m for m in metrics if m.name not in cfg.exclude_services]
    # Apply favorites filter
    if cfg.favorites_only and cfg.favorite_services:
        metrics = [m for m in metrics if m.name in cfg.favorite_services]

    # Show status table if not json
    if not json:
        table = Table(title="Docker Compose Services")
        table.add_column("Service", style="cyan")
        table.add_column("Container", style="magenta")
        table.add_column("Up", justify="center")
        table.add_column("State", style="yellow")
        table.add_column("Restarts", justify="right")
        table.add_column("CPU %", justify="right")
        table.add_column("Memory", justify="right")
        for m in metrics:
            up_str = "[green]●[/green]" if m.up else "[red]○[/red]"
            state_color = "green" if m.up else "red"
            mem_mb = m.memory_bytes / (1024*1024)
            mem_str = f"{mem_mb:.1f} MiB"
            table.add_row(
                m.name,
                m.container_name,
                up_str,
                f"[{state_color}]{m.state}[/{state_color}]",
                str(m.restart_count),
                f"{m.cpu_percent:.2f}%",
                mem_str,
            )
        console.print(table)

    # Check alerts
    if cfg.alert.rules and cfg.alert.channels:
        state_manager = None
        if cfg.smart_alerts:
            state_file = cfg.state_file or (Path.home() / ".docker-health-monitor-state.json")
            state_manager = AlertStateManager(state_file)
        alerter = Alerter(rules=cfg.alert.rules, channels=cfg.alert.channels, state_manager=state_manager)
        alerts_sent = alerter.check_and_alert(metrics)
        if alerts_sent > 0:
            console.print(f"[yellow]Sent {alerts_sent} alert notifications[/yellow]")
    else:
        console.print("[cyan]No alert rules or channels configured[/cyan]")


if __name__ == "__main__":
    main()