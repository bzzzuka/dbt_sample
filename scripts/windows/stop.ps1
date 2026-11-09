# stop.ps1 - Stop the project on Windows; volumes are preserved.
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\common.ps1")

Assert-Docker

Write-Host "Stopping project (volumes are preserved)..."
Invoke-Compose stop
Write-Host "Done. Start again with .\scripts\windows\start-all.ps1"
