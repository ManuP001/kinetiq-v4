<#
.SYNOPSIS
  Run the whole prototype locally with a real webcam (Windows twin of run_local.sh).
.DESCRIPTION
  API -> http://localhost:8000, PWA -> http://localhost:8080, CORS wired between
  them. http://localhost is a secure context by browser spec, so getUserMedia
  works without HTTPS. That stops being true for a phone reaching this machine by
  LAN IP -- see docs/DEPLOY_RUNBOOK.md for the deployed path.
#>
param(
  [int]$PortApi = 8000,
  [int]$PortPwa = 8080
)
$ErrorActionPreference = 'Stop'

$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..\..')
$env:PROTOTYPE_API_CORS_ORIGINS = "http://localhost:$PortPwa"

$api = Start-Process -PassThru -NoNewWindow -FilePath 'python' `
  -ArgumentList @('-m','uvicorn','prototype_api.main:app','--host','127.0.0.1','--port',"$PortApi") `
  -WorkingDirectory (Join-Path $Root 'evals\gate0')

$pwa = Start-Process -PassThru -NoNewWindow -FilePath 'python' `
  -ArgumentList @('-m','http.server',"$PortPwa",'--bind','127.0.0.1') `
  -WorkingDirectory (Join-Path $Root 'frontend')

try {
  Write-Host -NoNewline 'waiting for /health '
  $ok = $false
  foreach ($i in 1..40) {
    try {
      $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:$PortApi/health"
      if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
    Write-Host -NoNewline '.'
    Start-Sleep -Milliseconds 500
  }
  Write-Host ''

  if (-not $ok) {
    Write-Host 'API did not come up. Check the uvicorn output above.' -ForegroundColor Red
  } else {
    Write-Host ''
    Write-Host "  API : http://localhost:$PortApi/health" -ForegroundColor Green
    Write-Host "  PWA : http://localhost:$PortPwa" -ForegroundColor Green
    Write-Host 'Ctrl+C to stop both.'
  }
  Wait-Process -Id $api.Id
} finally {
  foreach ($p in @($api, $pwa)) {
    if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
  }
}
