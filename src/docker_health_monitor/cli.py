"""Command-line interface for docker-health-monitor."""

import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .collector import DockerComposeCollector
from .exporter import MetricsExporter

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
                    self.send_error(500, str(e))
            elif self.path == "/healthz":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_error(404, "Not Found")

        def log_message(self, fmt, *args):
            # Suppress logs
            pass

    console.print(f"[green]Starting server on http://0.0.0.0:{port}/metrics[/green]")
    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Server error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()