<#
.SYNOPSIS
  Point the PWA at a given API base URL by rewriting the ONE line in config.js.
.EXAMPLE
  .\set-api-url.ps1 https://kinetiq-v4-api.onrender.com
#>
param([Parameter(Mandatory=$true)][string]$ApiUrl)
$ErrorActionPreference = 'Stop'
$cfg = Join-Path $PSScriptRoot 'config.js'
$url = $ApiUrl.TrimEnd('/')
$text = Get-Content $cfg -Raw
$text = [regex]::Replace($text, 'API_BASE_URL:\s*"[^"]*"', "API_BASE_URL: `"$url`"")
Set-Content -Path $cfg -Value $text -NoNewline
Write-Host "config.js API_BASE_URL set to $url" -ForegroundColor Green
