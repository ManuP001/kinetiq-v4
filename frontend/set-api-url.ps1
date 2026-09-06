<#
.SYNOPSIS
  Point the PWA at an API base URL by rewriting the one line in config.js.
.DESCRIPTION
  Deploying should be editing one line, not a code change (frontend/CLAUDE.md).
  Commit the result and redeploy the static site.
.EXAMPLE
  .\set-api-url.ps1 https://kinetiq-v4-api.onrender.com
#>
param([Parameter(Mandatory = $true)][string]$ApiUrl)
$ErrorActionPreference = 'Stop'

$url = $ApiUrl.TrimEnd('/')
if ($url -notmatch '^https?://[^/]+$') {
  throw "Expected a bare origin like https://kinetiq-v4-api.onrender.com (scheme + host, no path). Got: $ApiUrl"
}
if ($url -like 'http://*' -and $url -notlike 'http://localhost*' -and $url -notlike 'http://127.0.0.1*') {
  Write-Warning "$url is plain HTTP. A phone will refuse the camera and block the call as mixed content. Use https for anything that isn't localhost."
}

$cfg = Join-Path $PSScriptRoot 'config.js'
$text = Get-Content $cfg -Raw
$updated = [regex]::Replace($text, 'API_BASE_URL:\s*"[^"]*"', "API_BASE_URL: `"$url`"")
if ($updated -eq $text) { throw "Could not find API_BASE_URL in $cfg -- has the file been restructured?" }

Set-Content -Path $cfg -Value $updated -NoNewline -Encoding utf8
Write-Host "config.js API_BASE_URL set to $url" -ForegroundColor Green
Write-Host "Next: git commit -am 'point PWA at the deployed API' && git push, then redeploy the static site."
