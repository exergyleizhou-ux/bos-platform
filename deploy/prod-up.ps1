param(
    [string]$EnvFile = ".env",
    [switch]$SeedDemoData
)

$ErrorActionPreference = "Stop"

function Invoke-Docker {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    & docker @Args
    if ($LASTEXITCODE -ne 0) {
        throw "docker $($Args -join ' ') failed with exit code $LASTEXITCODE."
    }
}

function Wait-DockerReady {
    param(
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {        
            & docker info *> $null
            if ($LASTEXITCODE -eq 0) {
                return
            }
            Start-Sleep -Seconds 3
        }
        catch {
            Start-Sleep -Seconds 3
        }
    }

    throw "Docker daemon is not ready. Check Docker Desktop and WSL first."
}

function Invoke-Compose {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    $composeArgs = @("compose", "-f", "docker-compose.prod.yml", "--env-file", $EnvFile) + $Args
    Invoke-Docker -Args $composeArgs
}

if (-not (Test-Path $EnvFile)) {
    if (-not (Test-Path ".env.prod.example")) {
        throw "Missing $EnvFile and .env.prod.example."
    }
    Copy-Item ".env.prod.example" $EnvFile
    Write-Host "Created $EnvFile from .env.prod.example. Update secrets before internet-facing deployment."
}

Wait-DockerReady

Write-Host "Starting production compose stack..."
Invoke-Compose -Args @("up", "-d", "--build")

Write-Host "Running database migrations..."
Invoke-Compose -Args @("exec", "-T", "backend", "alembic", "upgrade", "head")

if ($SeedDemoData) {
    Write-Host "Seeding demo data..."
    Invoke-Compose -Args @("exec", "-T", "backend", "python", "-m", "scripts.seed_data")
}

$healthUrl = "http://127.0.0.1/api/v1/health/live"
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -Method GET -TimeoutSec 5
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    throw "Deployment started but health endpoint is not ready: $healthUrl"
}

Write-Host "Production stack is up."
Write-Host "Nginx: http://127.0.0.1"
Write-Host "Live:  http://127.0.0.1/api/v1/health/live"
Write-Host "Ready: http://127.0.0.1/api/v1/health/ready"
