"""Collector for Docker Compose service metrics."""

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class ServiceMetrics:
    """Metrics for a single Docker Compose service."""

    name: str
    container_name: str
    up: bool
    state: str  # running, exited, restarting, etc.
    restart_count: int
    cpu_percent: float
    memory_bytes: int


class DockerComposeCollector:
    """Collects metrics from Docker Compose project."""

    def __init__(self, compose_path: Optional[Path] = None):
        self.compose_path = compose_path
        self.project_name: Optional[str] = None
        self.services: list[str] = []

    def detect_project(self) -> str:
        """Determine Docker Compose project name."""
        if self.compose_path:
            # Project name is the directory containing docker-compose.yml
            self.project_name = self.compose_path.parent.name
        else:
            # Try to find docker-compose.yml in current or parent dirs
            cwd = Path.cwd()
            for p in [cwd, *cwd.parents]:
                cand = p / "docker-compose.yml"
                if cand.exists():
                    self.compose_path = cand
                    self.project_name = p.name
                    break
            if not self.project_name:
                # Fallback to directory name
                self.project_name = cwd.name
        return self.project_name

    def list_services(self) -> list[str]:
        """Get list of service names from docker-compose.yml."""
        if self.compose_path and self.compose_path.exists():
            import yaml
            data = yaml.safe_load(self.compose_path.read_text())
            self.services = list(data.get("services", {}).keys())
        else:
            # Fallback: infer from container names
            self.services = self._infer_services_from_containers()
        return self.services

    def _infer_services_from_containers(self) -> list[str]:
        """Get service names by listing containers with project prefix."""
        project = self.project_name or self.detect_project()
        # List containers (including stopped) with names starting with project_
        cmd = ["docker", "ps", "-a", "--format", "{{.Names}}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        services = set()
        for line in result.stdout.splitlines():
            name = line.strip()
            if name.startswith(f"{project}_"):
                # name format: project_service_1 or project_service
                parts = name[len(project)+1:].split("_")
                if parts:
                    # The service name is the first part(s) before the last segment (which is usually a number)
                    # Simple heuristic: take all parts except the last if the last is a digit
                    if parts[-1].isdigit():
                        service = "_".join(parts[:-1])
                    else:
                        service = "_".join(parts)
                    services.add(service)
        return sorted(services)

    def get_container_for_service(self, service: str) -> Optional[str]:
        """Find container name for a given service."""
        project = self.project_name or self.detect_project()
        # Exact match first
        exact = f"{project}_{service}"
        # Check if container exists
        cmd = ["docker", "ps", "-a", "--format", "{{.Names}}", "--filter", f"name={exact}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        names = [n.strip() for n in result.stdout.splitlines() if n.strip()]
        if names:
            return names[0]
        # Try with trailing _1
        alt = f"{exact}_1"
        cmd2 = ["docker", "ps", "-a", "--format", "{{.Names}}", "--filter", f"name={alt}"]
        result2 = subprocess.run(cmd2, capture_output=True, text=True)
        names2 = [n.strip() for n in result2.stdout.splitlines() if n.strip()]
        if names2:
            return names2[0]
        return None

    def inspect_container(self, container_name: str) -> dict:
        """Get detailed inspect data."""
        cmd = ["docker", "inspect", container_name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        import json
        return json.loads(result.stdout)[0]

    def get_metrics(self) -> list[ServiceMetrics]:
        """Collect metrics for all services."""
        project = self.detect_project()
        if not self.services:
            self.list_services()

        metrics_list = []
        for service in self.services:
            container_name = self.get_container_for_service(service)
            if not container_name:
                logger.debug(f"No container found for service {service}")
                continue

            try:
                inspect = self.inspect_container(container_name)
                state = inspect["State"]
                up = state["Running"]
                restart_count = state.get("RestartCount", 0)

                # CPU and Memory via `docker stats --no-stream`
                stats_cmd = ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}\t{{.MemUsage}}", container_name]
                stats_res = subprocess.run(stats_cmd, capture_output=True, text=True)
                cpu_percent = 0.0
                memory_bytes = 0
                if stats_res.returncode == 0 and stats_res.stdout.strip():
                    cpu_str, mem_str = stats_res.stdout.strip().split("\t")
                    # CPU: "0.05%" -> float
                    cpu_percent = float(cpu_str.strip().rstrip("%")) if cpu_str.strip() else 0.0
                    # Mem: "1.2MiB / 1GiB" -> parse used part
                    used_part = mem_str.split("/")[0].strip()
                    # Convert to bytes
                    memory_bytes = self._parse_memory(used_part)
            except Exception as e:
                logger.error(f"Failed to get metrics for {service}: {e}")
                up = False
                state_str = "error"
                restart_count = 0
                cpu_percent = 0.0
                memory_bytes = 0
            else:
                state_str = "running" if up else (state.get("Status", "exited").lower())

            metrics = ServiceMetrics(
                name=service,
                container_name=container_name,
                up=up,
                state=state_str,
                restart_count=restart_count,
                cpu_percent=cpu_percent,
                memory_bytes=memory_bytes,
            )
            metrics_list.append(metrics)
        return metrics_list

    @staticmethod
    def _parse_memory(mem_str: str) -> int:
        """Convert memory string (e.g., '1.2GiB', '500MiB', '1024B') to bytes."""
        mem_str = mem_str.strip()
        if not mem_str:
            return 0
        units = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4}
        # Extract number and unit
        match = re.match(r"([\d.]+)\s*([A-Za-z]*)", mem_str)
        if match:
            num, unit = match.groups()
            try:
                value = float(num)
                factor = units.get(unit, 1)
                return int(value * factor)
            except ValueError:
                return 0
        return 0