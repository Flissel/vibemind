#requires -Version 7
<#
.SYNOPSIS
    Register the error-monitor agent's 20-min cron job with OpenFang.

.DESCRIPTION
    Idempotent. Resolves the agent's UUID via /api/agents, then either:
      - lists existing cron jobs and skips if one already exists with our name, or
      - POSTs a new job to /api/cron/jobs.

    The agent must already be spawned (template:error-monitor) — the sidecar
    handles that via auto-heal when openfang_debugger_launch.py is run with
    OPENFANG_AGENT_NAME=error-monitor. This script runs AFTER that.

.PARAMETER OpenfangUrl
    Default http://127.0.0.1:4200

.PARAMETER IntervalSec
    Default 1200 (20 min). OpenFang validates 60 <= every_secs <= 86400.

.PARAMETER JobName
    Default "error-monitor-scan". Name must be alphanumeric + spaces/hyphens/underscores.

.EXAMPLE
    pwsh -File scripts/openfang_error_monitor_register.ps1
#>
param(
    [string]$OpenfangUrl = "http://127.0.0.1:4200",
    [int]$IntervalSec = 1200,
    [string]$JobName = "error-monitor-scan",
    [string]$AgentName = "error-monitor"
)
$ErrorActionPreference = 'Stop'

function Get-AgentId {
    param([string]$Name)
    $agents = Invoke-RestMethod "$OpenfangUrl/api/agents" -TimeoutSec 10
    return ($agents | Where-Object { $_.name -eq $Name } | Select-Object -First 1).id
}

function Get-ExistingJob {
    param([string]$AgentId, [string]$JobName)
    try {
        $resp = Invoke-RestMethod "$OpenfangUrl/api/cron/jobs?agent_id=$AgentId" -TimeoutSec 10
        return $resp.jobs | Where-Object { $_.name -eq $JobName } | Select-Object -First 1
    } catch {
        return $null
    }
}

Write-Host "=== 1. Resolve agent id ===" -ForegroundColor Cyan
$id = Get-AgentId -Name $AgentName
if (-not $id) {
    Write-Host "  agent '$AgentName' not registered. Spawn it first:" -ForegroundColor Red
    Write-Host '  Invoke-RestMethod -Method Post http://127.0.0.1:4200/api/agents -ContentType application/json -Body ''{"template":"error-monitor"}''' -ForegroundColor DarkGray
    exit 2
}
Write-Host "  $id" -ForegroundColor Green

Write-Host ""
Write-Host "=== 2. Check for existing cron job ===" -ForegroundColor Cyan
$existing = Get-ExistingJob -AgentId $id -JobName $JobName
if ($existing) {
    Write-Host "  job '$JobName' already exists: $($existing.id)" -ForegroundColor Yellow
    Write-Host "  enabled=$($existing.enabled), next_run=$($existing.next_run)"
    Write-Host "  to delete: Invoke-RestMethod -Method Delete $OpenfangUrl/api/cron/jobs/$($existing.id)"
    exit 0
}

Write-Host ""
Write-Host "=== 3. Create cron job ===" -ForegroundColor Cyan
$jobBody = @{
    agent_id = $id
    name     = $JobName
    enabled  = $true
    schedule = @{ kind = "every"; every_secs = $IntervalSec }
    action   = @{
        kind         = "agent_turn"
        message      = "Run your scan workflow now. Time window: last 25 min."
        timeout_secs = 300
    }
    delivery = @{ kind = "none" }
} | ConvertTo-Json -Depth 5

Write-Host "Body:"
Write-Host $jobBody -ForegroundColor DarkGray
Write-Host ""

try {
    $resp = Invoke-RestMethod -Method Post -Uri "$OpenfangUrl/api/cron/jobs" `
        -ContentType 'application/json' -Body $jobBody -TimeoutSec 15
    Write-Host "Created:" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 5
} catch {
    Write-Host "Failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            Write-Host "Body: $($reader.ReadToEnd())" -ForegroundColor Yellow
        } catch {}
    }
    exit 1
}
