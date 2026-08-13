# Build frontend into backend/static for single-service Render deploys.
# Usage (from repo root):  .\scripts\build-spa.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\frontend"
$env:VITE_API_URL = ""
npm install
npm run build
$dest = "$root\backend\static"
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
New-Item -ItemType Directory -Path $dest | Out-Null
Copy-Item -Path "$root\frontend\dist\*" -Destination $dest -Recurse -Force
Write-Host "SPA copied to backend/static (VITE_API_URL empty = same-origin API)"
