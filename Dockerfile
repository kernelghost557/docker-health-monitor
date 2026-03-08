# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder

WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN pip install --no-cache-dir poetry && poetry install --no-dev --no-interaction --no-ansi

FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/local/lib /usr/local/lib
COPY src/ ./src/
COPY README.md .
RUN useradd -m -u 1000 monitor && chown -R monitor:monitor /app

USER monitor
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

ENTRYPOINT ["python", "-m", "docker_health_monitor"]
CMD ["serve"]