#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILES=(-f docker-compose.yml)
if [ "${USE_AMD64:-0}" = "1" ]; then
    COMPOSE_FILES+=(-f docker-compose.mac-amd64.yml)
fi

dc() {
    docker compose "${COMPOSE_FILES[@]}" "$@"
}

require_docker() {
    command -v docker >/dev/null 2>&1 || {
        echo "ERROR: docker not found. Install Docker Engine (Linux) or Docker Desktop (macOS)."
        exit 1
    }
    docker info >/dev/null 2>&1 || {
        echo "ERROR: Docker daemon is not running or current user has no access."
        echo "       Linux: sudo systemctl start docker; sudo usermod -aG docker \$USER (re-login)."
        exit 1
    }
    dc version >/dev/null 2>&1 || {
        echo "ERROR: Docker Compose v2 is required (docker compose, not docker-compose)."
        exit 1
    }
    [ -f .env ] || {
        echo "ERROR: .env not found in $ROOT"
        exit 1
    }
}

wait_healthy() {
    local svc="$1"
    local cid status
    for _ in $(seq 1 120); do
        cid="$(dc ps -q "$svc" 2>/dev/null || true)"
        if [ -n "$cid" ]; then
            status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo missing)"
            if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
                echo "[ok] $svc: $status"
                return 0
            fi
        fi
        sleep 3
    done
    echo "WARN: $svc did not become healthy in time"
    dc ps "$svc" || true
    return 1
}

wait_one_shot() {
    local svc="$1"
    local cid=""
    local status code
    for _ in $(seq 1 180); do
        cid="$(dc ps -a -q "$svc" 2>/dev/null || true)"
        [ -n "$cid" ] && break
        sleep 2
    done
    if [ -z "$cid" ]; then
        echo "ERROR: $svc container was not created"
        return 1
    fi
    # Let Compose actually start a stopped one-shot container before checking.
    sleep 2
    for _ in $(seq 1 600); do
        status="$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || echo missing)"
        if [ "$status" = "exited" ]; then
            code="$(docker inspect -f '{{.State.ExitCode}}' "$cid")"
            if [ "$code" != "0" ]; then
                echo "ERROR: $svc exited with code $code"
                dc logs --tail=120 "$svc" || true
                return 1
            fi
            echo "[ok] $svc: Exited (0)"
            return 0
        fi
        sleep 3
    done
    echo "ERROR: $svc did not finish in time"
    dc logs --tail=120 "$svc" || true
    return 1
}

wait_trino() {
    for _ in $(seq 1 120); do
        if dc exec -T trino curl -fsS http://localhost:8080/v1/info >/dev/null 2>&1; then
            echo "[ok] trino: ready"
            return 0
        fi
        sleep 3
    done
    echo "ERROR: Trino is not ready"
    dc logs --tail=100 trino || true
    return 1
}
print_access() {
    cat <<'EOF'

============================================================
  Project is ready (Linux/macOS)
============================================================
  Trino:        http://localhost:8081   trino / (empty)
                catalog=iceberg schema=analytics
  Airflow:      http://localhost:8080   admin / admin
  Superset:     http://localhost:8088   admin / admin
  MinIO:        http://localhost:9001   minioadmin / minioadmin
  Iceberg REST: http://localhost:8181
  Spark UI:     http://localhost:4040   (only while a Spark job runs)

  Check: docker compose ps -a
  Logs:  docker compose logs --tail=100 <service>
EOF
}