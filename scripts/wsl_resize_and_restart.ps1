# wsl_resize_and_restart.ps1
# Bump Docker WSL2 VM memory to 12GB and restart WSL + Docker Desktop.
# The openclaw image rebuild OOM-crashed Docker because the WSL2 VM was
# capped at 8GB. 12GB gives the build headroom.
# Run in an ELEVATED PowerShell. This kills ALL WSL/Docker containers
# (they autostart back EXCEPT OpenFang + Brain which are manual).

$ErrorActionPreference = "Stop"
$wslConfig = "$env:USERPROFILE\.wslconfig"

Write-Host "1. Rewriting $wslConfig (backup .bak)"
if (Test-Path $wslConfig) { Copy-Item $wslConfig "$wslConfig.bak" -Force }
$lines = @("[wsl2]", "memory=12GB", "processors=8", "swap=8GB")
Set-Content -Path $wslConfig -Value $lines -Encoding ASCII
Get-Content $wslConfig | ForEach-Object { Write-Host "   $_" }

Write-Host "2. Stopping Docker Desktop"
Get-Process "Docker Desktop" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5

Write-Host "3. wsl --shutdown"
wsl --shutdown
Start-Sleep -Seconds 8

Write-Host "4. Restarting Docker Desktop"
$ddExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $ddExe) { Start-Process $ddExe } else { Write-Host "   Docker Desktop.exe not found - start manually" }

Write-Host "5. Waiting for Docker engine (up to 5 min)"
$deadline = (Get-Date).AddMinutes(5)
$engineUp = $false
while ((Get-Date) -lt $deadline) {
    $v = docker version --format "{{.Server.Version}}" 2>$null
    if ($LASTEXITCODE -eq 0 -and $v) { Write-Host "   engine UP (Server $v)"; $engineUp = $true; break }
    Start-Sleep -Seconds 10
    Write-Host "   ...waiting"
}

Write-Host "6. New VM memory limit:"
wsl -d docker-desktop -e cat /proc/meminfo 2>$null | Select-String "MemTotal" | ForEach-Object { Write-Host "   $_" }

if ($engineUp) { Write-Host "DONE - tell Claude 'wsl done'" } else { Write-Host "ENGINE DID NOT COME UP - check Docker Desktop manually" }
