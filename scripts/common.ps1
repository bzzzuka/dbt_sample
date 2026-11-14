# Shared PowerShell helpers for Windows start scripts.
# Dot-source from scripts/windows/*.ps1:
#   . (Join-Path $PSScriptRoot "..\common.ps1")

$ErrorActionPreference = "Stop"

$script:ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $script:ProjectRoot

function Assert-Docker {
    $ErrorActionPreference = "Continue"

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "docker not found. Install Docker Desktop with WSL2 backend."
    }

    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker daemon is not running. Start Docker Desktop and wait for 'Running'."
    }

    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose v2 is required (use 'docker compose', not 'docker-compose')."
    }

    if (-not (Test-Path (Join-Path $script:ProjectRoot ".env"))) {
        throw ".env not found in $script:ProjectRoot"
    }
}

function Invoke-Compose {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$ComposeArgs
    )

    $ErrorActionPreference = "Continue"

    & docker compose @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($ComposeArgs -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Wait-Healthy {
    param(
        [string]$Service,
        [int]$Attempts = 120
    )

    $ErrorActionPreference = "Continue"

    for ($i = 0; $i -lt $Attempts; $i++) {
        $cid = @(& docker compose ps -q $Service 2>$null) | Select-Object -First 1
        if ($cid) {
            $status = (& docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $cid 2>$null)
            if ($status -eq "healthy" -or $status -eq "running") {
                Write-Host "[ok] $Service`: $status"
                return
            }
        }
        Start-Sleep -Seconds 3
    }

    throw "$Service did not become healthy in time"
}

function Wait-OneShot {
    param(
        [string]$Service,
        [int]$DiscoveryAttempts = 180,
        [int]$RunAttempts = 600
    )

    $ErrorActionPreference = "Continue"

    $cid = $null
    for ($i = 0; $i -lt $DiscoveryAttempts; $i++) {
        $cid = @(& docker compose ps -a -q $Service 2>$null) | Select-Object -First 1
        if ($cid) { break }
        Start-Sleep -Seconds 2
    }

    if (-not $cid) {
        throw "$Service container was not created"
    }

    # Let Compose actually start a stopped one-shot container before checking.
    Start-Sleep -Seconds 2

    for ($i = 0; $i -lt $RunAttempts; $i++) {
        $status = (& docker inspect -f '{{.State.Status}}' $cid 2>$null)
        if ($status -eq "exited") {
            $code = [int](& docker inspect -f '{{.State.ExitCode}}' $cid 2>$null)
            if ($code -ne 0) {
                & docker compose logs --tail=120 $Service
                throw "$Service exited with code $code"
            }
            Write-Host "[ok] $Service`: Exited (0)"
            return
        }
        Start-Sleep -Seconds 3
    }

    & docker compose logs --tail=120 $Service
    throw "$Service did not finish in time"
}

function Wait-Trino {
    param([int]$Attempts = 120)

    $ErrorActionPreference = "Continue"

    for ($i = 0; $i -lt $Attempts; $i++) {
        & docker compose exec -T trino curl -fsS http://localhost:8080/v1/info *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[ok] trino: ready"
            return
        }
        Start-Sleep -Seconds 3
    }

    & docker compose logs --tail=100 trino
    throw "Trino is not ready"
}

function Write-Access {
    Write-Host @"

============================================================
  Project is ready (Windows)
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
"@
}
