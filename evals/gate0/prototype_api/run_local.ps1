<#
.SYNOPSIS
  Run the whole Kinetiq v4 live prototype LOCALLY with a real webcam -- API + PWA, one command.

.DESCRIPTION
  Starts two processes and leaves them running until you press Ctrl+C:
    1. prototype_api  (this repo)     -> http://localhost:<ApiPort>
    2. the frontend/ PWA (in this repo) -> http://localhost:<PwaPort>

  It sets PROTOTYPE_API_CORS_ORIGINS to the PWA's local origin(s) so the browser's CORS check
  passes, waits for /health, and prints the URL to open.

  WHY THIS WORKS WITHOUT HTTPS: http://localhost (and http://127.0.0.1) is a SECURE CONTEXT by
  browser spec, so getUserMedia/camera works and there is no mixed-content problem -- an HTTP page
  calling an HTTP API is same-scheme. That is only true for localhost; the moment you want this on
  a PHONE (a different device, reached by LAN IP or a public URL) both sides must be HTTPS -- see
  ../../../docs/DEPLOY_RUNBOOK.md.

  Needs an internet connection on first run: the PWA fetches the MediaPipe pose model from a CDN.
  NOTE: frontend/config.js defaults API_BASE_URL to http://localhost:8000. If you pass a different
  -ApiPort, edit that one line in config.js to match.

.PARAMETER ApiPort
  Port for prototype_api. Default 8000.

.PARAMETER PwaPort
  Port for the frontend static server. Default 8080.

.PARAMETER PwaDir
  Path to the PWA. Defaults to ../../../frontend (the frontend/ folder in this monorepo).

.EXAMPLE
  .\run_local.ps1
  .\run_local.ps1 -ApiPort 8001 -PwaPort 8081
#>
[CmdletBinding()]
param(
    [int]$ApiPort = 8000,
    [int]$PwaPort = 8080,
    [string]$PwaDir
)

$ErrorActionPreference = 'Stop'

# --- resolve paths -----------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path   # .../evals/gate0/prototype_api
$Gate0Dir  = Split-Path -Parent $ScriptDir                      # .../evals/gate0
$RepoRoot  = Split-Path -Parent (Split-Path -Parent $Gate0Dir)  # .../kinetiq v4 (this monorepo)

if (-not $PwaDir) { $PwaDir = Join-Path $RepoRoot 'frontend' }

if (-not (Test-Path (Join-Path $PwaDir 'index.html'))) {
    Write-Host "ERROR: PWA not found at: $PwaDir" -ForegroundColor Red
    Write-Host "       (looked for index.html there). The camera PWA is the frontend/ folder in" -ForegroundColor Red
    Write-Host "       this repo. Pass -PwaDir <path> if you moved it." -ForegroundColor Red
    exit 1
}

# --- find python -------------------------------------------------------------------------------
$Py = $null
foreach ($candidate in @('python', 'py')) {
    try { & $candidate --version *> $null; if ($LASTEXITCODE -eq 0) { $Py = $candidate; break } } catch { }
}
if (-not $Py) {
    Write-Host "ERROR: no 'python' or 'py' on PATH. Install Python 3.12+ and re-run." -ForegroundColor Red
    exit 1
}

# --- fail early on ports already in use --------------------------------------------------------
foreach ($p in @(@{n='API'; v=$ApiPort}, @{n='PWA'; v=$PwaPort})) {
    $inUse = Get-NetTCPConnection -State Listen -LocalPort $p.v -ErrorAction SilentlyContinue
    if ($inUse) {
        Write-Host "ERROR: port $($p.v) ($($p.n)) is already in use." -ForegroundColor Red
        Write-Host "       Stop whatever is on it, or re-run with -$($p.n)Port <other>." -ForegroundColor Red
        exit 1
    }
}

# --- CORS: allow BOTH localhost and 127.0.0.1 forms of the PWA origin ---------------------------
# They are DIFFERENT origins to the browser. Allowing both means it works whichever one you type.
$env:PROTOTYPE_API_CORS_ORIGINS = "http://localhost:$PwaPort,http://127.0.0.1:$PwaPort"

Write-Host ""
Write-Host "Kinetiq v4 live prototype -- LOCAL run" -ForegroundColor Cyan
Write-Host "  API  : $Gate0Dir"
Write-Host "  PWA  : $PwaDir"
Write-Host "  CORS : $env:PROTOTYPE_API_CORS_ORIGINS"
Write-Host ""

$procs = @()
try {
    # --- 1. prototype_api ----------------------------------------------------------------------
    # Same invocation shape as the container CMD (uvicorn console entry, CWD=evals/gate0 so that
    # `import gate_config` / `detector.*` / `golden_loader` resolve).
    Write-Host "Starting prototype_api on http://localhost:$ApiPort ..." -ForegroundColor Yellow
    $api = Start-Process -FilePath $Py `
        -ArgumentList @('-m', 'uvicorn', 'prototype_api.main:app', '--host', '127.0.0.1', '--port', "$ApiPort") `
        -WorkingDirectory $Gate0Dir -PassThru -NoNewWindow
    $procs += $api

    # --- 2. frontend/ static server ------------------------------------------------------------
    Write-Host "Starting the PWA on http://localhost:$PwaPort ..." -ForegroundColor Yellow
    $pwa = Start-Process -FilePath $Py `
        -ArgumentList @('-m', 'http.server', "$PwaPort", '--bind', '127.0.0.1') `
        -WorkingDirectory $PwaDir -PassThru -NoNewWindow
    $procs += $pwa

    # --- wait for the API to answer -------------------------------------------------------------
    $healthUrl = "http://127.0.0.1:$ApiPort/health"
    $ok = $false
    foreach ($attempt in 1..30) {
        Start-Sleep -Milliseconds 500
        if ($api.HasExited) { throw "prototype_api exited early (exit code $($api.ExitCode)) -- see its output above." }
        try {
            $r = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3
            if ($r.status -eq 'ok') { $ok = $true; break }
        } catch { }
    }
    if (-not $ok) { throw "prototype_api did not answer $healthUrl within ~15s." }

    Write-Host ""
    Write-Host "  /health OK -- supported exercises: $($r.supported_exercises -join ', ')" -ForegroundColor Green
    Write-Host ""
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host "  OPEN THIS IN YOUR BROWSER:  http://localhost:$PwaPort" -ForegroundColor Green
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  config.js already points the PWA at http://localhost:8000 (the default API port)."
    Write-Host "  If you changed -ApiPort, edit frontend/config.js API_BASE_URL to match."
    Write-Host ""
    Write-Host "  Then: allow camera -> pick Squat/Push-up/Lunge -> do a few reps -> End set -> Summary."
    Write-Host ""
    Write-Host "  Press Ctrl+C to stop both servers." -ForegroundColor Yellow
    Write-Host ""

    while ($true) {
        Start-Sleep -Seconds 1
        if ($api.HasExited) { Write-Host "prototype_api exited (code $($api.ExitCode))." -ForegroundColor Red; break }
        if ($pwa.HasExited) { Write-Host "PWA static server exited (code $($pwa.ExitCode))." -ForegroundColor Red; break }
    }
}
finally {
    Write-Host ""
    Write-Host "Shutting down..." -ForegroundColor Yellow
    foreach ($p in $procs) {
        if ($p -and -not $p.HasExited) {
            try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch { }
        }
    }
    Remove-Item Env:\PROTOTYPE_API_CORS_ORIGINS -ErrorAction SilentlyContinue
    Write-Host "Stopped." -ForegroundColor Yellow
}
